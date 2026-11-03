import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import generate_metadata_cdc_constraints as gen

class ExactCdcConstraints(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.proof=json.loads((gen.ROOT/'validation/filtered-batch-cdc-proof-2026-11-04/structure.json').read_text())
  for name in list(self.proof['source_sha256'])+['constraints/dock/triangle54filtered_official.sdc']:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((gen.ROOT/name).read_bytes())
  self.proofpath=self.root/'proof.json';self.output=self.root/'output.sdc'
 def invoke(self,verify=False):
  self.proofpath.write_text(json.dumps(self.proof))
  argv=['generator','--proof',str(self.proofpath),'--output',str(self.output)]+(['--verify']if verify else[])
  with patch.object(gen,'ROOT',self.root),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):gen.main()
 def test_exact30_and_both_stage1_reports(self):
  self.invoke();text=self.output.read_text();self.assertEqual(text.count('\nset_false_path '),30)
  self.assertEqual(text.count('-max_paths 30 -max_common_paths 1'),2)
  for line in text.splitlines():
   if line.startswith('set_false_path '):
    self.assertIn('/metadata_meta_',line);self.assertNotIn('metadata_bus_',line);self.assertNotIn('/CLEAR',line);self.assertNotIn('*',line)
  self.invoke(True)
 def test_count_drift_rejected(self):
  self.proof['mapped_first_stage_count']=31
  with self.assertRaises(AssertionError):self.invoke()
 def test_source_drift_rejected(self):
  name=next(iter(self.proof['source_sha256']));(self.root/name).write_text('changed')
  with self.assertRaises(AssertionError):self.invoke()
 def test_stage1_exception_rejected(self):
  self.proof['first_stage_pins'][0]['first_stage_D']=self.proof['first_stage_pins'][0]['only_Q_consumer']
  with self.assertRaises(AssertionError):self.invoke()
 def test_modified_constraint_rejected(self):
  self.invoke();self.output.write_text(self.output.read_text()+'set_false_path -to [all_clocks]\n')
  with self.assertRaises(AssertionError):self.invoke(True)

if __name__=='__main__':unittest.main()
