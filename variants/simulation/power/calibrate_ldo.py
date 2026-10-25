"""Fit check against XC6206P302 1uF/1->40mA typical figure, not production bound."""
from pathlib import Path
import numpy as np,json,os
from ngspice_shared import Spice
from power_models import ldo,safe_functions
H=Path(__file__).resolve().parent
raw=Path('D:/tmp/carrier-power-transient')
c=dict(c33=1e-6,c10_effective=1e-6,ldo_ref_mult=3/3.3,ldo_trace_L=1e-9,ldo_trace_R=.001)
lines=['XC6206 family 3V typical-curve calibration','Vsource vout 0 4']+ldo(c)
lines=[('Vldocurrent ldocurrent 0 PWL(0 .001 2m .001 2.001m .040 4m .040 4.001m .001 6m .001)' if l.startswith('Vldocurrent') else l) for l in lines]
lines+=['.ic V(ldo_vin)=4 V(c10internal)=4 V(passcmd)=.001 V(v33raw)=3 V(c33int)=3 V(integ)=.001','.options method=gear reltol=.002 abstol=1n rshunt=1e12','.save v(v33raw) v(ldocurrent)','.tran 1u 6m 0 1u uic','.end']
lines=safe_functions(lines)
(H/'models/calibration-XC6206.cir').write_text('\n'.join(lines)+'\n')
os.environ['NGSPICE_STREAM_LOG']=str(raw/'calibration-XC6206.live.log')
s=Spice();s.load(lines,pspice=True);s.run();s.log(raw/'calibration-XC6206.log')
t=s.vector('time');v=s.vector('v(v33raw)');i=s.vector('v(ldocurrent)')
np.savez_compressed(raw/'calibration-XC6206.npz',time=t,vout=v,load=i)
np.savetxt(H/'results/calibration-XC6206.csv',np.column_stack([t,v,i])[::3],delimiter=',',header='time_s,vout_V,load_A',comments='')
result={'model':'Non-vendor PI/pass-current fit to typical XC6206P302 family plot, 3.0V; 3.3V part not directly characterized','vout_min':float(v[(t>=.002)&(t<.004)].min()),'vout_max_after_release':float(v[t>=.004].max()),'approximate_reference_plot_min_V':2.45,'approximate_reference_plot_peak_V':3.5,'reference_plot_timescale_ms_per_div':1,'minimum_time_s':float(t[np.argmin(v)]),'complete':bool(t[-1]>=.006*.999),'calibration_status':'approximate typical-curve agreement only; no transistor/control-corner validation'}
(H/'results/calibration-XC6206.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
