"""LCSC-first A-type99x78 revision; KiCad Python, local controls only."""
from pathlib import Path
import json,sys,math
import pcbnew
H=Path(__file__).resolve().parent;K=H/'kicad';sys.path.insert(0,str(K/'gen'))
p=K/'gen/design.py';s=p.read_text(encoding='utf8');s=s.split('# LCSC LITE A REVISION')[0]
selected={
 'J1':('DC-005-5A-2.0','C381116','carrier:BarrelJack_XKB_C381116','LCSC/JLC wave-solder candidate; stabilized12V center positive; XKB drawing A1; actual plug fit pending.'),
 'J3':('2.54-2*15P','C56496',None,'Bottom2x15 male; LCSC/JLC wave-solder candidate;6mm mating,3mm tails,2.54mm insulator. Preserve mirrored pinout; physical fit pending.'),
 'JP1':('B-2100S02P-A110','C124375',None,'LCSC/JLC wave-solder candidate;C5305 shunt supplied separately, initially absent.'),
 'SW3':('DS-02BLP','C692500','carrier:SW_XKB_DS02BLP_C692500','LCSC/JLC wave-solder candidate; first physical pole only; localCAD1-4, supplier diagram1-3. Both OFF initially=FPGA runs.'),
 'SW1':('TS-1187A-B-A-B','C318884','carrier:SW_XKB_TS1187A_C318884','LCSC/JLC SMT;H1.5mm; custom footprint90deg relative to datasheet: A/B common contacts on CAD left numbered1, C/D on right numbered2. Manufacturer rotation preview required.'),
 'SW2':('TS-1187A-B-A-B','C318884','carrier:SW_XKB_TS1187A_C318884','LCSC/JLC SMT;H1.5mm; custom footprint90deg relative to datasheet: A/B common contacts on CAD left numbered1, C/D on right numbered2. Manufacturer rotation preview required.')}
s+='\n# LCSC LITE A REVISION\n_build_before_lcsc=build\ndef build():\n    cs=_build_before_lcsc()\n    selected='+repr(selected)+'\n    for c in cs:\n        if c.ref in selected:\n            c.value,c.lcsc,fp,c.comment=selected[c.ref]\n            if fp:c.fp=fp\n        if c.ref=="SW3":\n            c.sym="Switch:SW_DIP_x02"\n            c.pins={"1":"BUCK_EN","4":"GND","2":None,"3":None};c.pads=None\n    return cs\n'
p.write_text(s,encoding='utf8')
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))
def rect(f,a,z,layer):
 t=pcbnew.PCB_SHAPE(f);t.SetShape(pcbnew.SHAPE_T_RECT);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetLayer(layer);t.SetWidth(mm(.05));f.Add(t)
def button():
 f=pcbnew.FOOTPRINT(None);f.SetFPID(pcbnew.LIB_ID('carrier','SW_XKB_TS1187A_C318884'));f.SetAttributes(pcbnew.FP_SMD)
 f.SetLibDescription('XKB C318884 H1.5; recommended lands7.0/5.0 by4.5/3.0 rotated90deg. CAD1 left=A/B common, CAD2 right=C/D common; vendor assembly orientation must be checked.')
 rect(f,(-2.55,-2.55),(2.55,2.55),pcbnew.F_Fab);rect(f,(-2.8,-3.75),(2.8,3.75),pcbnew.F_CrtYd)
 for n,x in [('1',-1.875),('2',1.875)]:
  for y in [-3,3]:
   p=pcbnew.PAD(f);p.SetNumber(n);p.SetAttribute(pcbnew.PAD_ATTRIB_SMD);p.SetShape(pcbnew.PAD_SHAPE_RECT);p.SetPosition(V(x,y));p.SetSize(V(.75,1));ls=pcbnew.LSET();[ls.AddLayer(l) for l in [pcbnew.F_Cu,pcbnew.F_Mask,pcbnew.F_Paste]];p.SetLayerSet(ls);f.Add(p)
 return f
def stop():
 f=pcbnew.FOOTPRINT(None);f.SetFPID(pcbnew.LIB_ID('carrier','SW_XKB_DS02BLP_C692500'));f.SetAttributes(pcbnew.FP_THROUGH_HOLE)
 f.SetLibDescription('XKB C692500 A2;7.62x2.54 pitch,1mm drill. CAD poles1-4/2-3 correspond supplier1-3/2-4, same physical columns.')
 rect(f,(-1.14,-4.57),(8.76,2.03),pcbnew.F_Fab);rect(f,(-1.64,-5.07),(9.26,2.53),pcbnew.F_CrtYd)
 for n,x,y in [('1',0,0),('4',7.62,0),('2',0,-2.54),('3',7.62,-2.54)]:
  p=pcbnew.PAD(f);p.SetNumber(n);p.SetAttribute(pcbnew.PAD_ATTRIB_PTH);p.SetShape(pcbnew.PAD_SHAPE_RECT if n=='1' else pcbnew.PAD_SHAPE_CIRCLE);p.SetPosition(V(x,y));p.SetSize(V(1.7,1.7));p.SetDrillSize(V(1,1));ls=pcbnew.LSET.AllCuMask();ls.AddLayer(pcbnew.F_Mask);ls.AddLayer(pcbnew.B_Mask);p.SetLayerSet(ls);f.Add(p)
 return f
P=K/'tab5-fpga-carrier.kicad_pcb';b=pcbnew.LoadBoard(str(P));fps={f.GetReference():f for f in b.GetFootprints()}
before=[(t.GetNetname(),str(t.GetStart()),str(t.GetEnd())) for t in b.GetTracks() if t.GetNetname() not in ['TAB_RST','F_BTN0']]
for ref,(value,code,fp,comment) in selected.items():
 old=fps[ref]
 if ref in ['SW1','SW2','SW3']:
  f=button() if ref!='SW3' else stop();pcbnew.FootprintSave(str(K/'lib/carrier.pretty'),f)
  f.SetReference(ref);f.SetValue(value);f.SetPath(old.GetPath());f.SetUuid(old.m_Uuid);f.SetPosition(old.GetPosition());f.SetOrientation(old.GetOrientation())
  for pad in f.Pads():
   net=('BUCK_EN' if pad.GetNumber()=='1' else 'GND' if pad.GetNumber()=='4' else '') if ref=='SW3' else ('F_BTN0' if ref=='SW1' else 'TAB_RST') if pad.GetNumber()=='1' else 'GND'
   if net:pad.SetNet(b.FindNet(net))
  if ref!='SW3':
   cx,cy=pcbnew.ToMM(old.GetPosition().x),pcbnew.ToMM(old.GetPosition().y);net=b.FindNet('F_BTN0' if ref=='SW1' else 'TAB_RST')
   for sign in [-1,1]:
    t=pcbnew.PCB_TRACK(b);t.SetStart(V(cx-4.1,cy+sign*2.25));t.SetEnd(V(cx-1.875,cy+sign*3));t.SetWidth(mm(.25));t.SetLayer(pcbnew.F_Cu);t.SetNet(net);b.Add(t)
  b.RemoveNative(old);b.Add(f)
 elif ref=='J1':
  old.SetFPID(pcbnew.LIB_ID(*fp.split(':')));old.SetValue(value);old.Models().clear()
  for pad in old.Pads():
   if pad.GetNumber()=='2':pad.SetFPRelativePosition(V(-5.9,0))
  old.SetLibDescription('XKB C381116 A1: pad1 rear, pad2X-5.9,pad3X-3/Y4.7,slots1x3.5; center positive12V.')
  lib=pcbnew.Cast_to_FOOTPRINT(old.Duplicate(False));lib.SetPosition(V(0,0));lib.SetOrientationDegrees(0);pcbnew.FootprintSave(str(K/'lib/carrier.pretty'),lib)
 else:old.SetValue(value)
assert before==[(t.GetNetname(),str(t.GetStart()),str(t.GetEnd())) for t in b.GetTracks() if t.GetNetname() not in ['TAB_RST','F_BTN0']]
for f in b.GetFootprints():
 f.Reference().SetLayer(pcbnew.F_Fab if not f.IsFlipped() else pcbnew.B_Fab);f.Reference().SetVisible(False);f.Value().SetVisible(False)
pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
(K/'sim/lcsc-revision.json').write_text(json.dumps({'selected':selected,'non_button_routes_unchanged':True,'dimensions_mm':[99,78]},indent=2)+'\n');print('A-type LCSC revision written')
