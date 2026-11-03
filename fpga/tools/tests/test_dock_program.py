import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('dock_program', Path(__file__).resolve().parents[1]/'dock_program.py')
dock = importlib.util.module_from_spec(spec); spec.loader.exec_module(dock)

class ProgramTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'source.v'; self.source.write_text('rtl')
        self.image = self.root/'output.fs'; self.image.write_bytes(b'image')
        self.manifest = self.root/'build/dock-oss-gfx/manifest.json'; self.manifest.parent.mkdir(parents=True)
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.data = {'status':'passed','variant':'gfx','sources':{str(self.source):sha(self.source)},
                     'stages':{name:{'status':'passed'} for name in ('synthesis','pnr','pack')},
                     'artifacts':{'pack':{'path':str(self.image),'sha256':sha(self.image)}}}
        self.write_manifest()
        self.loader = str(self.root/'loader.exe')
        Path(self.loader).write_bytes(b'fake executable')
        self.args = ['--loader',self.loader,'program','--variant','gfx']
    def write_manifest(self): self.manifest.write_text(json.dumps(self.data), encoding='utf8')
    def record(self):
        logs=list((self.root/'build/programming').glob('*.json'))
        self.assertEqual(len(logs),1)
        return json.loads(logs[0].read_text(encoding='utf8'))
    def test_dry_run_no_loader(self):
        invoke=Mock(); self.assertEqual(dock.run(self.args+['--dry-run'],self.root,invoke),0)
        invoke.assert_not_called(); r=self.record()
        self.assertEqual(r['status'],'dry_run')
        self.assertEqual(r['commands'][0]['argv'],[self.loader,'-b','tangprimer20k','-m',str(self.image)])
    def test_program_command_and_result(self):
        invoke=Mock(return_value=Mock(returncode=0,stdout='ok',stderr=''))
        self.assertEqual(dock.run(self.args,self.root,invoke),0)
        invoke.assert_called_once_with([self.loader,'-b','tangprimer20k','-m',str(self.image)],capture_output=True,text=True,encoding='utf-8',errors='replace',check=False,timeout=120)
        self.assertEqual(self.record()['status'],'passed')
        self.assertEqual(self.record()['loader_sha256'], hashlib.sha256(b'fake executable').hexdigest())
    def test_tampering_blocks_before_loader(self):
        self.source.write_text('changed'); invoke=Mock()
        self.assertEqual(dock.run(self.args,self.root,invoke),1)
        invoke.assert_not_called(); self.assertIn('source hash mismatch',self.record()['error'])
    def test_image_tampering_blocks_before_loader(self):
        self.image.write_bytes(b'changed'); invoke=Mock()
        self.assertEqual(dock.run(self.args,self.root,invoke),1)
        invoke.assert_not_called(); self.assertIn('image hash mismatch',self.record()['error'])
    def test_failed_build_and_loader_are_recorded(self):
        self.data['stages']['pack']['status']='failed'; self.write_manifest(); invoke=Mock()
        self.assertEqual(dock.run(self.args,self.root,invoke),1); invoke.assert_not_called()
        self.assertEqual(self.record()['status'],'failed')
    def test_detect_board_only_and_error_status(self):
        invoke=Mock(return_value=Mock(returncode=4,stdout='',stderr='error'))
        self.assertEqual(dock.run(['--loader',self.loader,'detect'],self.root,invoke),4)
        self.assertEqual(invoke.call_args.args[0],[self.loader,'-b','tangprimer20k','--detect'])
        self.assertEqual(self.record()['status'],'failed')
    def test_doctor_queries_only(self):
        invoke=Mock(return_value=Mock(returncode=0,stdout='',stderr=''))
        self.assertEqual(dock.run(['--loader',self.loader,'doctor'],self.root,invoke),0)
        self.assertEqual([c.args[0][1] for c in invoke.call_args_list],['--version','--help','--list-boards'])
    def test_serial_selection(self):
        invoke=Mock(return_value=Mock(returncode=0,stdout='',stderr=''))
        self.assertEqual(dock.run(self.args+['--serial','FT123'],self.root,invoke),0)
        self.assertEqual(invoke.call_args.args[0],[self.loader,'-b','tangprimer20k','--usb-serial-num','FT123','-m',str(self.image)])
    def test_timeout_records_partial_output(self):
        invoke=Mock(side_effect=subprocess.TimeoutExpired('loader',120,output=b'partial\xff',stderr=b'error'))
        self.assertEqual(dock.run(self.args,self.root,invoke),1)
        record=self.record()
        self.assertEqual(record['status'],'failed')
        self.assertEqual(record['commands'][0]['result'],'timeout')
        self.assertEqual(record['commands'][0]['stdout'],'partial\ufffd')
