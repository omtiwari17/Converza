import base64
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
import config
import jobs
import registry


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.orig_up = config.UPLOAD_DIR
        self.orig_out = config.OUTPUT_DIR
        self.orig_jobs_up = jobs.UPLOAD_DIR
        self.orig_jobs_out = jobs.OUTPUT_DIR

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
        os.environ.pop('CONVERZA_PASSWORD', None)
        config.UPLOAD_DIR = self.orig_up
        config.OUTPUT_DIR = self.orig_out
        jobs.UPLOAD_DIR = self.orig_jobs_up
        jobs.OUTPUT_DIR = self.orig_jobs_out
        app_mod.UPLOAD_DIR = self.orig_app_up
        app_mod.OUTPUT_DIR = self.orig_app_out
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_shell_true_anywhere_in_source(self):
        import ast

        root = Path(__file__).resolve().parent.parent
        for py_file in ('app.py', 'jobs.py', 'registry.py', 'config.py'):
            tree = ast.parse((root / py_file).read_text(encoding='utf-8'), filename=py_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == 'shell':
                            self.assertIsInstance(kw.value, ast.Constant, msg=f'Dynamic shell kwarg in {py_file}')
                            self.assertIs(kw.value.value, False, msg=f'shell=True in {py_file}')
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ('system', 'popen'):
                        self.fail(f'Forbidden shell call .{node.func.attr} in {py_file}')

    def test_security_headers_present(self):
        res = self.client.get('/')
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(res.headers.get('X-Frame-Options'), 'SAMEORIGIN')

    def test_backslash_traversal_and_dotfile_rejected_safely(self):
        fake_tools = {k: None for k in registry.get_tools()}
        fake_tools['pdftotext'] = 'pdftotext'
        with mock.patch('registry.get_tools', return_value=fake_tools):
            res = self.client.post(
                '/upload',
                data={
                    'files': [
                        (io.BytesIO(b'%PDF-1.4'), r'..\..\Windows\system32\evil.pdf'),
                        (io.BytesIO(b'hidden'), '.pdf'),
                        (io.BytesIO(b'empty'), ''),
                    ]
                },
                content_type='multipart/form-data',
            )
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            ids = re.findall(r'data-job-id="([0-9a-f]+)"', html)
            self.assertEqual(len(ids), 1)
            self.assertIn('evil.pdf', html)
            self.assertIn('.pdf', html)
            self.assertTrue((config.UPLOAD_DIR / ids[0] / 'in.pdf').is_file())

    def test_invalid_job_id_traversal_rejected(self):
        self.assertEqual(self.client.get('/jobs/..%2F..%2Fetc').status_code, 404)
        self.assertEqual(self.client.post('/convert/not-a-uuid', data={'target': 'txt'}).status_code, 404)
        self.assertEqual(self.client.get('/download/not-a-uuid').status_code, 404)
        self.assertEqual(self.client.get('/zip?ids=../secret').status_code, 404)
        self.assertEqual(
            self.client.post('/convert-all', data={'target_00000000000000000000000000000000': 'txt'}).status_code,
            404,
        )

    def test_subprocess_timeout_sets_error_state(self):
        job, _ = jobs.create_job('slow.mp4', 'video', 'mp4', size=100)
        with mock.patch('jobs.subprocess.run', side_effect=subprocess.TimeoutExpired(cmd=['ffmpeg'], timeout=900)):
            jobs.run_job(job['id'], ['ffmpeg', '-i', 'in.mp4', 'out.mp3'], config.OUTPUT_DIR / job['id'] / 'out.mp3', 'video', 'mp3')
        updated = jobs.get_job(job['id'])
        self.assertEqual(updated['status'], 'error')
        self.assertEqual(updated['error'], 'Timed out')

    def test_queued_jobs_run_sequentially_never_overlapping(self):
        active = 0
        max_active = 0
        guard = threading.Lock()

        def slow_run(cmd, **_kwargs):
            nonlocal active, max_active
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.15)
            Path(cmd[-1]).write_bytes(b'ok')
            with guard:
                active -= 1
            return mock.Mock(returncode=0)

        j1, _ = jobs.create_job('one.txt', 'document', 'txt', size=5)
        j2, _ = jobs.create_job('two.txt', 'document', 'txt', size=5)

        with mock.patch('jobs.subprocess.run', side_effect=slow_run):
            jobs.submit(j1['id'], ['pandoc', 'in.txt', '-o', str(config.OUTPUT_DIR / j1['id'] / 'out.html')], config.OUTPUT_DIR / j1['id'] / 'out.html', 'html')
            jobs.submit(j2['id'], ['pandoc', 'in.txt', '-o', str(config.OUTPUT_DIR / j2['id'] / 'out.html')], config.OUTPUT_DIR / j2['id'] / 'out.html', 'html')

            deadline = time.time() + 5.0
            while time.time() < deadline:
                s1 = jobs.get_job(j1['id'])['status']
                s2 = jobs.get_job(j2['id'])['status']
                if s1 == 'done' and s2 == 'done':
                    break
                time.sleep(0.05)

        self.assertEqual(jobs.get_job(j1['id'])['status'], 'done')
        self.assertEqual(jobs.get_job(j2['id'])['status'], 'done')
        self.assertEqual(max_active, 1)

    def test_cleanup_preserves_running_job_and_removes_finished_expired(self):
        running_job, _ = jobs.create_job('busy.pdf', 'pdf', 'pdf', size=10)
        old_done, _ = jobs.create_job('old.pdf', 'pdf', 'pdf', size=10)
        with jobs.LOCK:
            jobs.JOBS[running_job['id']]['status'] = 'running'
            jobs.JOBS[running_job['id']]['created'] = time.time() - 7200
            jobs.JOBS[old_done['id']]['status'] = 'done'
            jobs.JOBS[old_done['id']]['created'] = time.time() - 7200

        removed = jobs.cleanup_expired(ttl_seconds=3600)
        self.assertEqual(removed, 1)
        self.assertIsNotNone(jobs.get_job(running_job['id']))
        self.assertIsNone(jobs.get_job(old_done['id']))
        self.assertFalse((config.UPLOAD_DIR / old_done['id']).exists())
        self.assertFalse((config.OUTPUT_DIR / old_done['id']).exists())

    def test_optional_password_gate(self):
        os.environ['CONVERZA_PASSWORD'] = 'secret123'
        # /healthz remains open for liveness probes
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        # / requires Basic auth when CONVERZA_PASSWORD is set
        self.assertEqual(self.client.get('/').status_code, 401)
        token = base64.b64encode(b'user:secret123').decode('ascii')
        ok = self.client.get('/', headers={'Authorization': f'Basic {token}'})
        self.assertEqual(ok.status_code, 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
