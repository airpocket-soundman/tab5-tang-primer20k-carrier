"""Local full-size PCBA changes; preserves unrelated routing. KiCad Python."""
from pathlib import Path
import json,sys,math
import pcbnew
H=Path(__file__).resolve().parent;K=H/'kicad';sys.path.insert(0,str(K/'gen'))
import route_pcb as rt
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)

def button():
 f=pcbnew.FOOTPRINT(None);f.SetFPID(pcbnew.LIB_ID('carrier','SW_XKB_TS1102S_C480272'))
 f.SetLibDescription('XKB TS-1102S-B-D-B/C480272; manufacturer PCB mounting lands12x5.9, inner6.8x3.1; H5.5mm; verify pin grouping in assembly preview')
 f.SetAttributes(pcbnew.FP_SMD)
 for layer,x,y in [(pcbnew.F_Fab,3,3),(pcbnew.F_CrtYd,6.25,3.25)]:
  s=pcbnew.PCB_SHAPE(f);s.SetShape(pcbnew.SHAPE_T_RECT);s.SetStart(V(-x,-y));s.SetEnd(V(x,y));s.SetLayer(layer);s.SetWidth(mm(.05));f.Add(s)
 # Top-view physical1/2 are the upper pair,3/4 the lower pair.
 # Circuit diagram1/2 is one contact and3/4 the other contact.
 for y,n in [(-2.25,'1'),(2.25,'2')]:
  for x in (-4.7,4.7):
   p=pcbnew.PAD(f);p.SetNumber(n);p.SetPosition(V(x,y));p.SetSize(V(2.6,1.4));p.SetShape(pcbnew.PAD_SHAPE_RECT);p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
   ls=pcbnew.LSET();[ls.AddLayer(l) for l in (pcbnew.F_Cu,pcbnew.F_Mask,pcbnew.F_Paste)];p.SetLayerSet(ls);f.Add(p)
 f.Reference().SetVisible(False);f.Value().SetVisible(False);return f

def main():
 PCB=K/'tab5-fpga-carrier.kicad_pcb';b=pcbnew.LoadBoard(str(PCB));fps={f.GetReference():f for f in b.GetFootprints()}
 pcbnew.FootprintSave(str(K/'lib/carrier.pretty'),button())
 reroute={'F_BTN0','TAB_RST','BUCK_EN','HDMI_5V'}
 for t in list(b.GetTracks()):
  if t.GetNetname() in reroute:b.RemoveNative(t)
 for ref,pos in [('SW1',(14,11)),('SW2',(29,11))]:
  old=fps[ref];nets={p.GetNumber():p.GetNet() for p in old.Pads()};f=button();f.SetReference(ref);f.SetValue('TS-1102S-B-D-B');f.SetPosition(V(*pos));f.SetOrientationDegrees(0)
  f.SetPath(old.GetPath());f.SetUuid(old.m_Uuid)
  for p in f.Pads():p.SetNet(nets[p.GetNumber()])
  b.RemoveNative(old);b.Add(f);fps[ref]=f
 fps['SW3'].SetPosition(V(45.5,15))
 def wire(net,pts,w=.127):
  for a,z in zip(pts,pts[1:]):
   if any(not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.F_Cu and t.GetNetname()==net and {xy(t.GetStart()),xy(t.GetEnd())}=={a,z} for t in b.GetTracks()):continue
   t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(mm(w));t.SetLayer(pcbnew.F_Cu);t.SetNet(b.FindNet(net));b.Add(t)
 def pp(ref,n):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(n))
 for ref in ('U4','U5','U6'):
  # These line pairs are externally connected, independent of internal ESD silicon.
  for a,z in [('1','10'),('2','9'),('4','7'),('5','6'),('3','8')]:
   pa,pz=pp(ref,a),pp(ref,z)
   assert pa.GetNetname()==pz.GetNetname()
   if ref=='U6' or a=='3':wire(pa.GetNetname(),[xy(pa.GetPosition()),xy(pz.GetPosition())],.2)
 # Redundant ground stitches violating drill spacing; planes retain both areas.
 for t in list(b.GetTracks()):
  if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()=='GND' and any(math.dist(xy(t.GetPosition()),q)<.001 for q in [(72.7,63.5),(10.1,22.4)]):b.RemoveNative(t)
 rt.GRID=.1;r=rt.Router(b,2,1,127,79);r.load((2,1,127,79));r.max_exp=1000000
 layers={pcbnew.F_Cu:0,pcbnew.In2_Cu:1,pcbnew.B_Cu:2}
 for t in b.GetTracks():
  n=r.nid(t.GetNetname())
  if isinstance(t,pcbnew.PCB_VIA):
   for l in range(3):r.stamp_disc(l,*xy(t.GetPosition()),n,pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+rt.CLR+rt.TW/2)
  elif t.GetLayer() in layers:r.stamp_path(layers[t.GetLayer()],[xy(t.GetStart()),xy(t.GetEnd())],n,pcbnew.ToMM(t.GetWidth()))
 r.base=[o.copy() for o in r.occ]
 r.add_escape_stubs({'J5.18':(2.6,lambda x,y:-1)})
 failed=[]
 for net in ['HDMI_5V','F_BTN0','TAB_RST','BUCK_EN']:
  ok=r.route_net(net,.127 if net=='HDMI_5V' else .25,20.)
  print(net,ok,flush=True)
  if not ok:failed.append(net)
 # Commit only new local routes and vias.
 for name,l,pts,w in r.perm+r.tracks:
  for a,z in zip(pts,pts[1:]):
   t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetNet(b.FindNet(name));t.SetLayer([pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu][l]);t.SetWidth(mm(w));b.Add(t)
 for name,x,y in r.vias:
  v=pcbnew.PCB_VIA(b);v.SetPosition(V(x,y));v.SetWidth(mm(.6));v.SetDrill(mm(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNet(b.FindNet(name));b.Add(v)
 tb=b.GetTitleBlock();tb.SetTitle('Tab5 FPGA Workstation Spark engineering candidate');tb.SetRevision('spark-full-pcba-draft');tb.SetDate('2026-10-26')
 for f in b.GetFootprints():
  for p in f.Pads():
   if p.GetNetname()=='GND' and p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH:p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
 pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(PCB),b)
 (K/'sim/pcba-local-route.json').write_text(json.dumps({'failed':failed,'button_lcsc':'C480272','button_land_mm':{'pad':[2.6,1.4],'centres_x':[-4.7,4.7],'centres_y':[-2.25,2.25]},'HDMI_5V_min_route_width_mm':.127,'HDMI_5V_rating':'Must re-evaluate; not a500mA guarantee'},indent=2)+'\n')
 if failed:raise SystemExit(1)
if __name__=='__main__':main()
