"""Execute with KiCad Python; rotation/flip cases test geometry, not copper routing."""
import sys
import unittest
import pcbnew
from regression_common import run_case,run_suite,footprint,pad

class ESDRegression(unittest.TestCase):
    def check(self,label,expected,mutation=None):
        run_case(self,'check_esd_footprint.py',label,expected,mutation,error_key=None if expected else 'failed')
    def test_normal(self):self.check('normal',True)
    def test_rotated(self):
        self.check('rotated90',True,lambda b: footprint(b).SetOrientationDegrees(90))
    def test_flipped(self):
        self.check('back-side-mirror',True,lambda b: footprint(b).Flip(footprint(b).GetPosition(),False))
    def test_rotated_flipped(self):
        def change(b):
            f=footprint(b);f.SetOrientationDegrees(270);f.Flip(f.GetPosition(),True)
        self.check('rotated270-mirror',True,change)
    def test_land_shrunk(self):
        self.check('ground-pad-0.1mm',False,lambda b:pad(b).SetSize(pcbnew.VECTOR2I(100000,100000)))
    def test_position(self):
        def change(b):
            p=pad(b);p.SetFPRelativePosition(pcbnew.VECTOR2I(-365000,0))
        self.check('pad-position-drift',False,change)
    def test_part_missing(self):self.check('missing-U4',False,lambda b:footprint(b).SetReference('U6'))
    def test_pad_missing(self):
        def change(b):
            f=footprint(b);p=pad(b);f.Remove(p)
        self.check('missing-pad3',False,change)
    def test_duplicate_number(self):self.check('duplicate-pad-number',False,lambda b:pad(b,'2').SetNumber('1'))
    def test_mask(self):self.check('pad-mask-override',False,lambda b:pad(b).SetLocalSolderMaskMargin(10000))
    def test_footprint_paste(self):self.check('footprint-paste-override',False,lambda b:footprint(b).SetLocalSolderPasteMargin(10000))
    def test_layers(self):self.check('pad-layer-drift',False,lambda b:pad(b).SetLayerSet(pcbnew.LSET.AllCuMask()))
    def test_pad_angle(self):self.check('pad-angle-drift',False,lambda b:pad(b).SetOrientationDegrees(10))

if __name__=='__main__':run_suite(sys.modules[__name__],'regression_esd.json')
