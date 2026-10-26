"""Check the physical short D1 bias branches and local ground returns (KiCad Python).

CHECK_PCB and CHECK_JSON allow isolated mutation tests, as for the other checks.
"""
import json
import math
import os
from pathlib import Path
import pcbnew

HERE = Path(__file__).resolve().parent


def check(board):
    checks = []
    for ref, net in [('R30','HDMI_D1P_C'), ('R31','HDMI_D1N_C')]:
        fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        pads = {p.GetNumber(): p for p in fp.Pads()}
        signal, ground = pads['1'], pads['2']
        vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)
                and t.GetNetname() == 'GND' and t.TopLayer() == pcbnew.F_Cu
                and t.BottomLayer() == pcbnew.B_Cu]
        local_ground = False
        for v in vias:
            distance = pcbnew.ToMM((v.GetPosition()-ground.GetPosition()).EuclideanNorm())
            if not .6 <= distance <= .8:  # outside paste land, short return
                continue
            for t in board.GetTracks():
                if isinstance(t,pcbnew.PCB_VIA) or t.GetNetname() != 'GND' or t.GetLayer() != pcbnew.F_Cu:
                    continue
                ends = [t.GetStart(),t.GetEnd()]
                if any(pcbnew.ToMM((a-ground.GetPosition()).EuclideanNorm())<.01 and
                       pcbnew.ToMM((b-v.GetPosition()).EuclideanNorm())<.01 for a,b in [ends,ends[::-1]]):
                    local_ground = True
        tracks = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)
                  and t.GetNetname() == net]
        # A short same-layer route must leave the signal pad and meet another
        # copper centre line on that net, rather than terminate in free space.
        short_tap = False
        branch_mm = None
        for t in tracks:
            if t.GetLayer() != pcbnew.F_Cu or pcbnew.ToMM(t.GetLength()) > .7:
                continue
            ends = [t.GetStart(),t.GetEnd()]
            for a,b in [ends,ends[::-1]]:
                if pcbnew.ToMM((a-signal.GetPosition()).EuclideanNorm()) > .01:
                    continue
                for other in tracks:
                    if other == t or other.GetLayer() != pcbnew.F_Cu:
                        continue
                    x,y = pcbnew.ToMM(b.x),pcbnew.ToMM(b.y)
                    c,d = other.GetStart(),other.GetEnd()
                    cx,cy,dx,dy = map(pcbnew.ToMM,[c.x,c.y,d.x,d.y])
                    ll = (dx-cx)**2+(dy-cy)**2
                    u = max(0,min(1,((x-cx)*(dx-cx)+(y-cy)*(dy-cy))/ll)) if ll else 0
                    if math.hypot(x-cx-u*(dx-cx), y-cy-u*(dy-cy)) < .003:
                        short_tap = True
                        branch_mm = pcbnew.ToMM(t.GetLength())
        checks.append(dict(ref=ref, footprint=str(fp.GetFPID().GetLibItemName()),
                           footprint_ok=str(fp.GetFPID().GetLibItemName()) == 'R_0402_1005Metric',
                           signal_net_ok=signal.GetNetname() == net, ground_net_ok=ground.GetNetname() == 'GND',
                           short_tap=short_tap, branch_mm=branch_mm, local_ground_via=local_ground))
    ok = all(all(c[k] for k in ['footprint_ok','signal_net_ok','ground_net_ok','short_tap','local_ground_via']) for c in checks)
    return dict(ok=ok,checks=checks)


if __name__ == '__main__':
    board = pcbnew.LoadBoard(os.environ.get('CHECK_PCB',str(HERE.parent/'tab5-fpga-carrier.kicad_pcb')))
    result = check(board)
    Path(os.environ.get('CHECK_JSON',str(HERE/'d1_bias_check.json'))).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0 if result['ok'] else 1)
