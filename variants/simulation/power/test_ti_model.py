from pathlib import Path
import time
import numpy as np
from ngspice_shared import Spice
H=Path(__file__).resolve().parent
lines=['TI TPS5430 unencrypted ngspice compatibility test',
 '.include "'+(H/'models/TPS5430_TRANS.LIB').as_posix()+'"',
 '.param temper=25',
 'V1 src 0 PWL(0 0 10u 0 20u 12)',
 'RS src vin 0.1', 'CIN vin 0 20u',
 'Rena vin en 100k','Renb en 0 15k',
 'XU boot en 0 nc nc1 0 ph vin fb TPS5430_TRANS MODE=0',
 'Cboot boot ph 10n','Rind ph li .045','L1 li out 15u',
 'D1 0 ph DSS54', '.model DSS54 D(Is=50u Rs=.02 N=1.2 Cjo=200p Tt=8n Bv=40 Ibv=1m)',
 'RC out cp .04','CO cp 0 220u',
 'Rtop out fb 10k','Rbot fb 0 3246.43384',
 'Rload out 0 10',
 '.options reltol=.003 abstol=1n vntol=10u itl4=200 method=gear',
 '.save v(out) v(vin) v(ph) v(en) i(L1)',
 '.tran 100n 1m 0 100n uic','.end']
(H/'models/ti_compatibility_test.cir').write_text('\n'.join(lines)+'\n')
s=Spice();s.command('version');t=time.time();load=s.load(lines,pspice=True);print('load',load,flush=True)
s.log(H/'results/ti_compatibility_load.log')
if any('error' in x.lower() for x in s.messages):print('\n'.join(s.messages[-20:]),flush=True)
code=s.run();s.log(H/'results/ti_compatibility.log');print('run',code,'seconds',time.time()-t,flush=True)
try:
 tt=s.vector('time');out=s.vector('v(out)');print('samples',len(tt),'range',out.min(),out.max());np.savez(H/'results/ti_compatibility.npz',time=tt,out=out)
except Exception as e:print(e,'\n'.join(s.messages[-20:]))
