from pathlib import Path
import zipfile,json,pcbnew
from collections import defaultdict
H=Path(__file__).resolve().parent;mapping=json.loads((H/'easyeda/footprint-map.json').read_text());z=zipfile.ZipFile(H/'easyeda/spark-lite-a-lcsc-review.epro2');docs={};active=None
for line in z.read(next(n for n in z.namelist() if n.endswith('.epru'))).decode().splitlines():
 if '||' not in line:continue
 a,b=line.split('||',1);a=json.loads(a);b=json.loads(b.rstrip('|'))
 if a['type']=='DOCHEAD':active=b.get('uuid');docs.setdefault(active,[])
 elif a['type']=='PAD':docs[active].append(b)
results=[]
for ref,name in [('J1','BarrelJack_XKB_C381116'),('SW3','SW_XKB_DS02BLP_C692500'),('SW1','SW_XKB_TS1187A_C318884'),('SW2','SW_XKB_TS1187A_C318884')]:
 f=pcbnew.FootprintLoad(str(H/'kicad/lib/carrier.pretty'),name);expected=defaultdict(list);actual=defaultdict(list)
 for p in f.Pads():
  q=p.GetPosition();s=p.GetSize();d=p.GetDrillSize();expected[p.GetNumber()].append([pcbnew.ToMM(x) for x in [q.x,q.y,s.x,s.y,d.x,d.y]])
 for p in docs[mapping[ref]]:
  hole=[p['hole']['width']*.0254,p['hole']['height']*.0254] if p.get('hole') else [0,0]
  if round(p['relativeAngle'])%180==90:hole.reverse()
  actual[p['num']].append([p['centerX']*.0254,-p['centerY']*.0254,p['defaultPad']['width']*.0254,p['defaultPad']['height']*.0254,*hole])
 errors=[]
 for num,v in expected.items():
  if len(v)!=len(actual[num]):errors.append({'pad':num,'count':False});continue
  for a,e in zip(sorted(actual[num]),sorted(v)):
   if max(abs(x-y) for x,y in zip(a,e))>4e-6:errors.append({'pad':num,'expected':e,'actual':a})
 results.append({'ref':ref,'ok':not errors,'errors':errors})
report={'ok':all(r['ok'] for r in results),'results':results,'scope':'Native project footprint library pad positions, copper and drill dimensions for new LCSC parts against manufacturer-derived local lands; physical orientation and mating still pending.'}
(H/'easyeda/native-land-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['ok']
