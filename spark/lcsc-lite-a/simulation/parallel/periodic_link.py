"""Actual periodic 1/10/20/40MHz transient samples with selected680ohm."""
from pathlib import Path
import json
import numpy as np
from run_waveforms import deck,PARAMS
from ngspice_shared import Spice

HERE=Path(__file__).resolve().parent;RAW=Path('D:/tmp/carrier-parallel-models')
paths=json.loads((HERE/'extracted-paths.json').read_text());s=Spice();results=[]
for variant in ('spark-lite-a',):
    signal=paths[variant]['signals']['CLK']
    for freq in (1000000,10000000,20000000,40000000):
        period=1/freq
        for corner in ('fast','slow'):
            for direction in ('write','read'):
                p=dict(PARAMS[corner],cio=(3.467e-12 if corner=='fast' else 11e-12));lines,recv=deck(signal,p,direction,680,period,3)
                lines=[l if not l.startswith('.tran') else f'.tran 100p {3*period+10e-9} 0 100p' for l in lines]
                assert s.load(lines)==0;s.run();t=s.vector('time');v=s.vector('v('+recv+')')
                thresholds=(2.,.8) if direction=='write' else (.75*3.465,.25*3.135)
                highs=[float(np.interp(10e-9+(i+.25)*period,t,v)) for i in range(3)]
                lows=[float(np.interp(10e-9+(i+.75)*period,t,v)) for i in range(3)]
                ok=min(highs)>=thresholds[0] and max(lows)<=thresholds[1]
                results.append(dict(variant=variant,freq_Hz=freq,corner=corner,direction=direction,VIH_required_V=thresholds[0],VIL_required_V=thresholds[1],sample_high_min_V=min(highs),sample_low_max_V=max(lows),threshold_ok=ok))
                if freq==1000000:
                    stem=variant+'-1MHz-'+direction+'-'+corner
                    idx=np.arange(0,len(t),10)
                    np.savetxt(HERE/(stem+'.csv'),np.column_stack([t[idx],v[idx]]),delimiter=',',header='time_s,receiver_V',comments='')
                    (HERE/(stem+'.cir')).write_text('\n'.join(lines)+'\n')
(HERE/'periodic-results.json').write_text(json.dumps({'results':results,'sample_phase':'data launched at previous falling edge; sample 250ns after rising/falling transition for 1MHz, corresponding quarter-cycle points for sensitivity rates','scope':'Periodic physical-line model, not proof of RTL or DMA at sensitivity rates; A/B identical geometry reuse A results'},indent=2)+'\n')
assert all(r['threshold_ok'] for r in results if r['freq_Hz']==1000000)
print(json.dumps(results,indent=1))
