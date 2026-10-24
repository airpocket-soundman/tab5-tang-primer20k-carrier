"""Regression checks for widths, interval coverage, role uniqueness and vias."""
import copy
import sys
import unittest
import pcbnew
from regression_common import run_case,run_suite

def track(b):
    return next(t for t in b.GetTracks() if t.GetNetname()=='HDMI_D0P' and not isinstance(t,pcbnew.PCB_VIA) and abs(pcbnew.ToMM(t.GetWidth())-.2)<.001)
def via(b):return next(t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname().startswith('HDMI_'))

class ClassificationRegression(unittest.TestCase):
    def check(self,label,expected,board=None,roles=None,key=None):
        run_case(self,'check_classification.py',label,expected,board,roles,key)
    def test_normal(self):self.check('normal',True)
    def test_width(self):self.check('trace-0.20-to-0.18',False,lambda b:track(b).SetWidth(180000),key='width_mismatches')
    def test_role_width(self):
        def change(r):r['HDMI_D0P']['main'][0][2]=.18
        self.check('role-width-drift',False,roles=change,key='width_mismatches')
    def test_duplicate(self):
        def change(r):r['HDMI_D0P']['branch'].append(copy.deepcopy(r['HDMI_D0P']['main'][0]))
        self.check('duplicate-role-interval',False,roles=change,key='overlapping_roles')
    def test_stale_full_length(self):
        def change(r):
            layer,points,width=r['HDMI_D0P']['main'][0];a,b=points[:2]
            dx,dy=b[0]-a[0],b[1]-a[1]
            r['HDMI_D0P']['branch'].append([layer,[[a[0]-dx,a[1]-dy],[b[0]+dx,b[1]+dy]],width])
        self.check('stale-midpoint-on-copper-but-ends-outside',False,roles=change,key='stale_roles')
    def test_split(self):
        def change(r):
            pts=r['HDMI_D0P']['main'][0][1];a,b=pts[:2];pts.insert(1,[(a[0]+b[0])/2,(a[1]+b[1])/2])
        self.check('split-collinear-role-shared-endpoint',True,roles=change)
    def test_missing_role(self):
        def change(r):r['HDMI_D0P']['main']=[]
        self.check('uncovered-path',False,roles=change,key='unclassified')
    def test_tiny_extra_copper(self):
        def change(b):
            source=track(b);extra=pcbnew.PCB_TRACK(b)
            extra.SetNetCode(source.GetNetCode());extra.SetLayer(source.GetLayer());extra.SetWidth(200000)
            extra.SetStart(pcbnew.VECTOR2I(1000000,1000000));extra.SetEnd(pcbnew.VECTOR2I(1001000,1000000));b.Add(extra)
        self.check('tiny-unclassified-copper',False,change,key='unclassified')
    def test_via_drill(self):self.check('via-drill-drift',False,lambda b:via(b).SetDrill(250000),key='via_errors')
    def test_via_diameter(self):self.check('via-diameter-drift',False,lambda b:via(b).SetWidth(650000),key='via_errors')
    def test_via_missing(self):self.check('via-removed',False,lambda b:b.Remove(via(b)),key='via_errors')

if __name__=='__main__':run_suite(sys.modules[__name__],'regression_classification.json')
