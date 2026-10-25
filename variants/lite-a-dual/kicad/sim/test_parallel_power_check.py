"""Inject faults in minimum-success bus and power circuitry."""
import sys
import unittest
from regression_common import run_case, run_suite, footprint

class ParallelPowerTests(unittest.TestCase):
    def case(self,name,ref=None,value=None,pin=None,net=None):
        def mutate(board):
            f=footprint(board,ref)
            if value is not None:f.SetValue(value)
            if pin is not None:
                p=next(p for p in f.Pads() if p.GetNumber()==str(pin))
                p.SetNet(board.FindNet(net))
        run_case(self,'check_parallel_power.py',name,ref is None,mutate if ref else None)
    def test_normal(self):self.case('normal')
    def test_clock_on_wrong_pin(self):self.case('clock-disconnected','J4',pin=52,net='GND')
    def test_switch_channel_mismatch(self):self.case('switch-channel-mismatch','U7',pin=18,net='ISO_D0')
    def test_oe_wrong_default(self):self.case('OE-pulled-low','R46',pin=1,net='GND')
    def test_monitor_threshold_wrong(self):self.case('low-Tab-threshold','U9',value='TPS3839K33DBZR')
    def test_core_five_volt_missing(self):self.case('Core-power-missing','J4',pin=4,net='GND')
    def test_wrong_header_columns(self):
        def mutate(board):
            import pcbnew
            for p in footprint(board,'J3').Pads():
                pos=p.GetPosition();p.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(110)-pos.x,pos.y))
        run_case(self,'check_parallel_power.py','M5Bus-mirrored-columns',False,mutate)
    def test_missing_ground(self):self.case('Core-ground-missing','J4',pin=2,net='+5V')
    def test_wrong_feedback(self):self.case('wrong-buck-feedback','R7',value='3.24k')
    def test_missing_feedback_trim(self):self.case('missing-trim','R49',pin=1,net='GND')
    def test_wrong_trim_resistance(self):self.case('wrong-trim-value','R50',value='68k')
    def test_unstable_ldo_substitution(self):self.case('unverified-LDO-substitution','U3',value='AMS1117-3.3')

if __name__=='__main__':run_suite(sys.modules[__name__],'regression_parallel_power.json')
