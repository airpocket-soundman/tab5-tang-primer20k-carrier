from pathlib import Path
import json,itertools,numpy as np
HERE=Path(__file__).resolve().parent
ns={'__file__':str(HERE/'hpd_npn_sim.py')};exec((HERE/'hpd_npn_sim.py').read_text().split('rows=[]')[0],ns)
sp=ns['Spice']();rows=[]
for rail,hpd,load,tol in itertools.product((3.234,3.366),(None,0,2,2.4,5.5),(-10e-6,10e-6),(-.01,.01)):
 d=ns['circuit'](rail,hpd,1000,20,tol,load,100e-9,False,True,8e-12,5e-12)
 d=[s.replace('pin','buf') for s in d];d=[s.replace('Cpin buf','Cpin pin').replace('Dupper buf','Dupper pin').replace('I_input buf','I_input pin') for s in d];d.insert(-1,f'R52 buf pin {10000*(1+tol)}')
 sp.load(d);assert sp.run()==0
 pin=float(sp.vector('v(pin)')[0]);active=hpd is not None and hpd>=2
 rows.append(dict(rail_V=rail,HPD_V=hpd,GPIO_sink_A=load,R_tolerance=tol,pin_V=pin,active=active,pass_internal=pin<=.8 if active else pin>=2))
summary={'scope':'Powered DC with 10k series R52 between HPD_BUF filter and FPGA input','generic_model':True,'cases':len(rows),'misses':sum(not r['pass_internal'] for r in rows),'minimum_high_V':min(r['pin_V'] for r in rows if not r['active']),'maximum_low_V':max(r['pin_V'] for r in rows if r['active']),'results':rows}
(HERE/'hpd/series10k_powered.json').write_text(json.dumps(summary,indent=2)+'\n');print({k:v for k,v in summary.items() if k!='results'})
