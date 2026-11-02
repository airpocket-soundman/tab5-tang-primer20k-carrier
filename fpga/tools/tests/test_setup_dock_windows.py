import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('setup',Path(__file__).resolve().parents[1]/'setup_dock_windows.py')
setup=importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)

class SetupTests(unittest.TestCase):
    def make_archive(self,path,entries):
        with tarfile.open(path,'w:gz') as tar:
            for name,data in entries:
                member=tarfile.TarInfo(name); member.size=len(data)
                tar.addfile(member,io.BytesIO(data))
    def test_verify_archive_rejects_wrong_length_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a'; path.write_bytes(b'abc')
            setup.verify_archive(path,3,hashlib.sha256(b'abc').hexdigest())
            with self.assertRaises(ValueError): setup.verify_archive(path,4,hashlib.sha256(b'abc').hexdigest())
            with self.assertRaises(ValueError): setup.verify_archive(path,3,'0'*64)
    def test_extract_loader_selects_binary_dll_and_share_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); archive=tmp/'a.tgz'; dest=tmp/'dest'
            self.make_archive(archive,[('oss-cad-suite/bin/openFPGALoader.exe',b'exe'),
                ('oss-cad-suite/bin/libusb.dll',b'dll'),('oss-cad-suite/share/openFPGALoader/a.bit.gz',b'bit'),
                ('oss-cad-suite/lib/libftdi1.dll',b'ftdi'),
                ('oss-cad-suite/bin/iverilog.exe',b'compiler'),('oss-cad-suite/bin/vvp.exe',b'runtime'),
                ('oss-cad-suite/lib/ivl/ivl.exe',b'backend'),('oss-cad-suite/lib/ivl/vvp.tgt',b'target'),
                ('oss-cad-suite/license/LICENSE.iverilog',b'license'),
                ('oss-cad-suite/bin/yosys.exe',b'unwanted')])
            loader=setup.extract_loader(archive,dest)
            self.assertEqual(loader.read_bytes(),b'exe')
            self.assertEqual((dest/'bin/libusb.dll').read_bytes(),b'dll')
            self.assertEqual((dest/'bin/libftdi1.dll').read_bytes(),b'ftdi')
            self.assertEqual((dest/'bin/iverilog.exe').read_bytes(),b'compiler')
            self.assertEqual((dest/'bin/vvp.exe').read_bytes(),b'runtime')
            self.assertEqual((dest/'lib/ivl/ivl.exe').read_bytes(),b'backend')
            self.assertEqual((dest/'lib/ivl/vvp.tgt').read_bytes(),b'target')
            self.assertEqual((dest/'license/LICENSE.iverilog').read_bytes(),b'license')
            self.assertEqual((dest/'share/openFPGALoader/a.bit.gz').read_bytes(),b'bit')
            self.assertFalse((dest/'bin/yosys.exe').exists())
            (dest/'keep').write_text('preserve')
            setup.extract_loader(archive,dest)
            self.assertEqual((dest/'keep').read_text(),'preserve')
    def test_unsafe_member_and_duplicate_rejected(self):
        for entries in [[('../outside',b'x')], [('oss-cad-suite/bin/openFPGALoader.exe',b'a'),
                                                ('oss-cad-suite/bin/OPENFPGALOADER.EXE',b'b')]]:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as tmp:
                tmp=Path(tmp); a=tmp/'a.tgz'; self.make_archive(a,entries)
                with self.assertRaises(ValueError): setup.extract_loader(a,tmp/'dest')
                self.assertFalse((tmp/'outside').exists())
    def test_verified_existing_archive_is_not_redownloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'a.tgz'; archive.write_bytes(b'abc')
            with patch.object(setup,'SIZE',3),patch.object(setup,'SHA256',hashlib.sha256(b'abc').hexdigest()),patch.object(setup.urllib.request,'urlopen') as fetch:
                setup.acquire(archive); fetch.assert_not_called()
    def test_bad_cached_archive_is_not_redownloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'a.tgz'; archive.write_bytes(b'abc')
            with patch.object(setup.urllib.request,'urlopen') as fetch:
                with self.assertRaises(ValueError): setup.acquire(archive)
                fetch.assert_not_called()

if __name__=='__main__': unittest.main()
