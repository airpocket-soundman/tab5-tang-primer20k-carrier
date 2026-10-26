"""Illustrative Core/ESD/socket sensitivity on the extracted A/B carrier.

Socket L/C points are assumptions, not manufacturer limits or calibration.
Results cannot prove all physically possible channels are covered.
"""
import itertools
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
folder=ROOT/'variants/validation/lite-a-dual-channel'
sys.path.insert(0,str(folder))
import tmds_sparam as sp
sp.tc.load();sp.R_BIAS=510.
rows=[]
for core_z,esd_pf,socket in itertools.product((85.,100.,115.),(.2,.35,.5),((0.,0.),(1.,.3),(3.,1.))):
    pair=[]
    for tag,p,n in sp.tc.PAIRS:
        m=sp.metrics(sp.channel(tag,p,n,core_z=core_z,esd_cd=esd_pf*1e-12,socket_l=socket[0]*1e-9,socket_c=socket[1]*1e-12))
        pair.append(dict(pair=tag,**m))
    worst=max(pair,key=lambda m:m['s11_max_1500'])
    rows.append(dict(core_differential_ohm=core_z,esd_differential_pF=esd_pf,socket_differential_nH=socket[0],socket_differential_pF=socket[1],worst_pair=worst['pair'],worst_sdd11_db_below_1p5GHz=worst['s11_max_1500'],all_below_internal_minus10dB=worst['s11_max_1500']<=-10,channels=pair))
report=dict(scope=__doc__,bias_ohms=510,examples_not_a_guaranteed_bound=True,internal_reflection_target_db=-10,conditions=len(rows),target_misses=sum(not r['all_below_internal_minus10dB'] for r in rows),cases=rows)
(folder/'uncertainty.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('scope','cases')}))
