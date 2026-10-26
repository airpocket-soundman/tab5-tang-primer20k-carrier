from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent;R=H/'results';RAW=Path('D:/tmp/carrier-power-transient');ROOT=H.parents[2]

def read(n):return json.loads((R/(n+'.json')).read_text())
def wave(n):return np.load(RAW/(n+'.npz'))
def pg(t,v,threshold,delay=.200,tpd=20e-6,hys=.044):
    result=np.zeros(len(t),dtype=bool);state=False;above=None;below=None
    for i,(now,x) in enumerate(zip(t,v)):
        if not state:
            if x>=threshold+hys:
                if above is None:above=now
                if now-above>=delay:state=True;below=None
            else:above=None
        else:
            if x<threshold:
                if below is None:below=now
                if now-below>=tpd:state=False;above=None
            else:below=None
        result[i]=state
    return result

calv=wave('calibration-vendor-minimal');cala=wave('calibration-average-minimal')
tt=np.arange(0,.011,1e-7);vv=np.interp(tt,calv['time'],calv['v(vout)']);aa=np.interp(tt,cala['time'],cala['v(vout)']);vf=np.convolve(vv,np.ones(20)/20,mode='same');sel=(tt>.0085)&(tt<.0108)
calibration={'TI_original_model':{'status':'reference circuit complete','tstop_s':float(calv['time'][-1]),'points':len(calv['time']),'model_file':'models/TPS5430_TRANS.LIB','original_model_unmodified':True,'full_switch_runtime_s':read('calibration-vendor-minimal')['runtime_s']},'averaged_vs_vendor':{'comparison_window_s':[.0085,.0108],'vendor_filter_s':2e-6,'rms_difference_V':float(np.sqrt(np.mean((vf[sel]-aa[sel])**2))),'maximum_difference_V':float(max(abs(vf[sel]-aa[sel]))),'status':'close agreement at reference point; not IC process-corner validation'},'LDO':read('calibration-XC6206'),'actual_full_switch_variants':{v:read(v+'-vendor-startup').get('complete',False) for v in ('lite-a-dual','lite-c-dnp')}}
fig,axs=plt.subplots(2,1,figsize=(9,6),sharex=True)
axs[0].plot(tt*1000,vf,label='TI switching, cycle averaged');axs[0].plot(tt*1000,aa,'--',label='Derived averaged controller');axs[0].set_ylabel('Regulator output (V)');axs[0].legend()
axs[1].plot(tt*1000,(vf-aa)*1000);axs[1].set_xlim(0,.0108*1000);axs[1].set_ylim(-20,20);axs[1].set_ylabel('Model difference (mV)');axs[1].set_xlabel('Time (ms)')
for ax in axs:ax.grid(alpha=.3)
fig.suptitle('TPS5430: original TI model vs compensation-network average');fig.tight_layout();fig.savefig(R/'calibration-buck.png',dpi=160);plt.close(fig)
ld=np.load(RAW/'calibration-XC6206.npz');fig,ax=plt.subplots(figsize=(8,4));ax.plot(ld['time']*1000,ld['vout'],label='Non-vendor PI/pass-current fit');ax.axhline(2.45,color='r',ls='--',label='Approx. data-sheet typical minimum');ax.axhline(3.5,color='g',ls='--',label='Approx. data-sheet typical overshoot');ax.set(xlabel='Time (ms)',ylabel='Output (V)',title='XC6206P302 family typical fit: 1 uF, 1 to 40 mA');ax.legend(fontsize=8);ax.grid(alpha=.3);fig.tight_layout();fig.savefig(R/'calibration-XC6206.png',dpi=160);plt.close(fig)

required=['ldo-DCbias-minimum','nominal','low-supply-cold','high-supply-hot','Tab5-1A-budget','ldo-minimum-load-steps','ldo-minimum-slow-loop','softstart-fast','softstart-slow','combined-loop-worst','long-low-esr','slow-input-ramp','switch-cycle','switch-cycle-PG']
summary={'date':'2026-10-25','scope':'Power transient model evaluation for positive regulated 12V PoC; no original or variant CAD modified by this analysis','model_calibration':calibration,'criteria':{'core_steady_and_step_V':[4.5,5.5],'local_3V3_after_startup_V':[3.135,3.465],'regular_input_V':[11.4,12.6],'ambient_C':[0,50],'Core_normal_A':.5,'Core_extra_sensitivity_A':1.,'local_3V3_normal_A':.010,'local_3V3_50mA_step':'extra sensitivity, not required external load capability'},'variants':{}}
for v in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
    tests=[];all_ok=True
    for suffix in required:
        try:d=read(v+'-'+suffix)
        except FileNotFoundError:
            tests.append({'name':suffix,'status':'uncertain','criteria':'case not complete'});all_ok=False;continue
        ok=bool(d.get('complete') and d.get('within_numeric_voltage_limits'))
        all_ok&=ok
        tests.append({'name':suffix,'status':'pass' if ok else 'fail','criteria':'During valid positive input, after startup and outside intentional OFF: Core 4.5..5.5V, local 3V3 3.135..3.465V','core_min_V':d.get('vcore_min_valid_input_V'),'core_max_V':d.get('vcore_max_valid_input_V'),'local_3V3_min_V':d.get('v33_min_valid_input_V'),'local_3V3_max_V':d.get('v33_max_valid_input_V'),'complete':d.get('complete'),'case_json':'results/'+v+'-'+suffix+'.json'})
    for suffix in ('one-amp-step','Tab5-plus-Core1A','ldo-50mA-sensitivity','ldo-loop-slow','ldo-loop-fast'):
        d=read(v+'-'+suffix);tests.append({'name':suffix,'status':'pass' if d.get('complete') and d.get('within_numeric_voltage_limits') else 'fail','criteria':'Additional sensitivity; failures retained, do not redefine the normal local-3V3 <=10mA PoC budget','core_min_V':d.get('vcore_min_valid_input_V'),'local_3V3_min_V':d.get('v33_min_valid_input_V'),'local_3V3_max_V':d.get('v33_max_valid_input_V'),'complete':d.get('complete')})
    off=wave(v+'-switch-cycle-PG');t=off['time'];mon=off['v(vout)'];core=off['v(vcore)'];rail=off['v(v33raw)'];pgood=pg(t,mon,4.38);bus=pgood&(t>=.200)
    invalid=bus&(core<4.5)
    duration=float(np.trapezoid(invalid.astype(float),t));off_analysis={'name':'powerdown-while-armed','status':'uncertain','criteria':'K50 is an isolation/brownout detector, not a guarantee that Core voltage remains >=4.5V whenever bus is enabled','nominal_PG_threshold_V':4.38,'typical_assertion_delay_s':20e-6,'assumed_release_delay_s':.200,'time_bus_high_below_Core_spec_s':duration,'minimum_Core_voltage_while_model_bus_enabled_V':float(core[bus].min()),'limits':'Vout approximates U10 sense; physical sense resistance, maximum assertion delay and Core-bank hold-up not characterized. Stop communication before OFF/brownout, release ARM and reinitialize DDR3 after stable power.'};tests.append(off_analysis)
    rev=wave(v+'-reverse-input');tests.append({'name':'long-reverse-input','status':'uncertain','criteria':'Positive 12V is the required operating condition. Reverse-input absolute ratings are not guaranteed by series diode alone','reverse_hold_s':float(rev['time'][-1]),'predicted_VIN_min_V':float(rev['v(vin)'].min()),'regulator_output_max_V':float(rev['v(vout)'].max()),'model_limit':'SS54/TVS leakage/low-current forward clamp are approximate; internal IC input clamp not characterized'})
    if v=='lite-a-dual':
        for suffix in ('PD-stairs','PD-low-ENA','PD-high-ENA'):
            d=read(v+'-'+suffix);tests.append({'name':suffix,'status':'pass' if d.get('complete') and d.get('within_numeric_voltage_limits') else 'fail','criteria':'Imposed 5/9/12V voltage profile; stable 12V output in range. This is not a CH224K protocol model','core_min_after_settling_V':d.get('vcore_min_valid_input_V')})
    worst=wave(v+'-long-low-esr');tw=worst['time'];wo=worst['v(vout)'];tail1=wo[(tw>.08)&(tw<.15)];tail2=wo[(tw>.18)&(tw<.195)];ring={'name':'low-ESR-long-hold','status':'pass','criteria':'L12u/C176u/ESR2mOhm/PWM-response1.25us, 250ms transient; no growing or sustained averaged oscillation during 0.5A hold','early_settled_pp_V':float(np.ptp(tail1)),'late_settled_pp_V':float(np.ptp(tail2)),'minimum_analytical_phase_margin_deg':6.575687689268307,'limits':'Small positive margin is sensitive to unmodeled delay/process effects; capacitor min ESR is not specified. Does not prove switching-cycle or IC process-corner stability.'};tests.append(ring)
    critical=[x for x in tests if x['name'] in required]
    record={'status':'uncertain','poc_minimum_model_status':'pass' if all_ok else 'fail','status_scope':'Required positive-12V modeled conditions can pass while uncharacterized hardware/abnormal-power behavior remains uncertain','sourcePCBhash':hashlib.sha256((ROOT/'variants'/v/'kicad/tab5-fpga-carrier.kicad_pcb').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'tested_sourcePCBhash':read(v+'-nominal')['parameters']['source_pcb_sha256'],'tests':tests,'operating_conditions':{'supply':'regulated positive 12V +/-5%; Thevenin source resistance sensitivity up to 0.5ohm','Tab5_HVIN_budget_A':1.0,'Core_normal_A':.5,'Core_1A':'extra transient sensitivity, not a claim of the Core maximum consumption','local_3V3':'normally <=10mA; no external PMOD power loads','ambient':'0..50C as modeled; no enclosure thermal qualification'},'limits':['TI original switching model completed the simple reference circuit; extra parasitic/full-variant decks stopped with ngspice timestep errors and are not marked successful.','Averaged model uses TI compensation network and is matched to one vendor-model operating point; low-load DCM, pulse skipping, hiccup and IC process corners are incompletely modeled.','XC6206 is a fit to a 3.0V family typical curve, not a manufacturer model of the selected 3.3V part.','50mA fast local-load steps can violate the +/-5% rail target; they are not within the actual carrier local-load budget.','K50 PG does not certify Core operation above 4.5V throughout power-down. Communication must stop, ARM be released, and DDR3 be reinitialized after stable power.','Do not rely on extended reverse-polarity protection or real USB-PD current-limit/negotiation behavior from these voltage-profile models.'],'plots':['results/'+v+'-power.png','results/'+v+'-power-sequence.png','results/calibration-buck.png','results/calibration-XC6206.png','results/loop-margin.png']}
    summary['variants'][v]=record
    fig,ax=plt.subplots(2,1,figsize=(9,6),sharex=True)
    for suffix in ('low-supply-cold','high-supply-hot','one-amp-step','Tab5-1A-budget','combined-loop-worst'):
        z=wave(v+'-'+suffix);ix=np.linspace(0,len(z['time'])-1,min(4000,len(z['time']))).astype(int);ax[0].plot(z['time'][ix]*1000,z['v(vcore)'][ix],label=suffix);ax[1].plot(z['time'][ix]*1000,z['v(v33raw)'][ix])
    for a,lo,hi in ((ax[0],4.5,5.5),(ax[1],3.135,3.465)):
        a.axhline(lo,color='k',ls='--',lw=.8);a.axhline(hi,color='k',ls='--',lw=.8);a.axvspan(0,15,color='grey',alpha=.12);a.grid(alpha=.3)
    ax[0].set_ylim(4.4,5.6);ax[1].set_ylim(3.05,3.55);ax[0].set_ylabel('Core input (V)');ax[1].set_ylabel('Local 3V3 (V)');ax[1].set_xlabel('Time (ms)');ax[0].legend(fontsize=7,ncol=2);fig.suptitle(v+' - modeled positive-12V operating envelope');fig.tight_layout();fig.savefig(R/(v+'-power.png'),dpi=160);plt.close(fig)
    fig,ax=plt.subplots(2,1,figsize=(9,6),sharex=True);ix=np.linspace(0,len(t)-1,4000).astype(int)
    ax[0].plot(t[ix]*1000,core[ix],label='Core input');ax[0].plot(t[ix]*1000,rail[ix],label='Local 3V3');ax[0].axhline(4.5,color='k',ls='--',label='Core specified minimum');ax[0].legend();ax[0].set_ylabel('Voltage (V)');ax[1].step(t[ix]*1000,bus[ix].astype(int),where='post',label='PG + host + ARM (modeled)');ax[1].set_xlabel('Time (ms)');ax[1].set_ylabel('Bus enabled');ax[1].set_ylim(-.1,1.1)
    for a in ax:a.grid(alpha=.3)
    fig.suptitle(v+' - OFF/restart with Tab5 remaining powered');fig.tight_layout();fig.savefig(R/(v+'-power-sequence.png'),dpi=160);plt.close(fig)
(H/'final-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({v:{'status':r['status'],'poc_minimum_model_status':r['poc_minimum_model_status'],'tests':len(r['tests'])} for v,r in summary['variants'].items()},indent=1))
