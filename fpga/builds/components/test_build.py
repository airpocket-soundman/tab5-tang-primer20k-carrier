import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

spec=importlib.util.spec_from_file_location('component_build',Path(__file__).with_name('build.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'npu/rtl').mkdir(parents=True)
        (self.root/'npu/rtl/test.v').write_text('module test; endmodule')
        self.yosys=self.root/'yosys';self.yosys.write_text('tool')
    def report(self): return json.loads((self.root/'build/component-mac/manifest.json').read_text())
    def test_nonzero_is_failure(self):
        runner=Mock(return_value=Mock(returncode=3,stdout='bad',stderr='error'))
        self.assertEqual(b.build('mac',self.yosys,self.root,runner),1)
        r=self.report();self.assertEqual(r['status'],'failed');self.assertEqual(r['exit_code'],3)
        self.assertIn('bad',Path(r['log']).read_text())
    def test_success_without_artifact_fails_and_new_run(self):
        runner=Mock(return_value=Mock(returncode=0,stdout='',stderr=''))
        self.assertEqual(b.build('mac',self.yosys,self.root,runner),1)
        first=self.report();self.assertEqual(first['status'],'failed')
        self.assertEqual(b.build('mac',self.yosys,self.root,runner),1)
        self.assertNotEqual(first['run_dir'],self.report()['run_dir'])
    def test_success_counts_and_records_artifact(self):
        def run(cmd,**kwargs):
            report=self.report();path=Path(report['run_dir'])/'synth.json'
            path.write_text(json.dumps({'modules':{'int8_mac_lane':{'cells':{'a':{'type':'LUT4'},'b':{'type':'LUT4'}}}}}))
            return Mock(returncode=0,stdout='ok',stderr='')
        self.assertEqual(b.build('mac',self.yosys,self.root,run),0)
        r=self.report();self.assertEqual(r['resources'],{'LUT4':2})
        self.assertEqual(r['artifact']['sha256'],b.sha(Path(r['artifact']['path'])))
        self.assertIn('-noiopads',r['command'][-1])
