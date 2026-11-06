"""List the text items on the silkscreen layers of the r5l PCB (KiCad python)."""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
b = pcbnew.LoadBoard(str(K / 'tab5-fpga-carrier-r5l.kicad_pcb'))
mm = lambda v: round(pcbnew.ToMM(v), 1)
for d in b.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        print('BOARD-TEXT', b.GetLayerName(d.GetLayer()), (mm(d.GetPosition().x), mm(d.GetPosition().y)), repr(d.GetText()))
for f in b.GetFootprints():
    if f.GetReference() in ('JP1', 'JP3', 'SW4', 'J1', 'J2', 'J3'):
        for t in (f.Reference(), f.Value()):
            print('FP', f.GetReference(), 'field', b.GetLayerName(t.GetLayer()), 'visible' if t.IsVisible() else 'hidden', repr(t.GetText()))
