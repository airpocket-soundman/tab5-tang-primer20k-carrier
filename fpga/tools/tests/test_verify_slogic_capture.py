import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1]/'verify_slogic_capture.py'
spec = importlib.util.spec_from_file_location('verify_slogic_capture', MODULE)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class CaptureTests(unittest.TestCase):
    def capture(self, root, chunks=(1, 2), rate='100 MHz'):
        p = root/'capture.sr'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('metadata', '[global]\n[device 1]\nunitsize=2\ntotal probes=16\ncapturefile=logic-1\nsamplerate='+rate+'\n')
            for index in chunks:
                z.writestr('logic-1-'+str(index), bytes(range(8)))
        return p

    def test_complete(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.capture(Path(d))
            self.assertTrue(v.verify(p, 8, 100000000)['passed'])

    def test_truncated_but_valid_zip(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.capture(Path(d))
            r = v.verify(p, 12, 100000000)
            self.assertFalse(r['passed'])
            self.assertEqual(r['actual_samples'], 8)

    def test_driver_error_even_with_exact_size(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = self.capture(root)
            log = root/'capture.log'
            log.write_text('slogic-report end=error:usb-error samples=8/8\n')
            self.assertFalse(v.verify(p, 8, 100000000, log=log)['passed'])

    def test_missing_chunk(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'noncontiguous'):
                v.verify(self.capture(Path(d), (1, 3)), 8, 100000000)

    def test_rate_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(v.verify(self.capture(Path(d), rate='5 MHz'), 8, 100000000)['passed'])


if __name__ == '__main__':
    unittest.main()
