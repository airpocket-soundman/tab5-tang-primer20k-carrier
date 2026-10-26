"""Conservative +5V copper path resistance to Core pins; KiCad Python."""
import collections,heapq,json,math
from pathlib import Path
import pcbnew
H=Path(__file__).resolve().parent
b=pcbnew.LoadBoard(str(H.parent/'tab5-fpga-carrier.kicad_pcb'))
mm=pcbnew.ToMM
tracks=[t for t in b.GetTracks() if t.GetNetname()=='+5V' and not isinstance(t,pcbnew.PCB_VIA)]
vias=[t for t in b.GetTracks() if t.GetNetname()=='+5V' and isinstance(t,pcbnew.PCB_VIA)]
pads=[(f.GetReference(),p) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()=='+5V']
g=collections.defaultdict(list);points={}
def node(layer,p):
 k=(layer,p.x,p.y);points[k]=p;return k
def edge(a,c,r):g[a].append((c,r));g[c].append((a,r))
for t in tracks:
 for p in (t.GetStart(),t.GetEnd()):node(t.GetLayer(),p)
for v in vias:
 ns=[node(l,v.GetPosition()) for l in (pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)]
 for a,c in zip(ns,ns[1:]):edge(a,c,.001) # 2mOhm full via conservative nominal
# Add junctions where finite-width copper overlaps despite offset centrelines.
for t in tracks:
 a=t.GetStart();c=t.GetEnd();dx=c.x-a.x;dy=c.y-a.y;ll=dx*dx+dy*dy
 for k,pp in list(points.items()):
  if k[0]!=t.GetLayer():continue
  q=max(0,min(1,((pp.x-a.x)*dx+(pp.y-a.y)*dy)/(ll or 1)))
  v=pcbnew.VECTOR2I(round(a.x+q*dx),round(a.y+q*dy));distance=(pp-v).EuclideanNorm()/1e6
  if 0<distance<=mm(t.GetWidth())/2:
   other=node(t.GetLayer(),v)
   edge(k,other,.00001724*distance/(.127*.0175))
# Include pads touching the interior of a track, not just segment endpoints.
for ref,p in pads:
 for t in tracks:
  if not p.IsOnLayer(t.GetLayer()):continue
  a=t.GetStart();c=t.GetEnd();dx=c.x-a.x;dy=c.y-a.y;ll=dx*dx+dy*dy
  pp=p.GetPosition();q=max(0,min(1,((pp.x-a.x)*dx+(pp.y-a.y)*dy)/(ll or 1)))
  v=pcbnew.VECTOR2I(round(a.x+q*dx),round(a.y+q*dy))
  if p.HitTest(v):node(t.GetLayer(),v)
for t in tracks:
 a=t.GetStart();c=t.GetEnd();dx=c.x-a.x;dy=c.y-a.y;ll=dx*dx+dy*dy
 hits=[]
 for k,p in list(points.items()):
  if k[0]!=t.GetLayer():continue
  q=((p.x-a.x)*dx+(p.y-a.y)*dy)/ll if ll else 0
  if -.000001<=q<=1.000001 and abs((p.x-a.x)*dy-(p.y-a.y)*dx)/math.sqrt(ll or 1)<10:hits.append((q,k))
 hits.sort()
 th=.035 if t.GetLayer() in (pcbnew.F_Cu,pcbnew.B_Cu) else .0175
 for (_,n),(_,m) in zip(hits,hits[1:]):
  length=math.hypot(n[1]-m[1],n[2]-m[2])/1e6
  edge(n,m,.00001724*length/(mm(t.GetWidth())*th))
for ref,p in pads:
 pn=('pad',ref,p.GetNumber())
 for k,pos in list(points.items()):
  if p.IsOnLayer(k[0]) and p.HitTest(pos):edge(pn,k,0)
source=('pad','L1','2');dist={source:0};q=[(0,str(source),source)]
while q:
 d,_,n=heapq.heappop(q)
 if d>dist[n]:continue
 for m,r in g[n]:
  nd=d+r
  if nd<dist.get(m,1e99):dist[m]=nd;heapq.heappush(q,(nd,str(m),m))
res={str(n):dist.get(('pad','J4',str(n))) for n in (4,5,6,7)}
assert all(v is not None for v in res.values()),res
# TPS5430 all-temperature Vref limits 1.196..1.245V, not a rounded +/-2%.
# R7 is 3.3k parallel with (100k +100k), all three resistors +/-1%.
req=1/(1/3300+1/200000)
vmin=1.196*(1+10000*.99/(req*1.01));vmax=1.245*(1+10000*1.01/(req*.99))
hot={n:r*(1+.00393*(85-20)) for n,r in res.items()}
out=dict(ok=(vmin-max(hot.values())*.5>=4.5 and vmax<=5.5),path_resistance_ohm=res,copper_temperature_C=20,hot_copper_temperature_C=85,hot_path_resistance_ohm=hot,feedback_lower_equivalent_ohm=req,regulator_conservative_bound_V=[vmin,vmax],core_5V_official_range_V=[4.5,5.5],core_0_5A_max_path_drop_V=max(res.values())*.5,core_2A_max_path_drop_V=max(res.values())*2,core_0_5A_hot_copper_lower_bound_V=vmin-max(hot.values())*.5,notes=['Shortest series-resistance path gives a conservative copper-only drop when assigning the entire Core current to each individual path; parallel copper paths reduce actual resistance.','35um outer /17.5um inner; 2mOhm via; contact/inductor/ground-return resistance, regulator ripple/transients and load regulation excluded.','TPS5430 Vref 1.196..1.245V and each feedback resistor +/-1% are design bounds, not measured output. Core official 0.5A requirement is not a peak-current guarantee.','85C copper sensitivity is a resistance model only; it does not qualify the complete board for 85C ambient operation.'])
(H/'power_dc_check.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=1))
