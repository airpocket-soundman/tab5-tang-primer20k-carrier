"""Small deterministic, clearance-screened repairs; KiCad Python."""
import math
import json
from pathlib import Path
import pcbnew

HERE=Path(__file__).resolve().parent
PCB=HERE/'kicad/tab5-fpga-carrier.kicad_pcb'
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)

def main():
    b=pcbnew.LoadBoard(str(PCB));g=b.FindNet('GND')
    fps={f.GetReference():f for f in b.GetFootprints()}
    for n in range(28,36):fps['R'+str(n)].SetValue('510R')
    tb=b.GetTitleBlock();tb.SetTitle('Tab5 Tang Primer20K lite A dual input');tb.SetRevision('lite-a-dual');tb.SetDate('2026-10-25')
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname()=='GND' and p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH:p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    for p in fps['U2'].Pads():
        if p.GetNumber()=='9':p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pads=[p for f in b.GetFootprints() for p in f.Pads()]
    def segment_clear(a,z,width=.127):
        n=max(1,math.ceil(math.dist(a,z)/.04))
        for i in range(n+1):
            q=V(a[0]+(z[0]-a[0])*i/n,a[1]+(z[1]-a[1])*i/n)
            for t in b.GetTracks():
                if t.GetNetname()!='GND' and (isinstance(t,pcbnew.PCB_VIA) or t.GetLayer()==pcbnew.F_Cu) and t.HitTest(q,mm(width/2+.127)):
                    return False
            for p in pads:
                if p.GetNetname()!='GND' and p.IsOnLayer(pcbnew.F_Cu) and p.HitTest(q,mm(width/2+.127)):
                    return False
        return True
    def via_clear(x,y,dia):
        q=V(x,y)
        if not 28.3+dia/2<x<126.7-dia/2 or not 1.3+dia/2<y<78.7-dia/2:return False
        for t in b.GetTracks():
            if t.GetNetname()!='GND' and t.HitTest(q,mm(dia/2+.127)):return False
            if isinstance(t,pcbnew.PCB_VIA) and math.dist((x,y),xy(t.GetPosition()))<.55:return False
        for p in pads:
            if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD and p.HitTest(q,mm(dia/2+.05)):return False
            if p.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH and p.HitTest(q,mm(dia/2+.25)):return False
            if p.GetNetname()!='GND' and p.HitTest(q,mm(dia/2+.127)):return False
        return True
    def track(a,z):
        t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(mm(.127));t.SetLayer(pcbnew.F_Cu);t.SetNet(g);b.Add(t)
    def getpad(ref,num):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(num))
    report=[]
    for ref,num in [('U5',3),('R4',2)]:
        origin=xy(getpad(ref,num).GetPosition())
        found=None
        candidates=[]
        for ix in range(-50,51):
            for iy in range(-50,51):
                x,y=origin[0]+ix*.05,origin[1]+iy*.05
                d=math.dist(origin,(x,y))
                if .5<=d<=2.5:candidates.append((d,x,y))
        for _,x,y in sorted(candidates):
            if via_clear(x,y,.5) and segment_clear(origin,(x,y)):
                track(origin,(x,y))
                v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(mm(.5));v.SetDrill(mm(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(g);b.Add(v)
                found=(x,y);break
        report.append({'pad':ref+'.'+str(num),'via':found,'via_diameter_mm':.5,'drill_mm':.3})
        if found is None:raise RuntimeError('No safe GND stitch for '+ref)
    # The two ESD ground pads share the middle gap, clear of the four lanes.
    a,z=xy(getpad('U5',3).GetPosition()),xy(getpad('U5',8).GetPosition())
    assert segment_clear(a,z),'U5 ground bridge obstructed'
    track(a,z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(PCB),b)
    (HERE/'kicad/sim/ground-repair.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
