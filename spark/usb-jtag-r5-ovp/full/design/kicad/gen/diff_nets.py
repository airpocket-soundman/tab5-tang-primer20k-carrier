"""Compare every pre-existing track/via/pad of the r5 source with the r5c output (net names).
Run with KiCad python. Prints only differences."""
import pcbnew, sys
from pathlib import Path
K = Path(__file__).resolve().parents[1]
SRC = K.parents[3] / 'usb-jtag-r5/full/design/kicad/tab5-fpga-carrier-r5.kicad_pcb'
OUT = K / sys.argv[1] if len(sys.argv) > 1 else K / 'tab5-fpga-carrier-r5c.kicad_pcb'
mm = pcbnew.ToMM
def items(path):
    b = pcbnew.LoadBoard(str(path))
    d = {}
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            key = ('via', round(mm(t.GetX()), 3), round(mm(t.GetY()), 3))
        else:
            key = ('trk', t.GetLayer(), round(mm(t.GetStart().x), 3), round(mm(t.GetStart().y), 3),
                   round(mm(t.GetEnd().x), 3), round(mm(t.GetEnd().y), 3))
        d[key] = t.GetNetname()
    pads = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            pads[(f.GetReference(), p.GetNumber(), round(mm(p.GetX()), 3), round(mm(p.GetY()), 3))] = p.GetNetname()
    return d, pads
a, ap = items(SRC)
c, cp = items(OUT)
print('source items', len(a), 'output items', len(c))
chg = [(k, a[k], c.get(k)) for k in a if c.get(k) != a[k]]
print('tracks/vias removed or re-netted:', len(chg))
for k, x, y in chg: print('  ', k, x, '->', y)
pchg = [(k, ap[k], cp.get(k)) for k in ap if cp.get(k) != ap[k]]
print('pads re-netted:', len(pchg))
for k, x, y in pchg: print('  ', k, x, '->', y)
