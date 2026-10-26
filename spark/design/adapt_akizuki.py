"""Apply drawing-based Akizuki-only manual parts to the isolated Spark PCB.

Run with KiCad Python. Preserves communication/power routes except BUCK_EN.
KSD22 logical pad numbers are local KiCad convention: 1/4 and 2/3 poles.
"""
from pathlib import Path
import sys,json,hashlib
import pcbnew
H=Path(__file__).resolve().parent;K=H/'kicad'
sys.path.insert(0,str(K/'gen'))
import design
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))
def rect(f,a,z,layer):
 s=pcbnew.PCB_SHAPE(f);s.SetShape(pcbnew.SHAPE_T_RECT);s.SetStart(V(*a));s.SetEnd(V(*z));s.SetLayer(layer);s.SetWidth(mm(.05));f.Add(s)
def ksd22():
 f=pcbnew.FOOTPRINT(None);f.SetFPID(pcbnew.LIB_ID('carrier','SW_OTAX_KSD22_Akizuki108922'))
 f.SetAttributes(pcbnew.FP_THROUGH_HOLE)
 f.SetLibDescription('OTAX KSD22; KSDxx drawing page3: 7.6mm rows,2.54mm pitch,0.8mm holes,7.0x7.5mm body. Local logical poles1-4/2-3; second unused.')
 rect(f,(.05,-4.77),(7.55,2.23),pcbnew.F_Fab)
 rect(f,(-.9,-5.27),(8.5,2.73),pcbnew.F_CrtYd)
 for n,x,y in [('1',0,0),('4',7.6,0),('2',0,-2.54),('3',7.6,-2.54)]:
  p=pcbnew.PAD(f);p.SetNumber(n);p.SetPosition(V(x,y));p.SetSize(V(1.5,1.5));p.SetDrillSize(V(.8,.8));p.SetShape(pcbnew.PAD_SHAPE_RECT if n=='1' else pcbnew.PAD_SHAPE_CIRCLE);p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
  layers=pcbnew.LSET.AllCuMask();layers.AddLayer(pcbnew.F_Mask);layers.AddLayer(pcbnew.B_Mask);p.SetLayerSet(layers);f.Add(p)
 return f
def barrel():
 f=pcbnew.FootprintLoad('C:/Program Files/KiCad/10.0/share/kicad/footprints/Connector_BarrelJack.pretty','BarrelJack_Horizontal')
 f.SetFPID(pcbnew.LIB_ID('carrier','BarrelJack_MJ179PH_Akizuki106568'))
 f.SetLibDescription('Marushin MJ-179PH drawing: center-positive pad1 rear; pad2 shell; pad3 switched shell; reference mounting slots1x3.5mm, sideY4.9mm, front-relativeX7.7/10.75/13.7mm.')
 for p in f.Pads():
  if p.GetNumber()=='3':p.SetPosition(V(-2.95,4.9));p.SetSize(V(4.1,3.5));p.SetDrillSize(V(3.5,1))
  else:p.SetSize(V(3.5,4.1));p.SetDrillSize(V(1,3.5))
 # Generic 3D body is not a verified MJ-179PH model.
 f.Models().clear()
 for item in f.GraphicalItems():
  if item.GetLayer()==pcbnew.F_SilkS:item.SetLayer(pcbnew.F_Fab)
 return f
def routed(b):
 return sorted((t.GetClass(),t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,pcbnew.PCB_VIA) else 0) for t in b.GetTracks())
P=K/'tab5-fpga-carrier.kicad_pcb';b=pcbnew.LoadBoard(str(P));before=routed(b)
fps={f.GetReference():f for f in b.GetFootprints()};cs={c.ref:c for c in design.build()}
for ref,constructor in [('J1',barrel),('SW3',ksd22)]:
 old=fps[ref];f=constructor();pcbnew.FootprintSave(str(K/'lib/carrier.pretty'),f)
 f.SetReference(ref);f.SetValue(cs[ref].value);f.SetPath(old.GetPath());f.SetUuid(old.m_Uuid)
 f.SetPosition(old.GetPosition());f.SetOrientation(old.GetOrientation())
 for p in f.Pads():
  net=(cs[ref].pads or cs[ref].pins).get(p.GetNumber(),'')
  if net:p.SetNet(b.FindNet(net))
 f.Reference().SetLayer(pcbnew.F_Fab);f.Value().SetLayer(pcbnew.F_Fab)
 f.Reference().SetVisible(False);f.Value().SetVisible(False)
 b.RemoveNative(old);b.Add(f)
# Detour the low-speed BUCK_EN control around the unused second pole.
for t in list(b.GetTracks()):
 if t.GetNetname()=='BUCK_EN' and not isinstance(t,pcbnew.PCB_VIA) and {tuple((t.GetStart().x,t.GetStart().y)),tuple((t.GetEnd().x,t.GetEnd().y))}=={(mm(45.1),mm(21.1)),(mm(45.1),mm(15.4))}:
  width=t.GetWidth();b.RemoveNative(t)
  points=[(45.1,21.1),(44.2,20.2),(44.2,16.3),(45.1,15.4)]
  for a,z in zip(points,points[1:]):
   n=pcbnew.PCB_TRACK(b);n.SetStart(V(*a));n.SetEnd(V(*z));n.SetWidth(width);n.SetLayer(pcbnew.B_Cu);n.SetNet(b.FindNet('BUCK_EN'));b.Add(n)
unchanged=lambda rows:[r for r in rows if r[1]!='BUCK_EN']
assert unchanged(before)==unchanged(routed(b)),'Unexpected non-BUCK_EN track change'
pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
report={'pcb_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'non_BUCK_EN_tracks_and_vias_unchanged':unchanged(before)==unchanged(routed(b)),'track_and_via_count':len(routed(b)),'changes':['J1 manufacturer slot geometry and grounded pad3 location','SW3 KSD22 footprint; primary BUCK_EN pad1 unchanged, GND pad4; unused pole2/3 unconnected','BUCK_EN low-speed B.Cu detour around unused pole'],'limits':['No physical mating test yet','Ground zone fill changed; prior SI geometry remains identical, no new hardware validation implied']}
(K/'sim/akizuki-adaptation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
