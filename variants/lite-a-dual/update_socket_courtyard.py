"""Adopt the shared drawing-derived U-shaped socket courtyard, preserving copper."""
from pathlib import Path
import pcbnew
HERE=Path(__file__).resolve().parent
NAME='DDR3_XDAP_4042044_20401'
LIB=HERE/'kicad/lib/carrier.pretty'
PCB=HERE/'kicad/tab5-fpga-carrier.kicad_pcb'
b=pcbnew.LoadBoard(str(PCB));old=next(f for f in b.GetFootprints() if f.GetReference()=='J4')
new=pcbnew.FootprintLoad(str(LIB),NAME)
new.SetPosition(old.GetPosition());new.SetOrientation(old.GetOrientation());new.SetReference('J4');new.SetValue(old.GetValue());new.SetUuid(old.m_Uuid);new.SetPath(old.GetPath());new.SetFPID(old.GetFPID())
new.Reference().SetVisible(old.Reference().IsVisible());new.Value().SetVisible(old.Value().IsVisible())
new.Reference().SetLayer(old.Reference().GetLayer());new.Value().SetLayer(old.Value().GetLayer())
oldpads={}
for p in old.Pads():oldpads.setdefault(p.GetNumber(),[]).append(p)
for p in new.Pads():
    if p.GetNumber() in oldpads:
        q=min(oldpads[p.GetNumber()],key=lambda q:(p.GetPosition()-q.GetPosition()).EuclideanNorm())
        if q.GetNetname():p.SetNet(b.FindNet(q.GetNetname()))
        assert (p.GetPosition()-q.GetPosition()).EuclideanNorm()<1000,('pad position changed',p.GetNumber())
b.RemoveNative(old);b.Add(new)
pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(PCB),b)
print('Socket courtyard updated; existing electrical pad positions preserved')
