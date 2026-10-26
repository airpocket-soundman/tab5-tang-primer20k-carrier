"""Complete local ground stitches and fabrication graphics. KiCad Python."""
from pathlib import Path
import json,math
import pcbnew
H=Path(__file__).resolve().parent;P=H/'kicad/tab5-fpga-carrier.kicad_pcb'
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
b=pcbnew.LoadBoard(str(P));fps={f.GetReference():f for f in b.GetFootprints()}
pads=[p for f in b.GetFootprints() for p in f.Pads()]
def segment_ok(a,z):
 for i in range(max(1,math.ceil(math.dist(a,z)/.04))+1):
  q=V(*(a[j]+(z[j]-a[j])*i/max(1,math.ceil(math.dist(a,z)/.04)) for j in (0,1)))
  for t in b.GetTracks():
   if t.GetNetname()!='GND' and (isinstance(t,pcbnew.PCB_VIA) or t.GetLayer()==pcbnew.F_Cu) and t.HitTest(q,mm(.0635+.127)):return False
  for p in pads:
   if p.GetNetname()!='GND' and p.IsOnLayer(pcbnew.F_Cu) and p.HitTest(q,mm(.0635+.127)):return False
 return True
def via_ok(q):
 for t in b.GetTracks():
  if isinstance(t,pcbnew.PCB_VIA) and math.dist(xy(t.GetPosition()),xy(q))<.56:return False
  if t.GetNetname()!='GND' and t.HitTest(q,mm(.25+.127)):return False
 for p in pads:
  if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD and p.HitTest(q,mm(.25+.05)):return False
  if p.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH and p.HitTest(q,mm(.25+.25)):return False
  if p.GetNetname()!='GND' and p.HitTest(q,mm(.25+.127)):return False
 return True
report=[]
for ref in ('U5','U6'):
 pad=next(p for p in fps[ref].Pads() if p.GetNumber()=='8');origin=xy(pad.GetPosition())
 candidates=sorted((math.hypot(ix,iy)*.05,origin[0]+ix*.05,origin[1]+iy*.05) for ix in range(-65,66) for iy in range(-65,66) if 10<=math.hypot(ix,iy)<=65)
 target=None
 for _,x,y in candidates:
  if via_ok(V(x,y)) and segment_ok(origin,(x,y)):
   t=pcbnew.PCB_TRACK(b);t.SetStart(pad.GetPosition());t.SetEnd(V(x,y));t.SetWidth(mm(.127));t.SetNet(b.FindNet('GND'));t.SetLayer(pcbnew.F_Cu);b.Add(t)
   v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(mm(.5));v.SetDrill(mm(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNet(b.FindNet('GND'));b.Add(v);target=(x,y);break
 report.append({'reference':ref,'gnd_via':target,'via_mm':[.5,.3]})
 if target is None:raise RuntimeError('No clearance-safe GND stitch found: '+ref)
# Keep clean assembly/fabrication graphics without suppressing any DRC rule.
for f in b.GetFootprints():
 for obj in [f.Reference(),f.Value()]+list(f.GraphicalItems()):
  if obj.GetLayer() in (pcbnew.F_SilkS,pcbnew.B_SilkS):obj.SetLayer(pcbnew.B_Fab if obj.GetLayer()==pcbnew.B_SilkS else pcbnew.F_Fab)
for obj in b.GetDrawings():
 if obj.GetLayer() in (pcbnew.F_SilkS,pcbnew.B_SilkS):obj.SetLayer(pcbnew.B_Fab if obj.GetLayer()==pcbnew.B_SilkS else pcbnew.F_Fab)
pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
(H/'kicad/sim/ground-finish.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
