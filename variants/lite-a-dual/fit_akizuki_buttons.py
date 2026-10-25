"""Install TS-06104 per manufacturer drawing p8; run with KiCad Python.

Drawing PCB layout: 10.0/6.4mm outside/inside in X,
5.5/3.5mm outside/inside in Y. Pads 1=A/B, pads 2=C/D.
This is a local replacement, not regeneration of the qualified routing.
"""
from pathlib import Path
import pcbnew

HERE=Path(__file__).resolve().parent
LIB=HERE/'kicad/lib/carrier.pretty'
PCB=HERE/'kicad/tab5-fpga-carrier.kicad_pcb'
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))

def footprint():
    f=pcbnew.FOOTPRINT(None)
    f.SetFPID(pcbnew.LIB_ID('carrier','SW_TS_06104_HandSolder'))
    f.SetLibDescription('TS-06104 H4.3mm; Akizuki115969; maker drawing20201207005 p8')
    f.SetAttributes(pcbnew.FP_SMD)
    for layer,half_x,half_y in [(pcbnew.F_Fab,3.05,3.05),(pcbnew.F_CrtYd,5.25,3.4)]:
        s=pcbnew.PCB_SHAPE(f);s.SetShape(pcbnew.SHAPE_T_RECT);s.SetStart(V(-half_x,-half_y));s.SetEnd(V(half_x,half_y));s.SetLayer(layer);s.SetWidth(mm(.05));f.Add(s)
    for n,x in [('1',-4.1),('2',4.1)]:
        for y in [-2.25,2.25]:
            p=pcbnew.PAD(f);p.SetNumber(n);p.SetAttribute(pcbnew.PAD_ATTRIB_SMD);p.SetShape(pcbnew.PAD_SHAPE_RECT);p.SetPosition(V(x,y));p.SetSize(V(1.8,1));ls=pcbnew.LSET();ls.AddLayer(pcbnew.F_Cu);ls.AddLayer(pcbnew.F_Mask);ls.AddLayer(pcbnew.F_Paste);p.SetLayerSet(ls);f.Add(p)
    f.Reference().SetPosition(V(0,0));f.Reference().SetTextSize(V(.8,.8));f.Reference().SetTextThickness(mm(.12))
    f.Value().SetVisible(False)
    return f

def main():
    LIB.mkdir(exist_ok=True)
    pcbnew.FootprintSave(str(LIB),footprint())
    b=pcbnew.LoadBoard(str(PCB))
    for ref,cx in [('SW1',59.9),('SW2',70.5)]:
        old=next(f for f in b.GetFootprints() if f.GetReference()==ref)
        assert old.GetOrientationDegrees()==0
        if str(old.GetFPID().GetLibItemName())=='SW_TS_06104_HandSolder':continue
        nets={p.GetNumber():p.GetNet() for p in old.Pads()}
        signal=nets['1']
        for t in list(b.GetTracks()):
            if isinstance(t,pcbnew.PCB_VIA) or t.GetLayer()!=pcbnew.F_Cu or t.GetNetCode()!=signal.GetNetCode():continue
            if max(t.GetStart().y,t.GetEnd().y)<=mm(6.01) and min(t.GetStart().x,t.GetEnd().x)>mm(58):b.Remove(t)
        f=footprint();f.SetReference(ref);f.SetValue('TS-06104');f.SetPosition(V(cx,6.5))
        for p in f.Pads():p.SetNet(nets[p.GetNumber()])
        points=([(65.099999,6.),(55.8,6.),(55.8,4.25),(55.8,8.75)] if ref=='SW1' else [(68.4,6.),(66.4,6.),(66.4,4.25),(66.4,8.75)])
        for a,z in zip(points,points[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(mm(.25));t.SetLayer(pcbnew.F_Cu);t.SetNet(signal);b.Add(t)
        b.Remove(old);b.Add(f)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(str(PCB),b)

if __name__=='__main__':main()

