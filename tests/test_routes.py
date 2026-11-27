import io
import re
import shutil
import struct
import sys
import tempfile
import time
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
import config
import jobs
import registry


def _make_sample_pdf(text: str = 'Hello Converza') -> bytes:
    stream = f'BT /F1 12 Tf 20 100 Td ({text}) Tj ET\n'.encode('ascii')
    return (
        b'%PDF-1.4\n'
        b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
        b'2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n'
        b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]'
        b'/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n'
        b'4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n'
        + f'5 0 obj<</Length {len(stream)}>>stream\n'.encode('ascii')
        + stream
        + b'endstream\nendobj\n'
        b'xref\n0 6\n'
        b'0000000000 65535 f \n'
        b'0000000009 00000 n \n'
        b'0000000056 00000 n \n'
        b'0000000111 00000 n \n'
        b'0000000229 00000 n \n'
        b'0000000297 00000 n \n'
        b'trailer<</Size 6/Root 1 0 R>>\nstartxref\n391\n%%EOF\n'
    )


def _make_png(width: int = 32, height: int = 32) -> bytes:
    raw = b''.join(b'\x00' + b'\xff\xff\xff' * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack('!I', len(data))
            + tag
            + data
            + struct.pack('!I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw))
        + chunk(b'IEND', b'')
    )


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.orig_up = config.UPLOAD_DIR
        self.orig_out = config.OUTPUT_DIR
        self.orig_jobs_up = jobs.UPLOAD_DIR
        self.orig_jobs_out = jobs.OUTPUT_DIR
        self.orig_app_up = None

        config.UPLOAD_DIR = self.tmp_dir / 'uploads'
        config.OUTPUT_DIR = self.tmp_dir / 'outputs'
        jobs.UPLOAD_DIR = config.UPLOAD_DIR
        jobs.OUTPUT_DIR = config.OUTPUT_DIR
        import app as app_mod
        self.orig_app_up = app_mod.UPLOAD_DIR
        self.orig_app_out = app_mod.OUTPUT_DIR
        app_mod.UPLOAD_DIR = config.UPLOAD_DIR
        app_mod.OUTPUT_DIR = config.OUTPUT_DIR

        with jobs.LOCK:
            jobs.JOBS.clear()
        self.app = create_app(start_cleanup=False, clean_on_start=False)
        self.client = self.app.test_client()

    def tearDown(self):
        import app as app_mod
        with jobs.LOCK:
            jobs.JOBS.clear()
        config.UPLOAD_DIR = self.orig_up
        config.OUTPUT_DIR = self.orig_out
        jobs.UPLOAD_DIR = self.orig_jobs_up
        jobs.OUTPUT_DIR = self.orig_jobs_out
        app_mod.UPLOAD_DIR = self.orig_app_up
        app_mod.OUTPUT_DIR = self.orig_app_out
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _extract_job_id(self, html: str) -> str:
        m = re.search(r'data-job-id="([0-9a-f]+)"', html)
        self.assertIsNotNone(m, msg=f'No job id found in:\n{html}')
        return m.group(1)

    def _wait_until_finished(self, job_id: str, timeout: float = 10.0) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            res = self.client.get(f'/jobs/{job_id}')
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            if 'data-job-status="done"' in html or 'data-job-status="error"' in html:
                return html
            time.sleep(0.1)
        self.fail(f'Job {job_id} did not finish within {timeout}s')

    def test_index_and_static_assets_load(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Converza', html)
        self.assertIn('data-theme="converza-dark"', html)
        self.assertIn('Max 500 MB', html)
        self.assertIn('/static/css/app.css', html)
        self.assertIn('/static/js/htmx.min.js', html)

        css_res = self.client.get('/static/css/app.css')
        self.assertEqual(css_res.status_code, 200)
        self.assertGreater(len(css_res.data), 1000)
        css_res.close()

        js_res = self.client.get('/static/js/htmx.min.js')
        self.assertEqual(js_res.status_code, 200)
        self.assertGreater(len(js_res.data), 1000)
        js_res.close()

    def test_upload_unicode_traversal_and_skipped(self):
        tools = registry.get_tools()
        if not tools['pdftotext']:
            self.skipTest('pdftotext not installed')

        data = {
            'files': [
                (io.BytesIO(_make_sample_pdf()), '../测试 sample (1).pdf'),
                (io.BytesIO(b'MZ...'), 'malware.exe'),
            ]
        }
        res = self.client.post('/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('测试 sample (1).pdf', html)
        self.assertIn('malware.exe', html)
        job_id = self._extract_job_id(html)
        self.assertTrue((config.UPLOAD_DIR / job_id / 'in.pdf').is_file())

    def test_end_to_end_pdf_to_txt_and_download(self):
        if not registry.get_tools()['pdftotext']:
            self.skipTest('pdftotext not installed')

        res = self.client.post(
            '/upload',
            data={'files': (io.BytesIO(_make_sample_pdf('Phase3 Live Test')), 'doc with spaces.pdf')},
            content_type='multipart/form-data',
        )
        self.assertEqual(res.status_code, 200)
        job_id = self._extract_job_id(res.get_data(as_text=True))

        res = self.client.post(f'/convert/{job_id}', data={'target': 'txt'})
        self.assertEqual(res.status_code, 200)

        done_html = self._wait_until_finished(job_id)
        self.assertIn('data-job-status="done"', done_html)
        self.assertIn(f'/download/{job_id}', done_html)

        dl = self.client.get(f'/download/{job_id}')
        self.assertEqual(dl.status_code, 200)
        self.assertIn('doc_with_spaces.txt', dl.headers.get('Content-Disposition', ''))
        self.assertIn('Phase3 Live Test', dl.get_data(as_text=True))
        dl.close()

    def test_corrupt_file_marks_error_not_500(self):
        if not registry.get_tools()['pdftotext']:
            self.skipTest('pdftotext not installed')

        res = self.client.post(
            '/upload',
            data={'files': (io.BytesIO(b'not a pdf at all'), 'broken.pdf')},
            content_type='multipart/form-data',
        )
        job_id = self._extract_job_id(res.get_data(as_text=True))
        self.client.post(f'/convert/{job_id}', data={'target': 'txt'})
        err_html = self._wait_until_finished(job_id)
        self.assertIn('data-job-status="error"', err_html)
        self.assertIn('Retry', err_html)

    def test_invalid_target_and_missing_job_rejected(self):
        if not registry.get_tools()['pdftotext']:
            self.skipTest('pdftotext not installed')

        res = self.client.post(
            '/upload',
            data={'files': (io.BytesIO(_make_sample_pdf()), 'ok.pdf')},
            content_type='multipart/form-data',
        )
        job_id = self._extract_job_id(res.get_data(as_text=True))
        self.assertEqual(self.client.post(f'/convert/{job_id}', data={'target': 'docx'}).status_code, 400)
        self.assertEqual(self.client.post('/convert/doesnotexist', data={'target': 'txt'}).status_code, 404)
        self.assertEqual(self.client.get(f'/download/{job_id}').status_code, 404)

    def test_multipage_finalize_creates_zip(self):
        job, _ = jobs.create_job('slides.pdf', 'pdf', 'pdf', size=100)
        out_dir = config.OUTPUT_DIR / job['id']
        (out_dir / 'out-1.png').write_bytes(_make_png(4, 4))
        (out_dir / 'out-2.png').write_bytes(_make_png(4, 4))
        final_out = jobs._finalize_output(job['id'], 'pdf', 'png', out_dir / 'out.png')
        self.assertEqual(final_out.name, 'out.zip')
        with zipfile.ZipFile(final_out) as zf:
            self.assertEqual(zf.namelist(), ['out-1.png', 'out-2.png'])

    def test_cleanup_expired_deletes_old_jobs_and_files(self):
        job, in_path = jobs.create_job('old.png', 'image', 'png', size=10)
        in_path.write_bytes(_make_png(4, 4))
        with jobs.LOCK:
            jobs.JOBS[job['id']]['created'] = time.time() - 7200
        removed = jobs.cleanup_expired(ttl_seconds=3600)
        self.assertEqual(removed, 1)
        self.assertIsNone(jobs.get_job(job['id']))
        self.assertFalse((config.UPLOAD_DIR / job['id']).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
