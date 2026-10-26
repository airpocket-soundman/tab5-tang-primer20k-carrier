"""Drawing-based LCSC revision. Run once using KiCad's Python; preserves routes."""
from pathlib import Path
import sys,json,hashlib,math
import pcbnew
H=Path(__file__).resolve().parent;K=H/'kicad'
sys.path.insert(0,str(K/'gen'));import sexp
S=sexp.Str
selected={
 'J1':('DC-005-5A-2.0','C381116','carrier:BarrelJack_XKB_C381116','LCSC/JLC wave-solder candidate; center-positive stabilized12V only; XKB drawing A1 2025-04-22. 5A connector rating is not board current rating. Verify actual power plug fit.'),
 'SW3':('DS-02BLP','C692500','carrier:SW_XKB_DS02BLP_C692500','LCSC/JLC wave-solder candidate; local KiCad DIP numbering1-4/2-3; supplier diagram aligned numbering1-3/2-4. First pole closes BUCK_EN to GND to stop FPGA; second unused. Both OFF initially.'),
 'J3':('2.54-2*15P','C56496',None,'LCSC/JLC wave-solder candidate; bottom male2x15,6mm mating pins,3mm solder tails,2.54mm insulator; preserve user-confirmed mirrored pin assignment; fit and two-sided process pending.'),
 'JP1':('B-2100S02P-A110','C124375',None,'LCSC/JLC wave-solder candidate; 1x2 male2.54mm,6mm mating pins,3mm solder tails; C5305 shunt supplied separately and initially absent.')}
# Patch model, retaining all earlier engineering decisions as provenance.
p=K/'gen/design.py';s=p.read_text(encoding='utf8')
s=s.split('# LCSC PRIORITY REVISION')[0]
s+='\n# LCSC PRIORITY REVISION\n_build_before_lcsc=build\ndef build():\n    cs=_build_before_lcsc()\n    selected='+repr(selected)+'\n    for c in cs:\n        if c.ref in selected:\n            c.value,c.lcsc,fp,c.comment=selected[c.ref]\n            if fp:c.fp=fp\n    return cs\n'
p.write_text(s,encoding='utf8')
# Patch existing schematic properties only, preserving all UUIDs and wiring.
p=K/'tab5-fpga-carrier.kicad_sch';tree=sexp.parse(p.read_text(encoding='utf8'))
for sym in sexp.find(tree,'symbol'):
 props={str(v[1]):v for v in sexp.find(sym,'property')};ref=str(props.get('Reference',['','',''])[2])
 if ref not in selected:continue
 value,code,fp,comment=selected[ref]
 props['Value'][2]=S(value)
 if fp:props['Footprint'][2]=S(fp)
 for key,val in [('LCSC',code),('Supplier','LCSC'),('Supplier Part',code),('Comment',comment)]:
  if key in props:props[key][2]=S(val)
  else:sym.append(['property',S(key),S(val),['at','0','0','0'],['effects',['font',['size','1.27','1.27']],['hide','yes']]])
p.write_text(sexp.dump(tree)+'\n',encoding='utf8')
mm=pcbnew.FromMM
def V(x,y):return pcbnew.VECTOR2I(mm(x),mm(y))
def routes(b):
 return sorted((t.GetClass(),t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,pcbnew.PCB_VIA) else 0) for t in b.GetTracks())
def rect(f,a,z,layer):
 s=pcbnew.PCB_SHAPE(f);s.SetShape(pcbnew.SHAPE_T_RECT);ang=math.radians(f.GetOrientationDegrees());pos=f.GetPosition();xf=lambda q:pos+V(q[0]*math.cos(ang)-q[1]*math.sin(ang),q[0]*math.sin(ang)+q[1]*math.cos(ang));s.SetStart(xf(a));s.SetEnd(xf(z));s.SetLayer(layer);s.SetWidth(mm(.05));f.Add(s)
P=K/'tab5-fpga-carrier.kicad_pcb';b=pcbnew.LoadBoard(str(P));before=routes(b);fps={f.GetReference():f for f in b.GetFootprints()}
for ref,(value,code,fp,comment) in selected.items():
 f=fps[ref];f.SetValue(value)
 if not fp:continue
 f.SetFPID(pcbnew.LIB_ID(*fp.split(':')));f.Models().clear()
 for item in f.GraphicalItems():item.SetLayer(pcbnew.Dwgs_User)
 if ref=='J1':
  f.SetLibDescription('XKB C381116 A1: top view pad1 rear13.6mm, pad2 at7.7mm, pad3 at10.6mm/4.7mm. 3 slots1x3.5mm; center-positive pad1; pad2/3 GND.')
  points={'1':(0,0),'2':(-5.9,0),'3':(-3,4.7)}
  for p in f.Pads():
   n=p.GetNumber();p.SetFPRelativePosition(V(*points[n]));p.SetSize(V(4.1,3.5) if n=='3' else V(3.5,4.1));p.SetDrillSize(V(3.5,1) if n=='3' else V(1,3.5))
  rect(f,(-13.6,-4.5),(.4,4.5),pcbnew.F_Fab);rect(f,(-14.1,-5),(1,6.95),pcbnew.F_CrtYd)
 else:
  f.SetLibDescription('XKB C692500 drawing A2:7.62mm rows,2.54mm pitch,1.0mm drill,body9.9x6.6,H5.5. Local DIP numbering1-4/2-3; supplier aligned diagram1-3/2-4; first pole only.')
  points={'1':(0,0),'4':(7.62,0),'2':(0,-2.54),'3':(7.62,-2.54)}
  for p in f.Pads():p.SetFPRelativePosition(V(*points[p.GetNumber()]));p.SetDrillSize(V(1,1));p.SetSize(V(1.7,1.7))
  rect(f,(-1.14,-4.57),(8.76,2.03),pcbnew.F_Fab);rect(f,(-1.64,-5.07),(9.26,2.53),pcbnew.F_CrtYd)
 # Save footprint at local origin; keep board component position and orientation.
 lib=pcbnew.Cast_to_FOOTPRINT(f.Duplicate(False));lib.SetPosition(V(0,0));lib.SetOrientationDegrees(0)
 pcbnew.FootprintSave(str(K/'lib/carrier.pretty'),lib)
assert before==routes(b),'Unexpected routing change'
pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
report={'all_tracks_and_vias_unchanged':True,'selected':selected,'pcb_sha256':hashlib.sha256(P.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'limits':['LCSC/JLC listing is not manufacturer order acceptance','Tab5 mating and DC plug fit not physically verified','J3 bottom THT process with top SMT requires manufacturer review','SW3 local CAD pad numbering differs from supplier diagram; physical pole correspondence documented']}
(K/'sim/lcsc-revision.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,indent=2))

