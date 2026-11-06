"""r5l PCB step: replace JP2 and JP4 by the DP3T slide switch SW4 on a COPY of the r5 board.

Source (read only): spark/usb-jtag-r5/.../tab5-fpga-carrier-r5.kicad_pcb  (current r5, never modified)
Output            : spark/usb-jtag-r5-loadsw/.../tab5-fpga-carrier-r5l.kicad_pcb
Run with KiCad's python:  "C:/Program Files/KiCad/10.0/bin/python.exe" add_sw.py
Placement (found by a clearance scan, see README): SW4 vertical (rot 90) at (43.2, 11.0), the only
free area on the whole board; all other r5 copper is untouched except the stubs of JP2/JP4.
"""
import pcbnew, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from maze import Router
K=Path(__file__).resolve().parents[1]
SRC=K.parents[3]/'usb-jtag-r5/full/design/kicad/tab5-fpga-carrier-r5.kicad_pcb'
P=K/'tab5-fpga-carrier-r5l.kicad_pcb'
LIB=K/'lib/carrier.pretty'
FPNAME='SW_SLIDE_DP3T_SS-23D03-G080'
CX,CY,ROT=43.2,11.0,90
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
def pad(ref,num):
    f=next(f for f in b.GetFootprints() if f.GetReference()==ref)
    p=next(p for p in f.Pads() if p.GetNumber()==str(num))
    return (pcbnew.ToMM(p.GetX()),pcbnew.ToMM(p.GetY()))

# 1. remove JP2 and JP4 (their pads were junctions of F/B/In2 copper, so keep that copper joined with vias)
# BUCK_5V: dangling 0.25 stub that only reached JP2 pad1
rm=0
for t in list(b.GetTracks()):
    if t.GetClass()=='PCB_VIA' or t.GetLayer()!=F or t.GetNetname()!='BUCK_5V':continue
    s,e=t.GetStart(),t.GetEnd()
    pts={(round(pcbnew.ToMM(s.x),2),round(pcbnew.ToMM(s.y),2)),(round(pcbnew.ToMM(e.x),2),round(pcbnew.ToMM(e.y),2))}
    if pts=={(39.0,26.0),(38.15,26.85)}:b.Remove(t);rm+=1
assert rm==1,rm
JPS=[next(f for f in b.GetFootprints() if f.GetReference()==r) for r in ('JP2','JP4')]
for _f in JPS: b.Remove(_f)
# +5V (F.Cu stub + B.Cu), PD_CFG1 (F.Cu + B.Cu), PD_VDD (B.Cu + In2): old pad was the layer change
add_via(39.0,28.54,'+5V'); add_via(47.0,28.54,'PD_CFG1'); add_via(47.0,31.08,'PD_VDD')

# 2. SW4
f=IO.FootprintLoad(str(LIB),FPNAME)
f.SetFPID(pcbnew.LIB_ID('carrier',FPNAME))
f.SetReference('SW4');f.SetValue('SS-23D03-G080')
f.SetPosition(V(CX,CY));f.SetOrientationDegrees(ROT)
NETS={'1':'BUCK_5V','3':'VBUS_PD','4':'+5V','5':'PD_CFG1','6':'PD_VDD','8':'GND','9':'GND','10':'GND'}
for p in f.Pads():
    nn=NETS.get(p.GetNumber())
    if nn:p.SetNet(net(nn))
b.Add(f)
f.Reference().SetLayer(pcbnew.F_SilkS)
f.Reference().SetPosition(V(48.6,10.0)); f.Reference().SetVisible(True)
f.Value().SetLayer(pcbnew.F_Fab)

def label(text,x,y):
    t=pcbnew.PCB_TEXT(b);t.SetText(text);t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(V(x,y));t.SetTextSize(pcbnew.VECTOR2I(mm(0.8),mm(0.8)));t.SetTextThickness(mm(0.12));b.Add(t)
# slider positions: pads 1/8 (RUN) are at local x=-4 -> board y=CY+4 for rot 90; pads 3/6 (PGM) at CY
label('RUN',CX-5.0,CY+4.0);label('OFF',CX-5.0,CY+2.0);label('PGM',CX-5.0,CY)

# 3. routing
R=Router(b,(36.0,2.0,50.5,34.0),[F,I2,B],res=0.1,clr=0.2)
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
def Tp(num,layer=None):
    x,y=pad('SW4',num);return (x,y,layer)
exec(Path(__file__).with_name('sw_routes.py').read_text())
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(P))
print('saved',P.name,'unrouted:',failed)
