"""Proper two-junction NPN SPICE sensitivity for active-low HPD proposal.

Generic MMBT3904-like Gummel-Poon model, not a manufacturer-calibrated model.
Forced gain/threshold margins are cross-checked independently of this fit.
Root owns CAD; this file only evaluates the proposed circuit.
"""
import csv
import itertools
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'power'))
from ngspice_shared import Spice
OUT=HERE/'hpd';OUT.mkdir(exist_ok=True)
sp=Spice()

def circuit(rail,hpd,rs,beta,tol,load,cfilter=0,transient=False,clamp=True,cjc=4e-12,cpin=10e-12):
    core=0 if rail==0 else 3.135
    lines=['Active-low HPD proposal: NPN buffer',f'Vrail v33 0 {rail}',f'Vcore core 0 {core}',
        f'R40 hpd base {47000*(1+tol)}',f'R41 base 0 {100000*(1-tol)}',f'R51 v33 pin {47000*(1+tol)}',
        'Q5 pin base 0 Q3904',f'.model Q3904 NPN(IS=1e-14 BF={beta} BR=1 VAF=100 IKF=.1 RB=10 RC=1 RE=1 CJE=10p CJC={cjc} TF=.4n TR=100n)',
        'R_esd hpd 0 5meg',f'Cpin pin 0 {cpin}',f'I_input pin 0 {load if rail else 0}',
        'Bcbo pin base I=50n*tanh(max(v(pin,base),0)/.1)',
        '.model GPIOclamp D(IS=1e-9 N=1 RS=1)',
        '.options reltol=1e-5 abstol=1e-12 vntol=1e-7',
        '.save all']
    if clamp:lines += ['Dupper pin core GPIOclamp','.save @dupper[id]']
    if cfilter:lines.append(f'Cfilter pin 0 {cfilter}')
    if hpd is not None:
        lines += ['Vh source 0 '+('PULSE(0 5.5 100u 10n 10n 2m 100m)' if transient else str(hpd)),f'Rsource source hpd {rs}']
    if transient:lines.append('.tran 1u 12m 0 1u')
    else:lines.append('.op')
    return lines+['.end']

rows=[]
for rail,hpd,rs,beta,tol,load in itertools.product((0,3.234,3.3,3.366),(None,0,2.0,2.4,5.5),(1,1000),(20,40,300),(-.01,.01),(0,10e-6)):
    deck=circuit(rail,hpd,rs,beta,tol,load)
    sp.load(deck);assert sp.run()==0
    pin=float(sp.vector('v(pin)')[0]);base=float(sp.vector('v(base)')[0]);line=float(sp.vector('v(hpd)')[0])
    injected=max(0,float(sp.vector('i(vcore)')[0]))
    expected='off-rail-low' if rail==0 else ('active-low' if hpd is not None and hpd>=2 else 'inactive-high')
    ok=(pin<=.3 and injected<10e-6) if rail==0 else ((pin<=.8) if expected=='active-low' else pin>=2)
    ok=ok and -.3<=pin<=3.6
    rows.append(dict(rail_V=rail,input_HPD_V=hpd,source_R_ohm=rs,beta=beta,R_tolerance=tol,GPIO_sink_A=load,drain_HPD_V=line,base_V=base,FPGA_pin_V=pin,core_injection_A=injected,expected=expected,ok=ok))
with (OUT/'dc_sweep.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('DC',len(rows),'misses',sum(not r['ok'] for r in rows),flush=True)
tran=[]
fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
for rail,cfilter in itertools.product((0,3.3),(0,100e-9)):
    deck=circuit(rail,5.5,1000,20,.01,10e-6,cfilter,True,True,cjc=8e-12,cpin=5e-12)
    name=f'rail-{rail}-C-{cfilter:g}'
    (OUT/(name+'.cir')).write_text('\n'.join(deck)+'\n')
    sp.load(deck);assert sp.run()==0
    t=sp.vector('time');pin=sp.vector('v(pin)');hpd=sp.vector('v(hpd)');inj=np.maximum(sp.vector('i(vcore)'),0)
    transient=dict(rail_V=rail,Cfilter_F=cfilter,pin_max_V=float(pin.max()),pin_min_V=float(pin.min()),core_injection_peak_A=float(inj.max()),core_injected_charge_C=float(np.trapezoid(inj,t)))
    stable_low=(t>.3e-3)&(t<1.8e-3)
    stable_high=(t>10e-3)
    transient['active_low_max_V']=float(pin[stable_low].max());transient['released_high_min_V']=float(pin[stable_high].min())
    tran.append(transient)
    # Preserve switching detail and a decimated long waveform, not every solver row.
    use=np.unique(np.r_[np.arange(0,len(t),max(len(t)//2400,1)),np.flatnonzero((t>95e-6)&(t<120e-6))])
    np.savetxt(OUT/(name+'.csv'),np.column_stack((t[use],hpd[use],pin[use],inj[use])),delimiter=',',header='t_s,HPD_line_V,FPGA_pin_V,core_injection_A',comments='')
    ax=axes[0 if rail else 1];ax.plot(t*1e3,pin,label='100nF filter' if cfilter else 'no filter')
for ax in axes:
    ax.axhline(.8,color='r',lw=.5);ax.axhline(2,color='r',lw=.5);ax.set_ylabel('F_HPD V');ax.legend();ax.grid(alpha=.2)
axes[0].set_title('Powered rail, NPN active-low HPD / generic weak-gain + leakage corner')
axes[1].set_title('Core off: capacitive feedthrough and clamped injection sensitivity')
axes[1].set_xlabel('time ms');fig.tight_layout();fig.savefig(OUT/'hpd_transient.png',dpi=140);plt.close(fig)
summary=dict(status='conditional_pass_with_100nF_filter' if all(r['ok'] for r in rows) else 'fail',recommended_filter_F=100e-9,recommended_debounce_ms=10,internal_offrail_peak_injection_target_A=1e-6,circuit='MMBT3904 NPN, emitter GND, base from HPD47k + base100kPD, collector FPGA +47kPU to3V3; active-low',
    dc_cases=len(rows),dc_misses=sum(not r['ok'] for r in rows),
    powered_low_max_V=max(r['FPGA_pin_V'] for r in rows if r['rail_V'] and r['expected']=='active-low'),
    powered_high_min_V=min(r['FPGA_pin_V'] for r in rows if r['rail_V'] and r['expected']=='inactive-high'),
    off_core_pin_max_V=max(r['FPGA_pin_V'] for r in rows if not r['rail_V']),
    off_core_DC_injection_max_A=max(r['core_injection_A'] for r in rows if not r['rail_V']),
    transients=tran,limits=['Generic NPN model, not vendor-corner signoff.','GPIO clamp and pin capacitance are assumed sensitivities; no ESD compliance test.','RCLAMP5V leakage above VRWM, at5.5V, is not guaranteed by the 1uA@5V specification.','Firmware must invert HPD, configure the pin as input, and debounce.','DC source impedance swept up to1k; other source behavior not guaranteed.'])
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=1))
