"""r5s: bring all silkscreen text up to the JLCPCB legibility limits (KiCad python).

Limits used: height >= 1.0 mm, stroke >= 0.15 mm, height:stroke >= 6:1. Only silkscreen text changes
(size, stroke, a few positions / wording); no copper, no placement. Idempotent.
"""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
P = K / 'tab5-fpga-carrier-r5s.kicad_pcb'
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(str(P))
H, W = mm(1.0), mm(0.15)
# (old text) -> (new text, new x, new y, justification)
RESET = {
    'PGM': ('PGM', 38.2, 11.0, 'right'),
    'OFF': ('OFF', 38.2, 13.0, 'right'),
    'RUN': ('RUN', 38.2, 15.0, 'right'),
    'POWER OFF FIRST': ('POWER OFF!', 38.2, 17.4, 'right'),     # the long form ran into the R1 pad at x=25
    'POWER OFF!': ('POWER OFF!', 38.2, 17.4, 'right'),
    '1-2 ON': None, '2-3 OFF': None,            # JP3 pair handled below (JP1 has its own pair at x>45)
    'SW4+JP3 SAME MODE': ('SET SAME AS SW4', 45.0, 37.8, 'center'),
    'SET SAME AS SW4': ('SET SAME AS SW4', 45.0, 37.8, 'center'),
}
J = {'left': pcbnew.GR_TEXT_H_ALIGN_LEFT, 'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT, 'center': pcbnew.GR_TEXT_H_ALIGN_CENTER}
n = 0
for d in b.GetDrawings():
    if d.GetClass() != 'PCB_TEXT' or d.GetLayer() != pcbnew.F_SilkS:
        continue
    t = d.GetText()
    x, y = pcbnew.ToMM(d.GetPosition().x), pcbnew.ToMM(d.GetPosition().y)
    d.SetTextSize(pcbnew.VECTOR2I(H, H))
    d.SetTextThickness(W)
    if t in ('1-2 ON', '2-3 OFF') and x < 45:            # JP3 pair: two lines, 1.7 mm apart
        d.SetPosition(pcbnew.VECTOR2I(mm(40.0), mm(33.6 if t == '1-2 ON' else 35.3)))
    elif t in RESET and RESET[t]:
        txt, nx, ny, just = RESET[t]
        d.SetText(txt)
        d.SetPosition(pcbnew.VECTOR2I(mm(nx), mm(ny)))
        d.SetHorizJustify(J[just])
    n += 1
for f in b.GetFootprints():
    if f.GetReference() == 'SW4':
        r = f.Reference()
        r.SetTextThickness(mm(0.2))
b.Save(str(P))
print('silkscreen texts normalised:', n)
