"""Final680ohm all-signal re-evaluation after port-capacitance correction.

The active channel model is linear (RLC and fixedRon). A held rising step gives
the corresponding falling excursion by superposition about its steady rail.
This avoids hiding ringing in a too-short half-period observation window.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from run_waveforms import deck,PARAMS
from ngspice_shared import Spice
H=Path(__file__).resolve().parent;data=json.loads((H/'extracted-paths.json').read_text())
variant=sys.argv[1];s=Spice();rows=[]
corners={
 'fast_IBIS_min':dict(PARAMS['fast'],cio=3.062e-12),
 'fast_IBIS_typ':dict(PARAMS['fast'],cio=3.467e-12),
 'fast_IBIS_max':dict(PARAMS['fast'],cio=4.473e-12),
 'controlled_IBIS':dict(PARAMS['controlled'],cio=3.467e-12),
 'slow_Cio_bound':dict(PARAMS['slow'],cio=11e-12)}
for sig,g in data[variant]['signals'].items():
    for corner,p in corners.items():
        for direction in ('write','read'):
            lines,recv=deck(g,p,direction,680,10e-6,1)
            source='host' if direction=='write' else 'core'
            lines=[l for l in lines if not l.startswith('.save')]
            lines=[l if not l.startswith('.tran') else '.tran 20p 220n 0 20p' for l in lines]
            saved={'GPIO_receiver':recv,'GPIO_driver_pad':source,'switch_host_pin':'swa0','switch_core_pin':'swb0'}
            lines.insert(-1,'.save '+' '.join('v('+v+')' for v in saved.values()))
            s.messages.clear();assert s.load(lines)==0;s.run();t=s.vector('time');wave={k:s.vector('v('+n+')') for k,n in saved.items()}
            assert t[-1]>=219e-9
            ext={k:{'max':float(v.max()),'min_rising':float(v.min()),'min_falling_by_linearity':float(min(0,p['vdd']-v.max()))} for k,v in wave.items()}
            bad=np.flatnonzero((t>=10e-9)&(np.abs(wave['GPIO_receiver']-p['vdd'])>.05*p['vdd']))
            settled=abs(wave['GPIO_receiver'][-1]-p['vdd'])<=.05*p['vdd']
            assert settled,(variant,sig,corner,direction)
            settle=(t[bad[-1]]-10e-9)*1e9 if len(bad) else 0
            rows.append(dict(variant=variant,signal=sig,corner=corner,direction=direction,Rseries_ohm=680,port_C_pF=p['cio']*1e12,settle_5percent_ns=float(settle),pin_extrema_V=ext,receiver_voltage_ok=ext['GPIO_receiver']['max']<=3.6 and ext['GPIO_receiver']['min_falling_by_linearity']>=-.3,source_voltage_ok=ext['GPIO_driver_pad']['max']<=3.6 and ext['GPIO_driver_pad']['min_falling_by_linearity']>=-.3,switch_design_envelope_ok=all(ext[n]['max']<=5.5 and ext[n]['min_falling_by_linearity']>=-.5 for n in ('switch_host_pin','switch_core_pin'))))
            if sig=='CLK' and corner in ('fast_IBIS_typ','controlled_IBIS','slow_Cio_bound'):
                stem=variant+'-680-'+direction+'-'+corner
                idx=np.arange(0,len(t),10)
                np.savetxt(H/(stem+'.csv'),np.column_stack([t[idx],*[v[idx] for v in wave.values()]]),delimiter=',',header='time_s,'+','.join(wave),comments='')
                (H/(stem+'.cir')).write_text('\n'.join(lines)+'\n')
    print(variant,sig,'completed',len(rows),flush=True)
    report={'variant':variant,'sourcePCBhash':data[variant]['sourcePCBhash'],'results':rows,'parameters':corners,'scope':'All15 signals, both directions,680ohm; corrected per-port IBIS Ccomp plus package. Linear step-response model; falling extrema deduced by superposition. Not a fullGPIO IBIS or physicalDDR3 verification.'}
    (H/(variant+'-final680.json')).write_text(json.dumps(report,indent=2)+'\n')
