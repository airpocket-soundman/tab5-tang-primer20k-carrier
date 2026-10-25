"""Incremental loading sensitivity of NC DDR3 pins, not a DDR3-controller test.

Core schematic exposes RST/A11/A5 at SODIMM87/99/111. They are unconnected
in the carrier, but the contact and land still add a load. The official XLS
does NOT contain the internal DDR3 net lengths: do not invent their routing.
Here a local Thevenin source drives a series-L/contact-R + pad-C shunt stub.
All L/C ranges except the parallel-plate pad estimate are sensitivity choices.
"""
import itertools
import json
from pathlib import Path
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
cpad=8.854187817e-12*4.4*(.35e-3*2e-3)/(.2104e-3)
t=np.linspace(0,3e-9,3001)
rows=[];selected=[]
for Rs,L,C,tr in itertools.product((10.,25.,50.),(.5e-9,1e-9,3e-9),(cpad,.3e-12,1e-12),(.15e-9,.3e-9,.6e-9)):
    Rcontact=.05;tau=tr/np.log(9)
    num=[L*C,Rcontact*C,1.]
    den=np.polymul([L*C,(Rcontact+Rs)*C,1.],[tau,1.])
    _,out=signal.step(signal.TransferFunction(num,den),T=t)
    baseline=1-np.exp(-t/tau)
    delta=(out-baseline)*1.5
    at125=float(abs(np.interp(1.25e-9,t,delta)))
    tail=np.maximum.accumulate(abs(delta)[::-1])[::-1]
    good=np.flatnonzero(tail<.015)
    settling=float(t[good[0]]) if len(good) else None
    row=dict(R_thevenin_ohm=Rs,L_contact_H=L,C_stub_F=C,rise_10_90_s=tr,incremental_peak_error_V=float(max(abs(delta))),incremental_error_at_half_400MHz_cycle_V=at125,extra_error_settles_below_15mV_s=settling,selected_case_pass=bool(at125<.015))
    rows.append(row)
    if L==3e-9 and C==1e-12 and tr==.15e-9:
        selected.append((row,t,out*1.5,baseline*1.5))
fig,ax=plt.subplots(figsize=(8,4.5))
for r,tt,y,base in selected:ax.plot(tt*1e9,y,label=f'Rs={r["R_thevenin_ohm"]:.0f}ohm, L3nH/C1pF')
ax.plot(t*1e9,selected[0][3],'k--',label='no added contact load')
ax.axvline(1.25,color='r',lw=.8,label='half of 400MHz CA clock')
ax.set(xlabel='time ns',ylabel='local node V',title='NC socket-stub incremental sensitivity; not complete Core DDR3 SI')
ax.grid(alpha=.2);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(HERE/'ddr_nc_loading.png',dpi=140)
np.savetxt(HERE/'ddr_nc_loading_wave.csv',np.column_stack([t]+[y for _,_,y,_ in selected]+[selected[0][3]]),delimiter=',',header='t_s,Rs10_V,Rs25_V,Rs50_V,no_stub_V',comments='')
out=dict(status='conditional_pass_selected_incremental_loads' if all(r['selected_case_pass'] for r in rows) else 'uncertain',cases=len(rows),misses=sum(not r['selected_case_pass'] for r in rows),pad_parallel_plate_C_F=cpad,threshold_incremental_error_at_1p25ns_V=.015,max_incremental_error_at_1p25ns_V=max(r['incremental_error_at_half_400MHz_cycle_V'] for r in rows),results=rows,full_DDR3_validation='not performed: no internal routing stackup/impedance, exact buffer+DRAM models or integrated target controller/bitstream',limits=__doc__)
(HERE/'ddr_nc_loading.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('results','limits')},indent=1))
