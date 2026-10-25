from pathlib import Path
import sys,json,numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'power'));from ngspice_shared import Spice
ns={'__file__':str(HERE/'hpd_npn_sim.py')};exec((HERE/'hpd_npn_sim.py').read_text().split('rows=[]')[0],ns)
sp=Spice();rows=[]
for resistor in (.1,1000,4700,10000):
 for fall in (1e-6,1e-3):
  deck=ns['circuit'](3.366,None,1000,20,.01,0,100e-9,True,True,8e-12,5e-12)
  deck=[s.replace('pin','buf') for s in deck]
  deck=[s.replace('Cpin buf','Cpin pin').replace('Dupper buf','Dupper pin').replace('Vcore core 0 3.135',f'Vcore core 0 PWL(0 3.135 1m 3.135 {1e-3+fall} 0 12m 0)') for s in deck]
  deck.insert(-1,f'R52 buf pin {resistor}')
  name=f'offcore-series-{resistor:g}-fall-{fall:g}'
  (HERE/'hpd'/f'{name}.cir').write_text('\n'.join(deck)+'\n')
  sp.load(deck);assert sp.run()==0
  t=sp.vector('time');pin=sp.vector('v(pin)');buf=sp.vector('v(buf)');inj=np.maximum(0,sp.vector('i(vcore)'))
  use=t>1e-3
  rows.append(dict(series_R_ohm=resistor,core_fall_s=fall,local_rail_V=3.366,postfall_injection_peak_A=float(inj[use].max()),postfall_injection_final_A=float(inj[-1]),GPIO_final_V=float(pin[-1]),buffer_final_V=float(buf[-1])))
  sel=np.arange(0,len(t),max(1,len(t)//2000));np.savetxt(HERE/'hpd'/f'{name}.csv',np.column_stack((t[sel],buf[sel],pin[sel],inj[sel])),delimiter=',',header='t_s,buffer_V,GPIO_V,injection_A',comments='')
summary={'status':'uncertain_no_vendor_injection_rating','scope':'Independent Core-bank fall while local3V3 remains powered; generic assumed GPIO diode, HPD unplugged/inactive worst charged filter','results':rows,'recommendation':'Add 10k between filtered collector node and Core input to limit stored-capacitor discharge. This reduces but does not eliminate local3V3-to-off-Core DC injection (~50uA). No absent-rail guarantee without bank-referenced pullup or qualified fail-safe buffer.','original_off_core_18mV_scope':'Both Core and local rails zero only'}
(HERE/'hpd/offrail_sensitivity.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=1))
