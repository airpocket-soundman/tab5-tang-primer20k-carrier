import json
from pathlib import Path
import unittest
from generate_fragment_vectors import OUT,golden,render,vectors
from reference.game_gpu_reference import Frame,Vertex


class FragmentGolden(unittest.TestCase):
    def test_candidate_against_frame_reference(self):
        for v in vectors():
            ax,ay,bx,by,cx,cy,za,zb,zc,old,x,y,color=v
            if x>=16 or y>=16:continue
            frame=Frame(16,16)
            frame.clear(0,old)
            points=frame.triangle(Vertex(ax,ay,za),Vertex(bx,by,zb),Vertex(cx,cy,zc),color)
            covered,deg,invalid,passed,z,ox,oy,oc=golden(v)
            with self.subTest(v=v):
                self.assertEqual(bool(covered),(x,y) in points)
                self.assertEqual(frame.depth[y*16+x],z if passed else old)
                self.assertEqual(frame.color[y*16+x],color if passed else 0)
                self.assertEqual((invalid,ox,oy,oc),(0,x,y,color))
                if deg:self.assertFalse(covered or passed)

    def test_fixture_packing_and_manifest(self):
        files=render()
        self.assertEqual(len(vectors()),436)
        for name,data in files.items():
            self.assertEqual((OUT/name).read_text(),data)
        self.assertEqual(len(files['fragment_inputs.mem'].splitlines()[0]),13*16)
        self.assertEqual(len(files['fragment_expected.mem'].splitlines()[0]),8*16)
        manifest=json.loads((OUT/'fragment_manifest.json').read_text())
        self.assertEqual(manifest['rtl_simulation'],'not_run')
        self.assertEqual(manifest['count'],len(vectors()))


if __name__=='__main__':unittest.main()
