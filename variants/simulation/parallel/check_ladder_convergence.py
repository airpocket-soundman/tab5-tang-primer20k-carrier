"""Double the RLC ladder resolution on representative bounding channels."""
from pathlib import Path
import json
from run_waveforms import deck,PARAMS,analyse
from ngspice_shared import Spice
H=Path(__file__).resolve().parent
d=json.loads((H/'extracted-paths.json').read_text());s=Spice();rows=[]
for variant in ('lite-a-dual','lite-c-dnp'):
    for direction in ('write','read'):
        for corner in ('fast','slow'):
            cases=[]
            for scale in (1,2):
                p=dict(PARAMS[corner],segments_scale=scale,cio=(3.467e-12 if corner=='fast' else 11e-12),rise_window_s=200e-9)
                lines,recv=deck(d[variant]['signals']['CLK'],p,direction,680,10e-6)
                lines=[x if not x.startswith('.tran') else '.tran 20p 220n 0 20p' for x in lines]
                assert s.load(lines)==0;s.run();m=analyse(s.vector('time'),s.vector('v('+recv+')'),p)
                source='host' if direction=='write' else 'core';vv=s.vector('v('+source+')')
                cases.append(dict(scale=scale,source_max_V=float(vv.max()),source_min_V=float(vv.min()),**m))
            rows.append(dict(variant=variant,direction=direction,corner=corner,cases=cases,receiver_peak_change_V=cases[1]['max_V']-cases[0]['max_V'],settling_change_ns=cases[1]['settle_5percent_ns']-cases[0]['settle_5percent_ns']))
(H/'ladder-convergence.json').write_text(json.dumps({'results':rows,'scope':'Representative longestCLK channels, doubled segmentation. Convergence of this model does not validate unmeasured GPIO/internal-board assumptions.'},indent=2)+'\n')
print(rows)
