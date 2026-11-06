"""r5c PCB step: add the VBUS over-voltage cut-off to a COPY of the r5 board.

Source (read only): spark/usb-jtag-r5/.../tab5-fpga-carrier-r5.kicad_pcb  (current r5, never modified)
Output            : spark/usb-jtag-r5-ovp/.../tab5-fpga-carrier-r5c.kicad_pcb
Run with KiCad's python:  "C:/Program Files/KiCad/10.0/bin/python.exe" add_ovp.py
"""
import pcbnew, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from maze import Router
K=Path(__file__).resolve().parents[1]
SRC=K.parents[3]/'usb-jtag-r5/full/design/kicad/tab5-fpga-carrier-r5.kicad_pcb'
P=K/'tab5-fpga-carrier-r5c.kicad_pcb'
FP='C:/Program Files/KiCad/10.0/share/kicad/footprints/'
mm=pcbnew.FromMM
def V(x,y): return pcbnew.VECTOR2I(mm(x),mm(y))
IO=pcbnew.PCB_IO_KICAD_SEXPR()
b=pcbnew.LoadBoard(str(SRC))
F,I2,B=pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu
def net(name):
    ni=b.FindNet(name)
    if ni is None:
        ni=pcbnew.NETINFO_ITEM(b,name);b.Add(ni);ni=b.FindNet(name)
    return ni
def add_track(layer,pts,netname,w):
    n=net(netname)
    for a,c in zip(pts,pts[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*c));t.SetLayer(layer);t.SetWidth(mm(w));t.SetNet(n);b.Add(t)
def add_via(x,y,netname,dia=0.6,drill=0.3):
    v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(dia));v.SetDrill(mm(drill));v.SetNet(net(netname));b.Add(v)
def place(ref,lib,name,value,x,y,rot,pads):
    f=IO.FootprintLoad(FP+lib+'.pretty',name)
    f.SetFPID(pcbnew.LIB_ID(lib,name))      # 'Lib:Name' so the schematic/PCB parity check matches
    f.SetReference(ref);f.SetValue(value);f.SetPosition(V(x,y));f.SetOrientationDegrees(rot)
    for p in f.Pads():
        nn=pads.get(p.GetNumber())
        if nn:p.SetNet(net(nn))
    b.Add(f);return f
def pad(ref,num):
    f=next(f for f in b.GetFootprints() if f.GetReference()==ref)
    p=next(p for p in f.Pads() if p.GetNumber()==str(num))
    return (pcbnew.ToMM(p.GetX()),pcbnew.ToMM(p.GetY()))

# 1. JP2 pad3 leaves VBUS_PD (becomes VBUS_PGM); delete the two In2 segments that used the pad as a junction
jp2=next(f for f in b.GetFootprints() if f.GetReference()=='JP2')
for p in jp2.Pads():
    if p.GetNumber()=='3':p.SetNet(net('VBUS_PGM'))
removed=0
for t in list(b.GetTracks()):
    if t.GetClass()=='PCB_VIA' or t.GetLayer()!=I2 or t.GetNetname()!='VBUS_PD':continue
    s,e=t.GetStart(),t.GetEnd()
    pts={(round(pcbnew.ToMM(s.x),2),round(pcbnew.ToMM(s.y),2)),(round(pcbnew.ToMM(e.x),2),round(pcbnew.ToMM(e.y),2))}
    if (39.0,31.08) in pts:b.Remove(t);removed+=1
assert removed==2,removed

# 2. parts (layout in ovp_layout.py)
exec(Path(__file__).with_name('ovp_layout.py').read_text())

# 3. routing
R=Router(b,(33.0,11.0,50.5,35.5),[F,I2,B],res=0.1,clr=0.2)
failed=[]
def do(netname,w,terms,allowed=None):
    r=R.route(netname,w,terms,allowed)
    if r is None:
        failed.append(netname);print('UNROUTED',netname);return
    tracks,vias=r
    for layer,pts,ww in tracks:
        add_track(layer,pts,netname,ww);R.add_track(layer,pts,netname,ww)
    for x,y in vias:
        add_via(x,y,netname);R.add_via(x,y,netname)
    print('routed',netname,len(tracks),'tracks',len(vias),'vias')
def Tp(ref,num,layer=F):
    x,y=pad(ref,num);return (x,y,layer)
exec(Path(__file__).with_name('ovp_routes.py').read_text())
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(P))
print('saved',P.name,'unrouted:',failed)
