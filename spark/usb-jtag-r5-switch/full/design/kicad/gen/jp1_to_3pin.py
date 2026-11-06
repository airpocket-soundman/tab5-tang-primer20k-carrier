"""r5s: replace JP1 (1x2 header) by a 1x3 header with an unconnected pin 3 (KiCad python).

Pads 1 and 2 keep their position (58.9, 71.5) / (58.9, 74.04) and their nets, so the existing
copper is untouched; the new pad 3 sits at (58.9, 76.58) and is not connected.
Also updates the JP1 silkscreen text. Run once on the r5s board.
"""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
P = K / 'tab5-fpga-carrier-r5s.kicad_pcb'
FP = 'C:/Program Files/KiCad/10.0/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty'
IO = pcbnew.PCB_IO_KICAD_SEXPR()
b = pcbnew.LoadBoard(str(P))
old = next(f for f in b.GetFootprints() if f.GetReference() == 'JP1')
assert len(list(old.Pads())) == 2, 'JP1 is already 3-pin'
pos, rot = old.GetPosition(), old.GetOrientationDegrees()
nets = {p.GetNumber(): p.GetNetname() for p in old.Pads()}
print('old JP1 at', pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), 'rot', rot, 'nets', nets)
b.Remove(old)
new = IO.FootprintLoad(FP, 'PinHeader_1x03_P2.54mm_Vertical')
new.SetFPID(pcbnew.LIB_ID('Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical'))
new.SetReference('JP1')
new.SetValue('BUS ARM')
new.SetPosition(pos)
new.SetOrientationDegrees(rot)
for p in new.Pads():
    n = nets.get(p.GetNumber())
    if n:
        p.SetNet(b.FindNet(n))
# same text style as the other headers: reference on F.Fab (visible), value on F.Fab (hidden)
new.Reference().SetLayer(pcbnew.F_Fab)
new.Value().SetLayer(pcbnew.F_Fab)
new.Value().SetVisible(False)
b.Add(new)
# silkscreen: replace 'JP1 BUS ARM' / 'PLUG = ON' by a 3-line label (right of nothing: left of the header)
for d in list(b.GetDrawings()):
    if d.GetClass() == 'PCB_TEXT' and d.GetLayer() == pcbnew.F_SilkS and d.GetText() in ('JP1 BUS ARM', 'PLUG = ON'):
        b.Remove(d)
for text, x, y in (('JP1 BUS ARM', 56.4, 70.0), ('1-2 ON', 56.4, 71.7), ('2-3 OFF', 56.4, 73.4)):
    t = pcbnew.PCB_TEXT(b)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetText(text)
    t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
    t.SetTextThickness(pcbnew.FromMM(0.15))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    b.Add(t)
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(P))
print('JP1 is now 1x3 (pin3 unconnected)')
