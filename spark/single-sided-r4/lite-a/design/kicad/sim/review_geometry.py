"""Read-only copper-path audit. Run with KiCad's Python from repository root.

Find shortest same-net paths between component pad centres, splitting tracks at
tees and connecting copper inside pads. This is geometric length, not delay.
It does not assume the router's pair_lengths/stub_tracks metadata is complete.
"""
from pathlib import Path
import collections
import hashlib
import heapq
import json
import math
import pcbnew

HERE=Path(__file__).resolve().parent
PCB=HERE.parent/'tab5-fpga-carrier.kicad_pcb'
board=pcbnew.LoadBoard(str(PCB))
mm=pcbnew.ToMM


def pos(p):
    return round(mm(p.x),6),round(mm(p.y),6)


def solve(net):
    tracks=[t for t in board.GetTracks() if t.GetNetname()==net]
    nodes=set();lines=[];via_nodes=[]
    for t in tracks:
        if isinstance(t,pcbnew.PCB_VIA):
            x,y=pos(t.GetPosition())
            v=[(x,y,ly) for ly in [0,2,4,6]]
            nodes.update(v);via_nodes.append(v)
        else:
            a=(*pos(t.GetStart()),int(t.GetLayer()))
            b=(*pos(t.GetEnd()),int(t.GetLayer()))
            nodes.update([a,b]);lines.append((a,b))
    graph=collections.defaultdict(list)
    def edge(a,b,length):
        graph[a].append((b,length));graph[b].append((a,length))
    for a,b in lines:
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        split=[]
        for v in nodes:
            if v[2]!=a[2]:continue
            projection=((v[0]-a[0])*dx+(v[1]-a[1])*dy)/(length*length)
            cross=abs((v[0]-a[0])*dy-(v[1]-a[1])*dx)/length
            if -.000001<=projection<=1.000001 and cross<.000002:
                split.append((projection,v))
        split.sort()
        for (_,u),(_,v) in zip(split,split[1:]):edge(u,v,math.dist(u[:2],v[:2]))
    for v in via_nodes:
        for u,w in zip(v,v[1:]):edge(u,w,0) # vertical delay deliberately excluded
    pads=[]
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname()!=net:continue
            name=f.GetReference()+'.'+p.GetNumber()
            pads.append((name,f.GetValue()))
            centre=pos(p.GetPosition())
            for v in nodes:
                q=pcbnew.VECTOR2I(round(v[0]*1e6),round(v[1]*1e6))
                if p.IsOnLayer(v[2]) and p.HitTest(q):
                    edge(name,v,math.dist(centre,v[:2]))
    def distance(start,end):
        pq=[(0,str(start),start)];best={start:0}
        while pq:
            d,_,u=heapq.heappop(pq)
            if d>best[u]+1e-9:continue
            if u==end:return d
            for v,w in graph[u]:
                nd=d+w
                if nd<best.get(v,math.inf)-1e-9:
                    best[v]=nd;heapq.heappush(pq,(nd,str(v),v))
        return None
    endpoints=[name for name,value in pads if value!='499R']
    if len(endpoints)!=2:raise ValueError((net,pads))
    biases=[name for name,value in pads if value=='499R']
    length=distance(*endpoints)
    branch=None
    if biases and length is not None:
        # Tree geometry: (a->r + b->r - a->b)/2 is branch from main path.
        ar=distance(endpoints[0],biases[0]);br=distance(endpoints[1],biases[0])
        if ar is not None and br is not None:branch=(ar+br-length)/2
    return dict(endpoints=endpoints,main_pad_centre_path_mm=length,
                bias_branch_from_tee_mm=branch,pads=pads,
                planar_track_sum_mm=sum(math.dist(a[:2],b[:2]) for a,b in lines))


out={'board_sha256':hashlib.sha256(PCB.read_bytes()).hexdigest(),
     'method':'Connectivity graph; shortest pad-centre path; via vertical length excluded; no package length',
     'nets':{},'pairs':{}}
for tag in ['D0','D1','D2','CK']:
    for pn in ['P','N']:
        for suffix in ['','_C','_K']:
            net=f'HDMI_{tag}{pn}{suffix}';out['nets'][net]=solve(net)
    totals={pn:sum(out['nets'][f'HDMI_{tag}{pn}{suffix}']['main_pad_centre_path_mm'] for suffix in ['','_C','_K']) for pn in ['P','N']}
    totals['skew_mm']=totals['P']-totals['N'];out['pairs'][tag]=totals
    print(tag,totals)
for net,r in out['nets'].items():
    if r['bias_branch_from_tee_mm'] is not None:print(net,'branch_mm',r['bias_branch_from_tee_mm'])
(HERE/'review_connectivity_2026-10-24.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
