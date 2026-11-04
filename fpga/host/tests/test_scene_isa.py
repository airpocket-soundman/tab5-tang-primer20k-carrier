"""5シーン(Wire/Particles/Galaxy/Fire/Flow)のISA相当プログラムがCPU整数参照と全画素一致することの確認(縮小構成)。
フル構成は fpga/reference/run_scene_isa.py --report ... 。"""
import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'fpga'))
from reference import run_scene_isa as R


class SceneIsa(unittest.TestCase):
    def test_quick_all_scenes_match_reference(self):
        with tempfile.TemporaryDirectory() as d:
            rep = Path(d) / 'r.json'
            sys.argv = ['run_scene_isa', '--quick', '--report', str(rep)]
            self.assertEqual(R.main(), 0)
            data = json.loads(rep.read_text(encoding='utf-8'))
            self.assertTrue(data['all_match'])
            self.assertTrue(all(data['micro_tests'].values()))
            self.assertIn('Unsupported', data['galaxy']['LIGHT']['base'])


if __name__ == '__main__':
    unittest.main()
