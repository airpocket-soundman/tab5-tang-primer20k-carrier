from pathlib import Path
import argparse,json,time,hashlib
import os
import numpy as np
from ngspice_shared import Spice
from power_models import make
H=Path(__file__).resolve().parent
RAW=Path('D:/tmp/carrier-power-transient-lcsc');RAW.mkdir(exist_ok=True)

def run(c):
    name=c['name'];lines=make(c);deck=H/'models'/(name+'.cir');deck.write_text('\n'.join(lines)+'\n')
    os.environ['NGSPICE_STREAM_LOG']=str(RAW/(name+'.live.log'))
    s=Spice();s.command('version');start=time.time();ret=s.load(lines,pspice=True)
    if ret: s.log(H/'results'/(name+'.log'));raise RuntimeError(('load',name,ret))
    s.run();s.log(RAW/(name+'.log'))
    data={k:s.vector(k) for k in ('time','v(vout)','v(vcore)','v(v33raw)','v(vin)','v(en)','i(l1)','i(vsource)')}
    if c.get('model')!='vendor':data['v(active)']=s.vector('v(active)')
    np.savez_compressed(RAW/(name+'.npz'),**data)
    t=data['time'];v=data['v(vcore)'];v33=data['v(v33raw)'];valid=(t>=c.get('settled_start',.015))&(data['v(vin)']>=10.3)
    if 'variant' in c:
        src=next(l for l in lines if l.startswith('Vsource '))
        if 'PWL(' in src:
            def val(x):
                for sf,mul in [('m',1e-3),('u',1e-6),('n',1e-9)]:
                    if x.endswith(sf):return float(x[:-1])*mul
                return float(x)
            pts=list(map(val,src.split('PWL(')[1].split(')')[0].split()))
            source=np.interp(t,pts[::2],pts[1::2])
        else:source=np.full_like(t,float(src.split()[-1]))
        valid=(t>=c.get('settled_start',.015))&(source>=11.4-1e-4)&(source<=12.6+1e-4)
    if c.get('switch_off'):
        m=c.get('time_mult',1);valid&=((t<.030*m)|(t>.036*m+.011))
    metrics={'name':name,'parameters':c,'ngspice_return':ret,'samples':len(t),'runtime_s':time.time()-start,'tstop_s':float(t[-1]),'vcore_max_V':float(v.max()),'vout_max_V':float(data['v(vout)'].max()),'v33_max_V':float(v33.max()),'vcore_min_valid_input_V':float(v[valid].min()) if valid.any() else None,'vcore_max_valid_input_V':float(v[valid].max()) if valid.any() else None,'v33_min_valid_input_V':float(v33[valid].min()) if valid.any() else None,'v33_max_valid_input_V':float(v33[valid].max()) if valid.any() else None,'raw_path':str(RAW/(name+'.npz')),'warnings':[m for m in s.messages if 'warning' in m.lower() or 'error' in m.lower()],'max_inductor_current_A':float(data['i(l1)'].max())}
    metrics['within_numeric_voltage_limits']=bool(valid.any() and metrics['vcore_min_valid_input_V']>=4.5 and metrics['vcore_max_valid_input_V']<=5.5 and metrics['v33_min_valid_input_V']>=3.135 and metrics['v33_max_valid_input_V']<=3.465) if c.get('include_ldo',True) else bool(valid.any() and metrics['vcore_min_valid_input_V']>=4.5 and metrics['vcore_max_valid_input_V']<=5.5)
    metrics['complete']=bool(t[-1]>=c.get('stop',.045)*.999)
    metrics['deck_sha256']=hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest()
    metrics['model_code_sha256']=hashlib.sha256((H/'power_models.py').read_bytes()).hexdigest()
    metrics['TI_model_sha256']=hashlib.sha256((H/'models/TPS5430_TRANS.LIB').read_bytes()).hexdigest()
    (H/'results'/(name+'.json')).write_text(json.dumps(metrics,indent=2)+'\n')
    # Compact representative CSV; full adaptive sample arrays remain outside Git.
    ix=np.unique(np.linspace(0,len(t)-1,min(4000,len(t))).astype(int))
    keys=list(data)
    np.savetxt(H/'results'/(name+'.csv'),np.column_stack([data[k][ix] for k in keys]),delimiter=',',header=','.join(keys),comments='')
    print(json.dumps({k:metrics[k] for k in ('name','complete','samples','runtime_s','vout_max_V','vcore_min_valid_input_V','v33_min_valid_input_V','v33_max_V','within_numeric_voltage_limits')}),flush=True)
    return metrics

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('case');args=ap.parse_args()
    if Path(args.case).exists():c=json.loads(Path(args.case).read_text())
    else:c=dict(name=args.case)
    run(c)
