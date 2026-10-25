"""CCM small-signal loop from TI's exact error-amp R/C network; numpy only."""
from pathlib import Path
import itertools,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
F=np.logspace(1,6,4000);s=2j*np.pi*F
A=206538/((1+s/(2*np.pi*14.96))*(1+s/(2*np.pi*1e7)))
Yi=1/2.75e6+s*20e-12/(1+s*260e3*20e-12)
Yf=s*1e-12+s*30e-12/(1+s*3.27e6*30e-12)
Gc=A*Yi/(Yi+(1+A)*Yf)
Hfb=(1/(1/3300+1/200000))/(10000+1/(1/3300+1/200000))
def loop(L,C,esr,load,delay):
 Zc=esr+1/(s*C);Z=1/(1/Zc+load/4.982)
 return Gc*(1/.0375)*Z/(.1+s*L+Z)*Hfb*np.exp(-s*delay)
def metric(t):
 g=20*np.log10(abs(t));phase=np.unwrap(np.angle(t))*180/np.pi
 ids=np.where((g[:-1]>=0)&(g[1:]<0))[0]
 return [{'crossover_Hz':float(F[i]),'phase_margin_deg':float(180+phase[i])} for i in ids]
rows=[]
for L,C,esr,load,delay in itertools.product((12e-6,15e-6,18e-6),(176e-6,220e-6,264e-6),(.002,.01,.02,.04),(.56,1.06),(.25e-6,1.25e-6)):
 t=loop(L,C,esr,load,delay)
 rows.append(dict(L_H=L,C_F=C,ESR_ohm=esr,total_load_A=load,PWM_delay_s=delay,crossings=metric(t)))
worst=min(rows,key=lambda r:min(x['phase_margin_deg'] for x in r['crossings']))
ref=loop(15e-6,220e-6,.02,1,1e-6)
result={'status':'CCM analytical sensitivity, not IC process-corner or measured Bode verification','model':'Exact TI macro error-amplifier network; average plant gain 1/.0375; Rseries=.1ohm; actual RFB network; PWM-delay sensitivity','cases':len(rows),'minimum_phase_margin_case':worst,'EVM_typical_reference_comparison':{'TI_published_crossover_Hz':25000,'TI_published_phase_margin_deg':50,'analytical_ESR20mohm':metric(ref)},'all_sampled_CCM_margins_positive':all(all(x['phase_margin_deg']>0 for x in r['crossings']) for r in rows),'limitations':['Low-load DCM/burst operation excluded from CCM Bode interpretation.','ESR lower bound is not guaranteed by the capacitor maximum-only datasheet; 2mohm is an additional sensitivity, not a certified part corner.','Internal IC compensation process spread and full switching/hiccup dynamics not characterized by this analytical sensitivity.'],'results':rows}
(H/'results/loop-margin.json').write_text(json.dumps(result,indent=2)+'\n')
fig,ax=plt.subplots(2,1,figsize=(8,6),sharex=True)
for e in (.002,.01,.02,.04):
 t=loop(15e-6,220e-6,e,.56,1.25e-6)
 ax[0].semilogx(F,20*np.log10(abs(t)),label=f'ESR {e*1000:g} mOhm')
 ax[1].semilogx(F,np.unwrap(np.angle(t))*180/np.pi)
ax[0].axhline(0,color='k',lw=.7);ax[1].axhline(-180,color='k',lw=.7)
ax[0].set_ylim(-50,70);ax[1].set_ylim(-270,0);ax[1].set_xlim(100,2e5)
ax[0].set_ylabel('Loop gain (dB)');ax[1].set_ylabel('Phase (deg)');ax[1].set_xlabel('Frequency (Hz)');ax[0].legend()
for a in ax:a.grid(True,which='both',alpha=.3)
fig.suptitle('TPS5430 compensation-network sensitivity (CCM model)');fig.tight_layout();fig.savefig(H/'results/loop-margin.png',dpi=160)
print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=1))
