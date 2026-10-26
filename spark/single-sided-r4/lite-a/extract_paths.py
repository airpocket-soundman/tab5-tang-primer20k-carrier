"""Read-only extraction of every populated parallel-link copper section."""
from pathlib import Path
import collections
import hashlib
import json
import math
import pcbnew

HERE=Path(__file__).resolve().parent
ROOT=HERE
VARIANTS=('spark-lite-a',)
SIGNALS=['D'+str(i) for i in range(8)]+['CLK','RDY','DIR']+['AUX'+str(i) for i in range(4)]
result={}
for variant in VARIANTS:
    path=HERE/'design/kicad/tab5-fpga-carrier.kicad_pcb'
    b=pcbnew.LoadBoard(str(path));signals={};segments=[]
    for sig in SIGNALS:
        sections={}
        for prefix in ('M_','ISO_','F_'):
            net=prefix+sig;tracks=[t for t in b.GetTracks() if t.GetNetname()==net]
            lengths=collections.defaultdict(float);via_count=0;total=0
            for t in tracks:
                if isinstance(t,pcbnew.PCB_VIA):via_count+=1;continue
                length=pcbnew.ToMM(t.GetLength());total+=length
                layer=b.GetLayerName(t.GetLayer());width=pcbnew.ToMM(t.GetWidth())
                lengths[(layer,width)]+=length
                aa,bb=t.GetStart(),t.GetEnd()
                segments.append((sig,layer,pcbnew.ToMM(aa.x),pcbnew.ToMM(aa.y),pcbnew.ToMM(bb.x),pcbnew.ToMM(bb.y),width))
            pp=[(f.GetReference(),p.GetNumber()) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()==net]
            assert len(pp)==2,(variant,net,pp)
            sections[prefix[:-1]]={'length_mm':total,'vias':via_count,'physical_endpoints':pp,'layer_width_lengths':[{'layer':l,'width_mm':w,'length_mm':v} for (l,w),v in sorted(lengths.items())]}
        series=[f for f in b.GetFootprints() if f.GetReference().startswith('R') and {p.GetNetname() for p in f.Pads()}=={'ISO_'+sig,'F_'+sig}]
        assert len(series)==1
        signals[sig]={'sections':sections,'total_carrier_mm':sum(s['length_mm'] for s in sections.values()),'total_carrier_vias':sum(s['vias'] for s in sections.values()),'series':{'reference':series[0].GetReference(),'actual_value':series[0].GetValue()}}
    coupled=collections.defaultdict(float);minimum={}
    for i,a in enumerate(segments):
        ux,uy=a[4]-a[2],a[5]-a[3];la=math.hypot(ux,uy)
        if la<.1:continue
        ux,uy=ux/la,uy/la
        for c in segments[i+1:]:
            if a[0]==c[0] or a[1]!=c[1]:continue
            vx,vy=c[4]-c[2],c[5]-c[3];lc=math.hypot(vx,vy)
            if lc<.1 or abs((ux*vx+uy*vy)/lc)<.995:continue
            cross=abs((c[2]-a[2])*uy-(c[3]-a[3])*ux)
            edge_gap=cross-(a[6]+c[6])/2
            if edge_gap>1 or edge_gap<-.01:continue
            c0=(c[2]-a[2])*ux+(c[3]-a[3])*uy;c1=(c[4]-a[2])*ux+(c[5]-a[3])*uy
            overlap=max(0,min(la,max(c0,c1))-max(0,min(c0,c1)))
            if overlap<.05:continue
            key=tuple(sorted((a[0],c[0])));coupled[key]+=overlap
            minimum[key]=min(minimum.get(key,99),edge_gap)
    result[variant]={'sourcePCB':str(path.relative_to(ROOT)),'sourcePCBhash':hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'signals':signals,'coupled_parallel_spans':[{'signals':list(k),'overlap_mm':v,'minimum_edge_gap_mm':minimum[k]} for k,v in sorted(coupled.items(),key=lambda kv:-kv[1])], 'length_scope':'sum of physical track segments for each two-pad net; conservatively includes short copper inside solder lands; vias counted separately. Cross-board internal traces are modelled separately as uncertain ranges.'}
(HERE/'simulation/parallel/extracted-paths.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:{'max_length_mm':max(s['total_carrier_mm'] for s in v['signals'].values()),'max_vias':max(s['total_carrier_vias'] for s in v['signals'].values()),'closest_pair':v['coupled_parallel_spans'][0]} for k,v in result.items()},indent=2))
