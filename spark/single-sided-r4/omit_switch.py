from pathlib import Path
import sys,json,subprocess
import pcbnew
H=Path(__file__).resolve().parent;v=sys.argv[1];K=H/v/'design/kicad';P=K/'tab5-fpga-carrier.kicad_pcb';sys.path.insert(0,str(K/'gen'))
import design,route_pcb as rt
b=pcbnew.LoadBoard(str(P));sw=next(f for f in b.GetFootprints() if f.GetReference()=='SW3');old=[p.GetBoundingBox() for p in sw.Pads()]
for t in list(b.GetTracks()):
 if t.GetNetname()=='BUCK_EN' or (t.GetNetname()=='GND' and any(q.Contains(t.GetStart()) or q.Contains(t.GetEnd()) for q in old)):b.RemoveNative(t)
b.RemoveNative(sw)
x0,y0,x1,y1=design.BOARD;r=rt.Router(b,x0,y0,x1,y1);r.load(design.BOARD);layers={pcbnew.F_Cu:0,pcbnew.In2_Cu:1,pcbnew.B_Cu:2}
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
def V(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
for t in b.GetTracks():
 n=r.nid(t.GetNetname())
 if isinstance(t,pcbnew.PCB_VIA):
  for l in range(3):r.stamp_disc(l,*xy(t.GetPosition()),n,pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+rt.CLR+rt.TW/2)
 elif t.GetLayer() in layers:r.stamp_path(layers[t.GetLayer()],[xy(t.GetStart()),xy(t.GetEnd())],n,pcbnew.ToMM(t.GetWidth()))
r.base=[o.copy() for o in r.occ];assert r.route_net('BUCK_EN',.2,30)
for name,l,pts,w in r.tracks:
 for a,z in zip(pts,pts[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(pcbnew.FromMM(w));t.SetLayer([pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu][l]);t.SetNet(b.FindNet(name));b.Add(t)
for name,x,y in r.vias:
 t=pcbnew.PCB_VIA(b);t.SetPosition(V(x,y));t.SetWidth(pcbnew.FromMM(.6));t.SetDrill(pcbnew.FromMM(.3));t.SetViaType(pcbnew.VIATYPE_THROUGH);t.SetNet(b.FindNet(name));b.Add(t)
b.GetTitleBlock().SetRevision('single-sided-no-switch-r4');b.GetTitleBlock().SetDate('2026-10-26')
for iteration in range(25):
 pcbnew.SaveBoard(str(P),b);b=pcbnew.LoadBoard(str(P));b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
 out=K/'sim/drc-final.json';subprocess.run([str(Path(sys.executable).parent/'kicad-cli.exe'),'pcb','drc','--severity-all','--format','json','-o',str(out),str(P)],check=True,capture_output=True)
 d=json.loads(out.read_text());dangling={i['uuid'] for e in d['violations'] if e['type'] in ('track_dangling','via_dangling') for i in e['items']}
 if not dangling:break
 for t in list(b.GetTracks()):
  if t.m_Uuid.AsString() in dangling:b.RemoveNative(t)
assert not d['violations'] and not d['unconnected_items'],d
bottom=[f.GetReference() for f in b.GetFootprints() if f.IsFlipped() and any(p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD for p in f.Pads()) and not f.IsDNP()]
assert not bottom,bottom
(K/'sim/single-sided-check.json').write_text(json.dumps({'revision':'r4-no-switch','drc_violations':0,'unconnected':0,'bottom_populated_smt':bottom,'manual_THT':['J3'],'switch_removed':True},indent=2)+'\n')
print(v,'PASS: DRC0, unconnected0, bottom SMT0')
