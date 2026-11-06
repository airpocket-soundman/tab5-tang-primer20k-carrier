"""r5l: re-do the mode / power / bus labels on the silkscreen (KiCad python).

The r5 texts ('RUN 1-2', 'PROG 2-3', 'ALL 3 / POWER OFF') described three jumpers moved together.
In r5l the mode is one slide switch (SW4) plus the separate JP3 (Tab5 power) and JP1 (bus ARM).
Only silkscreen text changes; no copper, no placement. Run: KiCad python fix_silk.py
"""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
P = K / 'tab5-fpga-carrier-r5l.kicad_pcb'
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(str(P))
OLD = {'RUN 1-2', 'PROG 2-3', 'ALL 3 / POWER OFF'}
size = None
for d in list(b.GetDrawings()):
    if d.GetClass() == 'PCB_TEXT' and d.GetLayer() == pcbnew.F_SilkS and d.GetText() in OLD:
        size = (d.GetTextSize(), d.GetTextThickness())
        b.Remove(d)
assert size, 'old silkscreen texts not found (already replaced?)'
# text, x, y (mm), height (mm), horizontal justification
NEW = [
    ('SW4 MODE', 47.6, 6.6, 1.0, 'left'),
    ('POWER OFF FIRST', 38.2, 17.2, 0.8, 'right'),
    ('JP3 TAB5 PWR', 43.0, 23.0, 1.0, 'center'),
    ('1-2 ON', 40.0, 34.2, 0.9, 'center'),
    ('2-3 OFF', 40.0, 35.7, 0.9, 'center'),
    ('SW4+JP3 SAME MODE', 45.0, 37.4, 0.9, 'center'),
    ('JP1 BUS ARM', 56.4, 70.7, 1.0, 'right'),
    ('PLUG = ON', 56.4, 72.3, 1.0, 'right'),
]
for text, x, y, h, just in NEW:
    t = pcbnew.PCB_TEXT(b)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetText(text)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h)))
    t.SetTextThickness(mm(0.15))
    t.SetHorizJustify({'left': pcbnew.GR_TEXT_H_ALIGN_LEFT, 'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                       'center': pcbnew.GR_TEXT_H_ALIGN_CENTER}[just])
    b.Add(t)
b.Save(str(P))
print('silkscreen texts replaced:', len(OLD), '->', len(NEW))
