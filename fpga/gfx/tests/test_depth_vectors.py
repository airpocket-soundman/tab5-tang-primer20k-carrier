import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('depth_vectors',Path(__file__).with_name('generate_depth_vectors.py'))
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class DepthTests(unittest.TestCase):
    def test_fixed_width_restoring_equals_exact_integer_floor(self):
        for v in g.vectors():
            invalid,passed,z=g.golden(v)
            if invalid or not v[-1]:continue
            area,wa,wb,wc,za,zb,zc,old,_=v
            n=wa*za+wb*zb+wc*zc
            self.assertLess(n,1<<49)
            q,r=g.restoring(n,area)
            self.assertEqual(q,z)
            self.assertEqual(n,q*area+r)
            self.assertTrue(0<=r<area)
            self.assertEqual(passed,q>old)
            self.assertTrue(0<=q<=65535)
    def test_strict_depth_equal_and_fraction_floor(self):
        self.assertEqual(g.golden((3,1,1,1,0,0,5,1,1)),(False,False,1))
        self.assertEqual(g.golden((3,1,1,1,0,0,5,0,1)),(False,True,1))
        self.assertEqual(g.golden((3,1,1,1,0,0,5,0,0)),(False,False,0))
    def test_coverage_weights_feed_existing_frame_depth(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from reference.game_gpu_reference import Frame,Vertex
        cspec=importlib.util.spec_from_file_location('coverage_vectors',Path(__file__).with_name('generate_vectors.py'))
        cov=importlib.util.module_from_spec(cspec);cspec.loader.exec_module(cov)
        tri=(Vertex(0,0,0),Vertex(128,0,65535),Vertex(0,128,3))
        for vertices in (tri,(tri[0],tri[2],tri[1])):
            frame=Frame(8,8);frame.triangle(*vertices,1)
            for y in range(8):
                for x in range(8):
                    covered,deg,swap,area,wa,wb,wc=cov.coverage(vertices,x,y)
                    if not covered:continue
                    z=frame.depth[y*8+x]
                    for old in (0,z,min(65535,z+1)):
                        inp=(area,wa,wb,wc,*(v.z for v in vertices),old,1)
                        self.assertEqual(g.golden(inp),(False,z>old,z))

    def test_invalid_shape_and_fixtures(self):
        for v in g.vectors()[-18:]:self.assertEqual(g.golden(v),(True,False,0))
        for name,data in g.render().items():self.assertEqual((Path(__file__).parent/name).read_text(),data)
if __name__=='__main__':unittest.main()
