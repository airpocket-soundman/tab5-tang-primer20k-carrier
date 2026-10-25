"""Compare a single Basic 510R against 499R with the identical routed geometry.

Relative sensitivity only. This is not HDMI compliance or calibrated whole-board
3D validation. Both ends include the baseline Core/connector approximations.
"""
from pathlib import Path
import json
import itertools
import numpy as np
import tmds_sparam as sp

HERE=Path(__file__).resolve().parent
sp.tc.load()
results={}
for tag,p,n in sp.tc.PAIRS:
    row={}
    for resistance in (494.01,499.,503.99,504.9,510.,515.1):
        sp.R_BIAS=resistance
        m=sp.channel(tag,p,n)
        row[str(resistance)]=sp.metrics(m)
    sp.R_BIAS=499.
    ref=sp.curves(sp.channel(tag,p,n))
    sp.R_BIAS=510.
    new=sp.curves(sp.channel(tag,p,n))
    # Preserve raw dictionaries; metric definitions belong to the original model.
    row['curve_comparison']={str(k):float(np.max(np.abs(np.asarray(new[k])-np.asarray(ref[k])))) for k in range(len(ref))}
    results[tag]=row
dc=[]
for supply,termination,r in itertools.product((3.135,3.465),(45.,55.),(504.9,515.1)):
    voltage=supply*r/(r+termination)
    dc.append(dict(sink_pullup_V=supply,sink_termination_ohm=termination,bias_ohm=r,node_V=voltage,bias_W=voltage**2/r))
report=dict(scope=__doc__,source_geometry='preserved d93af0b layout; actual new layouts must be checked separately',
            parts={'0402':'JLC C25123 Basic 510R 1% 62.5mW','0603':'JLC C23193 Basic 510R 1% 100mW'},
            nominal_499_node_V=3.3*499/(499+50),nominal_510_node_V=3.3*510/(510+50),
            dc_sensitivity=dc,channels=results)
(HERE/'sensitivity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({tag:r['curve_comparison'] for tag,r in results.items()},indent=1))
print('maximum bias dissipation W:',max(c['bias_W'] for c in dc))
