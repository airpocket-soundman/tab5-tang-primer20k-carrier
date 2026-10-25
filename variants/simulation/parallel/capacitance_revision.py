"""Resolve I/O capacitance interpretation using actual TI IBIS port facts.

The IBIS per-port C_comp2.86/3.15/4.03pF plus corresponding PW package C
0.202/0.317/0.443pF is different from placing the entire ON-port11pF
datasheet bound on both ports. Both interpretations are retained as sweeps.
"""
from pathlib import Path
import json
import numpy as np
from run_waveforms import deck,PARAMS
from ngspice_shared import Spice
H=Path(__file__).resolve().parent;d=json.loads((H/'extracted-paths.json').read_text());s=Spice();out=[]
for variant in ('lite-a-dual','lite-c-dnp'):
    for rr in (470,680):
        for direction in ('write','read'):
            for corner in ('fast','controlled','slow'):
                caps=(3.062,3.467,4.473) if corner!='slow' else (4.473,11)
                for cap in caps:
                    p=dict(PARAMS[corner],cio=cap*1e-12)
                    period=1e-6 if corner=='slow' else 200e-9
                    lines,recv=deck(d[variant]['signals']['CLK'],p,direction,rr,period,1)
                    source='host' if direction=='write' else 'core'
                    lines=[x for x in lines if not x.startswith('.save')]
                    if corner=='slow':lines=[x if not x.startswith('.tran') else '.tran 100p 1.01u 0 100p' for x in lines]
                    lines.insert(-1,f'.save v({recv}) v({source}) v(swa0) v(swb0)')
                    assert s.load(lines)==0;s.run();t=s.vector('time');v=s.vector('v('+recv+')')
                    rise=(t>=10e-9)&(t<10e-9+period*.4)
                    bad=np.flatnonzero(np.abs(v[rise]-p['vdd'])>.05*p['vdd'])
                    settled=abs(v[rise][-1]-p['vdd'])<=.05*p['vdd']
                    settle=(t[rise][bad[-1]]-10e-9)*1e9 if settled and len(bad) else 0 if settled else None
                    row=dict(variant=variant,Rseries_ohm=rr,corner=corner,direction=direction,port_C_pF=cap,receiver_max_V=float(v.max()),receiver_min_V=float(v.min()),source_max_V=float(s.vector('v('+source+')').max()),source_min_V=float(s.vector('v('+source+')').min()),switch_max_V=max(float(s.vector('v('+n+')').max()) for n in ('swa0','swb0')),switch_min_V=min(float(s.vector('v('+n+')').min()) for n in ('swa0','swb0')),settle_ns=float(settle) if settle is not None else None,settled_in_window=bool(settled))
                    if corner=='slow':
                        row['high_250ns_V']=float(np.interp(260e-9,t,v));row['low_750ns_V']=float(np.interp(760e-9,t,v))
                    out.append(row)
        (H/'capacitance-revision.json').write_text(json.dumps({'results':out,'scope':'Representative longestCLK A/B(shared)/C. I/O per-port capacitance taken from legacyTI IBIS facts plus package. Strong-fast source remains uncalibrated, not an actualGPIO absolute-limit certification.'},indent=2)+'\n')
        print(variant,rr,'done',flush=True)
(H/'capacitance-revision.json').write_text(json.dumps({'results':out,'scope':'Representative longestCLK A/B(shared)/C. I/O per-port capacitance taken from legacyTI IBIS facts plus package. Strong-fast source remains uncalibrated, not an actualGPIO absolute-limit certification.'},indent=2)+'\n')
print('completed',len(out))
