"""Compare 220/330/470ohm in all 15 physical channels, both directions.

Archives GPIO source/receiver and bus-switch external pin excursions separately.
Electrically identical A/B extracted geometries reuse one solved waveform.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from ngspice_shared import Spice
from run_waveforms import deck,analyse,PARAMS

HERE=Path(__file__).resolve().parent
RAW=Path('D:/tmp/carrier-parallel-models')
data=json.loads((HERE/'extracted-paths.json').read_text())
cache={};results=[];s=Spice()
for variant,b in data.items():
    for signal,geom in b['signals'].items():
        signature=json.dumps(geom,sort_keys=True)
        for corner in ('fast','controlled','slow'):
            for direction in ('write','read'):
                for resistor in (220,330,470):
                    key=(signature,corner,direction,resistor)
                    if key not in cache:
                        p=PARAMS[corner];lines,recv=deck(geom,p,direction,resistor)
                        source='host' if direction=='write' else 'core'
                        saved={'GPIO_receiver':recv,'GPIO_driver_pad':source,'switch_host_pin':'swa0','switch_core_pin':'swb0','resistor_host_pin':'iso','socket_core':'socket_b'}
                        lines=[l for l in lines if not l.startswith('.save')]
                        lines.insert(-1,'.save v(drive) '+' '.join('v('+n+')' for n in set(saved.values())))
                        s.messages.clear();assert s.load(lines)==0;s.run()
                        t=s.vector('time');wave={k:s.vector('v('+n+')') for k,n in saved.items()}
                        assert t[-1]>=200e-9
                        row={'corner':corner,'direction':direction,'Rseries_ohm':resistor,**analyse(t,wave['GPIO_receiver'],p),
                             'pin_extrema_V':{k:{'min':float(v.min()),'max':float(v.max())} for k,v in wave.items()}}
                        row['receiver_voltage_ok']=row['max_V']<=3.6 and row['min_V']>=-.3
                        row['source_voltage_ok']=row['pin_extrema_V']['GPIO_driver_pad']['max']<=3.6 and row['pin_extrema_V']['GPIO_driver_pad']['min']>=-.3
                        row['switch_voltage_ok']=all(row['pin_extrema_V'][k]['max']<=5.5 and row['pin_extrema_V'][k]['min']>=-.5 for k in ('switch_host_pin','switch_core_pin'))
                        cache[key]=row
                        if signal=='CLK' and corner in ('fast','controlled') and resistor==330:
                            stem=variant+'-qualify-'+direction+'-'+corner+'-'+str(resistor)
                            (RAW/(stem+'.cir')).write_text('\n'.join(lines)+'\n')
                            idx=np.flatnonzero(t<=100e-9)[::5]
                            np.savetxt(RAW/(stem+'.csv'),np.column_stack([t[idx],*[v[idx] for v in wave.values()]]),delimiter=',',header='time_s,'+','.join(wave),comments='')
                    results.append(dict(variant=variant,signal=signal,**cache[key]))
        print(variant,signal,'unique solves',len(cache),flush=True)
    (HERE/'resistor-qualification.json').write_text(json.dumps({'results':results,'unique_spice_solves':len(cache),'physical_channel_cases':len(results),'criterion':'GPIO -0.3..3.6V, switch -0.5..5.5V in unclamped sensitivity; 5% settling before 250ns setup/hold guard; not full GPIO IBIS qualification','parameters':PARAMS},indent=2)+'\n')
print('done',len(results),len(cache))
