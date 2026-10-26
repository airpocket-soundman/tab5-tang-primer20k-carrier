from pathlib import Path
import zipfile,json,pcbnew
H=Path(__file__).resolve().parent;mapping=json.loads((H/'easyeda/footprint-map.json').read_text())
z=zipfile.ZipFile(H/'easyeda/spark-lcsc-priority-review.epro2');docs={};active=None
for l in z.read(next(n for n in z.namelist() if n.endswith('.epru'))).decode().splitlines():
 if '||' not in l:continue
 h,b=l.split('||',1);h=json.loads(h);b=json.loads(b.rstrip('|'))
 if h['type']=='DOCHEAD':active=b.get('uuid');docs.setdefault(active,[])
 elif h['type']=='PAD':docs[active].append(b)
result=[]
for ref,name in [('J1','BarrelJack_XKB_C381116'),('SW3','SW_XKB_DS02BLP_C692500')]:
 f=pcbnew.FootprintLoad(str(H/'kicad/lib/carrier.pretty'),name);native={p['num']:p for p in docs[mapping[ref]]};errors=[]
 for p in f.Pads():
  n=native[p.GetNumber()];pos=p.GetPosition();size=p.GetSize();drill=p.GetDrillSize()
  expected=[pcbnew.ToMM(pos.x),pcbnew.ToMM(pos.y),pcbnew.ToMM(size.x),pcbnew.ToMM(size.y),pcbnew.ToMM(drill.x),pcbnew.ToMM(drill.y)]
  hole=[n['hole']['width']*.0254,n['hole']['height']*.0254]
  assert round(n['padAngle'])%180==0
  if round(n['relativeAngle'])%180==90:hole.reverse()
  actual=[n['centerX']*.0254,-n['centerY']*.0254,n['defaultPad']['width']*.0254,n['defaultPad']['height']*.0254,*hole]
  if max(abs(a-e) for a,e in zip(actual,expected))>4e-6:errors.append({'pin':p.GetNumber(),'expected':expected,'actual':actual})
  if not n['plated'] or n['topSolderExpansion']<0 or n['bottomSolderExpansion']<0:errors.append({'pin':p.GetNumber(),'plating_or_mask':True})
  assert p.IsOnLayer(pcbnew.F_Mask) and p.IsOnLayer(pcbnew.B_Mask)
 result.append({'ref':ref,'ok':not errors,'pads':len(native),'errors':errors})
report={'ok':all(r['ok'] for r in result),'results':result,'scope':'LCSC J1/SW3 pad centers, copper size, slot/drill size, plating and open masks against local manufacturer-derived KiCad footprints. Physical mating still untested.'}
(H/'easyeda/manual-footprint-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if report['ok'] else 1)
