"""r5l: silkscreen check on the real board data (KiCad python). Read-only.

Lists every text on F.Silkscreen / B.Silkscreen with height, stroke width, ratio and orientation,
and flags values below the usual JLCPCB legibility limits (height >= 1.0 mm, stroke >= 0.15 mm,
height : stroke >= 6 : 1). Also reports silk text whose box overlaps another silk text box.
"""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
b = pcbnew.LoadBoard(str(K / 'tab5-fpga-carrier-r5l.kicad_pcb'))
mm = pcbnew.ToMM
items = []
for d in b.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        items.append(('board', d))
for f in b.GetFootprints():
    for t in list(f.GraphicalItems()):
        if t.GetClass() == 'PCB_TEXT' and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            items.append((f.GetReference(), t))
    for t in (f.Reference(), f.Value()):
        if t.IsVisible() and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            items.append((f.GetReference() + ':field', t))
print('silk texts:', len(items))
bad = []
boxes = []
for src, t in items:
    h = mm(t.GetTextSize().y)
    w = mm(t.GetTextThickness())
    bb = t.GetBoundingBox()
    box = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
    rot = t.GetTextAngleDegrees()
    ratio = h / w if w else 0
    flag = []
    if h < 1.0 - 1e-6: flag.append('height<1.0')
    if w < 0.15 - 1e-6: flag.append('stroke<0.15')
    if ratio < 6 - 1e-6: flag.append('ratio<6:1')
    if t.IsMirrored() and t.GetLayer() == pcbnew.F_SilkS: flag.append('mirrored on top')
    print('%-10s %-22r h=%.2f w=%.2f ratio=%.1f rot=%g box=(%.1f,%.1f)-(%.1f,%.1f) %s' % (src, t.GetText(), h, w, ratio, rot, *box, ' '.join(flag)))
    if flag: bad.append((src, t.GetText(), flag))
    boxes.append((src, t.GetText(), box))
ov = []
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a, c = boxes[i][2], boxes[j][2]
        if a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]:
            ov.append((boxes[i][:2], boxes[j][:2]))
print('below limits:', len(bad))
for x in bad: print('  ', x)
print('overlapping text boxes:', len(ov))
for x in ov: print('  ', x)
