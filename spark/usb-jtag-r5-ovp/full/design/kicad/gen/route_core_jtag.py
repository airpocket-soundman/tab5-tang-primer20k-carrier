"""Connect JTAG directly to the official Core goldfinger, no cable connector."""
from pathlib import Path
import json
import pcbnew
import design,route_pcb as rt
K=Path(__file__).resolve().parents[1];P=K/(design.PROJECT+'.kicad_pcb')
JTAG={'143':'JTAG_TMS','147':'JTAG_TDO','149':'JTAG_TCK','153':'JTAG_TDI'}
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
def V(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def main():
    b=pcbnew.LoadBoard(str(P));fps={f.GetReference():f for f in b.GetFootprints()}
    if 'J9' in fps:b.RemoveNative(fps['J9'])
    for p in fps['J4'].Pads():
        if p.GetNumber() in JTAG:p.SetNet(b.FindNet(JTAG[p.GetNumber()]))
    for t in list(b.GetTracks()):
        if t.GetNetname() in JTAG.values():b.RemoveNative(t)
    rt.GRID=.05
    r=rt.Router(b,*design.BOARD);r.load(design.BOARD)
    layers={pcbnew.F_Cu:0,pcbnew.In2_Cu:1,pcbnew.B_Cu:2}
    for t in b.GetTracks():
        n=r.nid(t.GetNetname())
        if isinstance(t,pcbnew.PCB_VIA):
            for l in range(3):r.stamp_disc(l,*xy(t.GetPosition()),n,pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+rt.CLR+rt.TW/2)
        elif t.GetLayer() in layers:r.stamp_path(layers[t.GetLayer()],[xy(t.GetStart()),xy(t.GetEnd())],n,pcbnew.ToMM(t.GetWidth()))
    r.base=[o.copy() for o in r.occ];result={}
    for name in JTAG.values():
        r.max_exp=800000;result[name]=r.route_net(name,.127,12);print(name,result[name],flush=True)
    for name,l,pts,w in r.tracks:
        for a,z in zip(pts,pts[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetLayer([pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu][l]);t.SetWidth(pcbnew.FromMM(w));t.SetNet(b.FindNet(name));b.Add(t)
    for name,x,y in r.vias:
        t=pcbnew.PCB_VIA(b);t.SetPosition(V(x,y));t.SetWidth(pcbnew.FromMM(.6));t.SetDrill(pcbnew.FromMM(.3));t.SetViaType(pcbnew.VIATYPE_THROUGH);t.SetNet(b.FindNet(name));b.Add(t)
    b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
    (K/'sim/core-jtag-route.json').write_text(json.dumps({'source':'SOM-3961 schematicp1','pins':JTAG,'route_completed':result,'external_cable_required':False},indent=2)+'\n')
if __name__=='__main__':main()
