"""A missing branch or local ground return must fail the D1 physical check."""
import sys
import unittest
import pcbnew
from regression_common import run_case, run_suite, footprint


class D1BiasTests(unittest.TestCase):
    def test_normal(self):
        run_case(self,'check_d1_bias.py','normal',True)

    def test_missing_branch(self):
        def mutate(board):
            pad = next(p for p in footprint(board,'R30').Pads() if p.GetNumber() == '1')
            track = next(t for t in board.GetTracks() if not isinstance(t,pcbnew.PCB_VIA)
                         and t.GetNetname() == pad.GetNetname() and t.GetLength()<pcbnew.FromMM(.7)
                         and (t.GetStart()-pad.GetPosition()).EuclideanNorm()<pcbnew.FromMM(.01))
            board.RemoveNative(track)
        run_case(self,'check_d1_bias.py','branch-removed',False,mutate)

    def test_missing_ground_via(self):
        def mutate(board):
            pad = next(p for p in footprint(board,'R31').Pads() if p.GetNumber() == '2')
            via = next(t for t in board.GetTracks() if isinstance(t,pcbnew.PCB_VIA)
                       and (t.GetPosition()-pad.GetPosition()).EuclideanNorm()<pcbnew.FromMM(.8))
            board.RemoveNative(via)
        run_case(self,'check_d1_bias.py','local-ground-via-removed',False,mutate)

    def test_wrong_ground_net(self):
        def mutate(board):
            pad = next(p for p in footprint(board,'R31').Pads() if p.GetNumber() == '2')
            pad.SetNet(board.FindNet('+3V3'))
        run_case(self,'check_d1_bias.py','wrong-resistor-return',False,mutate)


if __name__ == '__main__':
    run_suite(sys.modules[__name__],'regression_d1_bias.json')
