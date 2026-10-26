"""Fingerprint relevant copper independently of full PCB serialization changes.

Use --baseline before revision, then rerun to compare. Track geometry only;
new HDMI pull-up load is covered by the declared 10mA local-rail envelope.
"""
from pathlib import Path
import json
import hashlib
import sys
import pcbnew

H=Path(__file__).resolve().parent;ROOT=H.parents[1]
def sha(o):return hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest()
result={};boards=[]
for v in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
    path=ROOT/'variants'/v/'kicad/tab5-fpga-carrier.kicad_pcb'
    b=pcbnew.LoadBoard(str(path));boards.append(b)
    nets={str(n) for n in b.GetNetsByName()}
    signals=[f'D{i}' for i in range(8)]+['CLK','RDY','DIR']+[f'AUX{i}' for i in range(4)]
    parallel={prefix+signal for prefix in ('M_','ISO_','F_') for signal in signals}
    power={n for n in nets if any(s in n.upper() for s in ('VIN','VOUT','BUCK','5V_CORE','3V3_LOCAL'))} | {'+5V','+3V3','FB_TRIM'}
    def fingerprint(selected):
        tracks=[]
        for t in b.GetTracks():
            n=str(t.GetNetname())
            if n not in selected:continue
            a=t.GetStart();z=t.GetEnd()
            tracks.append([n,t.GetClass(),a.x,a.y,z.x,z.y,t.GetLayer(),(t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth())])
        return dict(nets=sorted(selected),copper_sha256=sha(sorted(tracks)),track_count=len(tracks))
    result[v]=dict(source_pcb_sha256=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),parallel=fingerprint(parallel),power=fingerprint(power),core5V=fingerprint({'+5V'}))
if '--baseline' in sys.argv:
    (H/'geometry-before-revision.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
else:
    baseline=json.loads((H/'geometry-before-revision.json').read_text(encoding='utf-8'))
    for v,r in result.items():
        r['parallel_copper_unchanged']=r['parallel']==baseline[v]['parallel']
        r['power_selected_copper_unchanged']=r['power']==baseline[v]['power']
        r['core5V_copper_unchanged']=r['core5V']==baseline[v]['core5V']
    (H/'geometry-after-revision.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=1))
