"""Measure real local-cap paths using the physical copper graph, KiCad Python."""
from pathlib import Path
import heapq
import json
import math
import pcbnew
H=Path(__file__).resolve().parent
prefix=(H/'check_power_dc.py').read_text().split("source=('pad','L1','2')")[0]

def measure(net,src,dst):
    scope={'__file__':str(H/'check_power_dc.py')}
    exec(compile(prefix.replace("=='+5V'",'=='+repr(net)),str(H/'check_power_dc.py'),'exec'),scope)
    g=scope['g'];b=scope['b'];ts=scope['tracks']
    source=('pad',src[0],src[1]);target=('pad',dst[0],dst[1]);dist={source:0};prev={};q=[(0,str(source),source)]
    while q:
        d,_,n=heapq.heappop(q)
        if d>dist[n]:continue
        if n==target:break
        for m,r in g[n]:
            nd=d+r
            if nd<dist.get(m,math.inf):dist[m]=nd;prev[m]=n;heapq.heappush(q,(nd,str(m),m))
    assert target in dist,(net,src,dst)
    path=[target]
    while path[-1]!=source:path.append(prev[path[-1]])
    path.reverse();length=0;vias=0;widths=[];layers=set()
    for a,z in zip(path,path[1:]):
        if a[0]=='pad' or z[0]=='pad':continue
        if a[0]!=z[0]:vias+=1;continue
        length+=math.hypot(a[1]-z[1],a[2]-z[2])/1e6
        layers.add(b.GetLayerName(a[0]))
        mid=pcbnew.VECTOR2I((a[1]+z[1])//2,(a[2]+z[2])//2)
        candidates=[pcbnew.ToMM(t.GetWidth()) for t in ts if t.GetLayer()==a[0] and t.HitTest(mid)]
        if candidates:widths.append(min(candidates))
    def getpad(ref,num):return next(p for f in b.GetFootprints() if f.GetReference()==ref for p in f.Pads() if p.GetNumber()==num)
    gv=[t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()=='GND']
    ground={r:min(pcbnew.ToMM((getpad(r,'1' if r=='U3' else '2').GetPosition()-v.GetPosition()).EuclideanNorm()) for v in gv) for r in ('U3','C10','C11')}
    return {'endpoint_spacing_mm':pcbnew.ToMM((getpad(*src).GetPosition()-getpad(*dst).GetPosition()).EuclideanNorm()),'copper_path_length_mm':length,'layer_transition_count':vias,'track_layers':sorted(layers),'minimum_path_width_mm':min(widths),'copper_path_resistance_ohm':dist[target],'nearest_ground_via_mm':ground}

result={'input_cap':measure('+5V',('U3','3'),('C10','1')),'output_cap':measure('+3V3',('U3','2'),('C11','1')),'scope':'Shortest copper-resistance graph path. Pad copper treated ideal; no loop inductance or stability proof. GND-via distances are geometric nearest distances, not return-current trajectories.'}
(H/'ldo_local_paths.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=1))
