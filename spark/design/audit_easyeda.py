"""Independent electrical/geometry comparison, using KiCad Python.

Native source coordinates are mil; serialization accuracy is 0.0001mil.
Checks pads by ref/number/net and tracks/vias by net, layer and geometry.
Does not certify native DRC, pad shapes, fills, schematic association or eligibility.
"""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib
import numpy as np
import pcbnew
H=Path(__file__).resolve().parent;P=H/'kicad/tab5-fpga-carrier.kicad_pcb';S=H/'easyeda/akizuki-pcb-source.txt'
rows=[]
for line in S.read_text(encoding='utf8').splitlines():
 if '||' not in line:continue
 header,body=line.split('||',1);rows.append((json.loads(header),json.loads(body.rstrip('|'))))
refs={body['parentId']:body['value'] for head,body in rows if head['type']=='ATTR' and body.get('key')=='Designator'}
components=[head['id'] for head,body in rows if head['type']=='COMPONENT']
b=pcbnew.LoadBoard(str(P));expected=defaultdict(list);actual=defaultdict(list)
def mil(v):return pcbnew.ToMM(v)/.0254
def seg(net,layer,a,z,width):
 a,z=sorted([tuple(a),tuple(z)])
 return (net,layer),(*a,*z,width)
layers={pcbnew.F_Cu:1,pcbnew.B_Cu:2,pcbnew.In1_Cu:15,pcbnew.In2_Cu:16}
for t in b.GetTracks():
 if isinstance(t,pcbnew.PCB_VIA):key=('via',t.GetNetname());value=(mil(t.GetPosition().x),-mil(t.GetPosition().y),mil(t.GetDrillValue()),mil(t.GetWidth(pcbnew.F_Cu)))
 else:
  key,value=seg(t.GetNetname(),layers[t.GetLayer()],(mil(t.GetStart().x),-mil(t.GetStart().y)),(mil(t.GetEnd().x),-mil(t.GetEnd().y)),mil(t.GetWidth()))
 expected[key].append(value)
for head,body in rows:
 if head['type']=='VIA':key=('via',body['netName']);value=(body['centerX'],body['centerY'],body['holeDiameter'],body['viaDiameter'])
 elif head['type']=='LINE' and body['layerId'] in layers.values():key,value=seg(body['netName'],body['layerId'],(body['startX'],body['startY']),(body['endX'],body['endY']),body['width'])
 else:continue
 actual[key].append(value)
errors=[];max_delta=0
for key in expected.keys()|actual.keys():
 e=expected[key];a=actual[key]
 if len(e)!=len(a):errors.append({'group':str(key),'expected':len(e),'actual':len(a)});continue
 order=lambda values:sorted(values,key=lambda row:tuple(round(x,3) for x in row))
 if not e:continue
 delta=float(np.max(np.abs(np.array(order(e))-np.array(order(a)))))
 max_delta=max(max_delta,delta)
 if delta>.00015:errors.append({'group':str(key),'max_delta_mil':delta})
paste_only=[(f.GetReference(),p.GetNumber()) for f in b.GetFootprints() for p in f.Pads() if not p.GetLayerSet().CuStack()]
ep=Counter((f.GetReference(),p.GetNumber(),p.GetNetname()) for f in b.GetFootprints() for p in f.Pads() if p.GetLayerSet().CuStack())
ap=Counter()
for head,body in rows:
 if head['type']!='PAD_NET':continue
 ident=json.loads(head['id']);ap[(refs[ident[1]],str(ident[2]),body.get('padNet',''))]+=1
if ep!=ap:errors.append({'pad_net_missing':list((ep-ap).items()),'pad_net_extra':list((ap-ep).items())})
expected_refs={f.GetReference() for f in b.GetFootprints()}
native_refs={refs[i] for i in components}
if expected_refs!=native_refs:errors.append({'component_reference_mismatch':True})
report={'ok':not errors,'source_pcb_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'native_source_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'components':len(components),'pads':sum(ap.values()),'non_copper_paste_apertures_excluded':paste_only,'named_nets':len({net for _,_,net in ap if net}),'segments':sum(len(v) for k,v in actual.items() if k[0]!='via'),'vias':sum(len(v) for k,v in actual.items() if k[0]=='via'),'max_geometry_delta_mm':max_delta*.0254,'tolerance_mm':.00015*.0254,'errors':errors,'scope':'Reference identities, all copper/mechanical pad-net assignments, copper track net/layer/width/endpoints and via net/location/drill/diameter; excludes paste aperture U1, pad shapes/masks, zones, native DRC, schematic association and eligibility'}
(H/'easyeda/electrical-migration-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report,indent=2));raise SystemExit(0 if report['ok'] else 1)
