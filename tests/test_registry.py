import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import registry


class RegistryTests(unittest.TestCase):
    def tearDown(self):
        registry.refresh_tools()

    def test_detect_category_covers_all_five_categories(self):
        self.assertEqual(registry.detect_category('mp4'), 'video')
        self.assertEqual(registry.detect_category('.MP3'), 'audio')
        self.assertEqual(registry.detect_category('webp'), 'image')
        self.assertEqual(registry.detect_category('docx'), 'document')
        self.assertEqual(registry.detect_category('pdf'), 'pdf')
        self.assertIsNone(registry.detect_category('exe'))
        self.assertIsNone(registry.detect_category(''))

    def test_target_labels(self):
        self.assertEqual(registry.target_label('ocr_txt'), 'Text (OCR)')
        self.assertEqual(registry.target_label('mp4'), 'MP4')

    def test_windows_convert_collision_rejected(self):
        def fake_which(name):
            if name == 'convert':
                return r'C:\Windows\system32\convert.exe'
            return None

        fake_proc = mock.Mock(stdout='Invalid parameter - -version', stderr='')
        with mock.patch('registry.shutil.which', side_effect=fake_which), \
             mock.patch('registry.subprocess.run', return_value=fake_proc):
            self.assertIsNone(registry._find_magick())

    def test_build_cmd_all_categories_without_requiring_installed_tools(self):
        cmd, out = registry.build_cmd('video', 'in.mp4', 'out', 'mp3', require_tool=False)
        self.assertEqual(out, 'out.mp3')
        self.assertIn('-vn', cmd)

        cmd, out = registry.build_cmd('video', 'in.mp4', 'out', 'gif', require_tool=False)
        self.assertEqual(out, 'out.gif')
        self.assertIn('fps=10,scale=480:-1', cmd)

        cmd, out = registry.build_cmd('audio', 'in.wav', 'out', 'flac', require_tool=False)
        self.assertEqual(out, 'out.flac')
        self.assertNotIn('-vn', cmd)

        cmd, out = registry.build_cmd('image', 'in.png', 'out', 'ocr_txt', require_tool=False)
        self.assertEqual(out, 'out.txt')
        self.assertTrue(cmd[0].lower().endswith('tesseract') or 'tesseract' in cmd[0].lower())
        self.assertEqual(cmd[1:], ['in.png', 'out'])

        cmd, out = registry.build_cmd('document', 'in.md', 'out', 'docx', require_tool=False)
        self.assertEqual(out, 'out.docx')
        self.assertEqual(cmd[1:], ['in.md', '-o', 'out.docx'])

        cmd, out = registry.build_cmd('pdf', 'in.pdf', 'out', 'png', require_tool=False)
        self.assertEqual(out, 'out.png')
        self.assertEqual(cmd[1:], ['-png', 'in.pdf', 'out'])

        cmd, out = registry.build_cmd('pdf', 'in.pdf', 'out', 'txt', require_tool=False)
        self.assertEqual(out, 'out.txt')
        self.assertEqual(cmd[1:], ['in.pdf', 'out.txt'])

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            registry.build_cmd('video', 'in.mp4', 'out', 'docx', require_tool=False)

    def test_available_targets_hides_missing_tools_and_pdf_policy(self):
        fake_tools = {
            'ffmpeg': None,
            'magick': '/usr/bin/magick',
            'magick_pdf': False,
            'tesseract': '/usr/bin/tesseract',
            'pandoc': None,
            'pdftoppm': '/usr/bin/pdftoppm',
            'pdftotext': None,
        }
        with mock.patch('registry.get_tools', return_value=fake_tools):
            self.assertEqual(registry.available_targets('video'), [])
            self.assertEqual(registry.available_targets('document'), [])
            self.assertNotIn('pdf', registry.available_targets('image'))
            self.assertIn('ocr_txt', registry.available_targets('image'))
            self.assertIn('webp', registry.available_targets('image'))
            self.assertEqual(registry.available_targets('pdf'), ['png', 'jpg'])

    def test_collect_multipage_outputs_natural_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'out'
            for name in ('out-10.png', 'out-2.png', 'out-1.png'):
                (Path(tmp) / name).write_bytes(b'png')
            found = registry.collect_multipage_outputs(base, 'png')
            self.assertEqual([p.name for p in found], ['out-1.png', 'out-2.png', 'out-10.png'])

    def test_live_tesseract_ocr_if_installed(self):
        tools = registry.get_tools()
        if not tools['tesseract']:
            self.skipTest('tesseract not installed')
        # Generate a clean PNG with Pillow (or skip if unavailable) or minimal bitmap test
        # We check via PIL in global python? No, test .venv only has flask/waitress; create minimal valid BMP/PNG?
        # Tesseract reads uncompressed BMP directly! Write a 24-bit BMP or test PNG via zlib/struct.
        with tempfile.TemporaryDirectory() as tmp:
            # Minimal valid 1x1 white PNG (Tesseract accepts PNG cleanly even if empty text)
            import struct
            import zlib

            def make_png(width, height):
                raw = b''.join(b'\x00' + b'\xff\xff\xff' * width for _ in range(height))
                def chunk(tag, data):
                    return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xffffffff)
                return (
                    b'\x89PNG\r\n\x1a\n'
                    + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0))
                    + chunk(b'IDAT', zlib.compress(raw))
                    + chunk(b'IEND', b'')
                )

            src = Path(tmp) / 'sample.png'
            src.write_bytes(make_png(64, 32))
            dst_base = Path(tmp) / 'out'
            cmd, out = registry.build_cmd('image', src, dst_base, 'ocr_txt')
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue(Path(out).is_file())

    def test_live_pdftotext_if_installed(self):
        tools = registry.get_tools()
        if not tools['pdftotext']:
            self.skipTest('pdftotext not installed')
        pdf_bytes = (
            b'%PDF-1.4\n'
            b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
            b'2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n'
            b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]'
            b'/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n'
            b'4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n'
            b'5 0 obj<</Length 44>>stream\n'
            b'BT /F1 12 Tf 20 100 Td (Hello Converza) Tj ET\n'
            b'endstream\nendobj\n'
            b'xref\n0 6\n'
            b'0000000000 65535 f \n'
            b'0000000009 00000 n \n'
            b'0000000056 00000 n \n'
            b'0000000111 00000 n \n'
            b'0000000229 00000 n \n'
            b'0000000297 00000 n \n'
            b'trailer<</Size 6/Root 1 0 R>>\nstartxref\n391\n%%EOF\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'sample.pdf'
            src.write_bytes(pdf_bytes)
            dst_base = Path(tmp) / 'out'
            cmd, out = registry.build_cmd('pdf', src, dst_base, 'txt')
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue(Path(out).is_file())
            self.assertIn('Hello Converza', Path(out).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
