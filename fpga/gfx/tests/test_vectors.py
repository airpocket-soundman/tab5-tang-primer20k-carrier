import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('game_rtl_vectors',Path(__file__).with_name('generate_vectors.py'))
gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
from reference.game_gpu_reference import Frame,Vertex

class CoverageGoldenTests(unittest.TestCase):
    def test_fixtures_and_width_invariants(self):
        for name,data in gen.render_files().items():
            self.assertEqual((Path(__file__).parent/name).read_text(),data)
        for inp,out in gen.vectors():
            covered,deg,swap,area,wa,wb,wc=out
            self.assertTrue(all(-(1<<63)<=v<(1<<63) for v in (area,wa,wb,wc)))
            self.assertGreaterEqual(area,0)
            self.assertEqual(wa+wb+wc,area)
            if covered:
                self.assertTrue(all(v>=0 for v in (wa,wb,wc)))
                self.assertFalse(deg)
            vertices=tuple(Vertex(inp[i],inp[i+1],0) for i in (0,2,4))
            reverse=gen.coverage((vertices[0],vertices[2],vertices[1]),*inp[6:])
            self.assertEqual(reverse[0:2],out[0:2])
            self.assertEqual(reverse[3:],(area,wa,wc,wb))

    def test_pixel_coverage_matches_existing_frame_reference(self):
        # Directly compare with Frame.triangle traversal/scissor implementation.
        tris=[(Vertex(0,0,1),Vertex(128,0,3),Vertex(0,128,8)),
              (Vertex(128,0,1),Vertex(128,128,3),Vertex(0,128,8)),
              (Vertex(-8,-8,1),Vertex(136,8,3),Vertex(8,136,8)),
              (Vertex(-32768,-32768,1),Vertex(32767,-32768,3),Vertex(-32768,32767,8))]
        for tri in tris:
            for vertices in (tri,(tri[0],tri[2],tri[1])):
                frame=Frame(8,8);covered=frame.triangle(*vertices,1)
                for y in range(8):
                    for x in range(8):
                        out=gen.coverage(vertices,x,y)
                        self.assertEqual(out[0],(x,y) in covered)
                        if out[0]:
                            self.assertEqual(frame.depth[y*8+x],sum(w*v.z for w,v in zip(out[4:],vertices))//out[3])

    def test_shared_edge_ownership(self):
        a=(Vertex(0,0,1),Vertex(128,0,1),Vertex(0,128,1))
        b=(Vertex(128,0,1),Vertex(128,128,1),Vertex(0,128,1))
        for y in range(8):
            for x in range(8):
                self.assertEqual(int(gen.coverage(a,x,y)[0])+int(gen.coverage(b,x,y)[0]),1)

if __name__=='__main__': unittest.main()
