"""Representative longCLK channel with carrier Z increased to160ohm.

This bounds a more distant/partly interrupted reference-plane assumption.
It is not a reconstruction of every inner-layer return-current path.
"""
from pathlib import Path
import json
from run_waveforms import deck,PARAMS,analyse
from ngspice_shared import Spice
H=Path(__file__).resolve().parent;d=json.loads((H/'extracted-paths.json').read_text());s=Spice();out=[]
for variant in ('lite-a-dual','lite-c-dnp'):
    for corner in ('fast','controlled','slow'):
        for direction in ('write','read'):
            p=dict(PARAMS[corner],z=160,cio=(11e-12 if corner=='slow' else 3.467e-12),rise_window_s=200e-9)
            lines,recv=deck(d[variant]['signals']['CLK'],p,direction,680,10e-6)
            source='host' if direction=='write' else 'core'
            lines=[x for x in lines if not x.startswith('.save')];lines.insert(-1,f'.save v({recv}) v({source}) v(swa0) v(swb0)')
            lines=[x if not x.startswith('.tran') else '.tran 20p 220n 0 20p' for x in lines]
            assert s.load(lines)==0;s.run();m=analyse(s.vector('time'),s.vector('v('+recv+')'),p)
            out.append(dict(variant=variant,corner=corner,direction=direction,carrier_Z_ohm=160,**m,source_max_V=float(s.vector('v('+source+')').max()),switch_max_V=max(float(s.vector('v('+n+')').max()) for n in ('swa0','swb0'))))
(H/'inner-layer-stress.json').write_text(json.dumps({'results':out,'scope':'Representative longestCLK A/B(shared)/C, uniform160ohm carrier stress; external unknown traces85ohm. Does not replace actual layer-specific field extraction.'},indent=2)+'\n')
print(out)
