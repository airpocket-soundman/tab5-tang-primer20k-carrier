"""Print tracks/vias of the given nets in the r5l board (KiCad python)."""
import pcbnew, sys
from pathlib import Path
K = Path(__file__).resolve().parents[1]
b = pcbnew.LoadBoard(str(K / 'tab5-fpga-carrier-r5l.kicad_pcb'))
mm = lambda v: round(pcbnew.ToMM(v), 3)
want = set(sys.argv[1:])
for t in b.GetTracks():
    if t.GetNetname() in want:
        if t.GetClass() == 'PCB_VIA':
            print('VIA', t.GetNetname(), mm(t.GetX()), mm(t.GetY()))
        else:
            print(b.GetLayerName(t.GetLayer()), t.GetNetname(), (mm(t.GetStart().x), mm(t.GetStart().y)), '->', (mm(t.GetEnd().x), mm(t.GetEnd().y)), 'w', mm(t.GetWidth()))
