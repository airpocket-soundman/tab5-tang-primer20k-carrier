"""Tests use fake processes; no FPGA tool or device is accessed."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'build_oss.py'
spec = importlib.util.spec_from_file_location('build_oss', SCRIPT)
build_oss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_oss)


class BuildTests(unittest.TestCase):
    def run_build(self, failing=None, missing=None):
        temp = tempfile.TemporaryDirectory(prefix='dock oss test ')
        self.addCleanup(temp.cleanup)
        out = Path(temp.name)
        old = out/'old.fs'
        old.write_bytes(b'old image')
        calls = []
        def fake(command, **kwargs):
            if '--version' in command:
                return subprocess.CompletedProcess(command, 0, stdout='fake 1.0', stderr='')
            stage = 'synthesis' if '-p' in command else 'pnr' if '--write' in command else 'pack'
            calls.append((stage, command))
            if stage == failing:
                return subprocess.CompletedProcess(command, 1, stdout='failed')
            if stage == 'synthesis':
                artifact = Path(re.search(r'-json "([^"]+)"', command[2]).group(1))
            elif stage == 'pnr':
                artifact = Path(command[command.index('--write')+1])
            else:
                artifact = Path(command[command.index('-o')+1])
            if stage != missing:
                artifact.write_text('fake output', encoding='utf-8')
            return subprocess.CompletedProcess(command, 0, stdout='ok')
        with patch.object(build_oss.subprocess, 'run', side_effect=fake):
            status = build_oss.build('gfx', out/'yosys', out/'nextpnr', out/'pack', out)
        manifest = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(old.read_bytes(), b'old image')
        return status, manifest, calls, old

    def test_success_records_fresh_artifacts_and_constraints(self):
        status, m, calls, old = self.run_build()
        self.assertEqual(status, 0)
        self.assertEqual(m['status'], 'passed')
        self.assertEqual([c[0] for c in calls], ['synthesis', 'pnr', 'pack'])
        self.assertEqual([m['stages'][s]['status'] for s in ('synthesis','pnr','pack')], ['passed']*3)
        self.assertIn('synth_gowin -family gw2a -top tab5_dock_gfx_top', calls[0][1][2])
        self.assertIn('--freq', calls[1][1])
        self.assertIn('family=GW2A-18', calls[1][1])
        self.assertNotIn('--timing-allow-fail', calls[1][1])
        self.assertNotIn('--vopt=allow-unconstrained', calls[1][1])
        self.assertNotEqual(Path(m['artifacts']['pack']['path']), old)
        self.assertEqual(len(m['artifacts']['pack']['sha256']), 64)
        self.assertEqual(m['hardware_access'], 'none')
        self.assertIn('--sspi_as_gpio', calls[2][1])
        for option in ('--jtag_as_gpio','--mspi_as_gpio','--reconfign_as_gpio'):
            self.assertNotIn(option, calls[2][1])

    def test_pnr_failure_does_not_pack_or_claim_old_image(self):
        status, m, calls, _ = self.run_build(failing='pnr')
        self.assertEqual(status, 1)
        self.assertEqual([c[0] for c in calls], ['synthesis', 'pnr'])
        self.assertEqual(m['stages']['pnr']['status'], 'failed')
        self.assertEqual(m['stages']['pack']['status'], 'not_run')
        self.assertNotIn('pack', m['artifacts'])

    def test_missing_synthesis_output_fails_before_pnr(self):
        status, m, calls, _ = self.run_build(missing='synthesis')
        self.assertEqual(status, 1)
        self.assertEqual([c[0] for c in calls], ['synthesis'])
        self.assertEqual(m['stages']['synthesis']['status'], 'failed')
        self.assertEqual(m['stages']['pnr']['status'], 'not_run')

    def test_pack_failure_has_no_pack_artifact(self):
        status, m, calls, _ = self.run_build(failing='pack')
        self.assertEqual(status, 1)
        self.assertEqual(m['stages']['pack']['status'], 'failed')
        self.assertNotIn('pack', m['artifacts'])


if __name__ == '__main__':
    unittest.main()
