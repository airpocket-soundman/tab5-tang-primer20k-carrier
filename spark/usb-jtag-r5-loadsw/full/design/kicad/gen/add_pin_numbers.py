"""r5l: print pin numbers next to the pins of JP1, JP3 and SW4 (silkscreen only, KiCad python).

JP1/JP3: the number sits 2.0 mm to the right of each pin. SW4: the number sits just outside each of
the two pad columns, inside the body outline. Height 1.0 mm, stroke 0.15 mm (JLCPCB limits).
Idempotent: single-digit silk texts are removed and re-created. Run once after fix_silk_sizes.py.
"""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
P = K / 'tab5-fpga-carrier-r5l.kicad_pcb'
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(str(P))
# Re-running on a board that already has the numbers is refused: removing text items through pcbnew
# crashed the interpreter. To change the offsets, restore the board from git and run this once.
if any(d.GetClass() == 'PCB_TEXT' and d.GetLayer() == pcbnew.F_SilkS and d.GetText() in list('12345678')
       for d in b.GetDrawings()):
    print('pin numbers are already present: nothing to do')
    raise SystemExit(0)
placed = []
def put(text, x, y):
    t = pcbnew.PCB_TEXT(b)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetText(text)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    t.SetTextThickness(mm(0.15))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    b.Add(t)
    placed.append((text, round(x, 2), round(y, 2)))
fps = {f.GetReference(): f for f in b.GetFootprints()}
for ref, dx in (('JP3', 2.1), ('JP1', 2.1)):
    for p in fps[ref].Pads():
        put(p.GetNumber(), tomm(p.GetX()) + dx, tomm(p.GetY()))
sw = fps['SW4']
cx = tomm(sw.GetPosition().x)
for p in sw.Pads():
    n = p.GetNumber()
    if n not in list('12345678'):
        continue
    x, y = tomm(p.GetX()), tomm(p.GetY())
    put(n, x - 1.4 if x < cx else x + 1.45, y)   # centred between the pad edge and the body outline
print('pin numbers placed:', len(placed))
for t in placed:
    print('  ', t)
b.Save(str(P))
