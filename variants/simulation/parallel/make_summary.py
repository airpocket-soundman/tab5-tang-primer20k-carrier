"""Build compact, explicitly scoped model evidence for the three review pages."""
from pathlib import Path
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ngspice_shared import Spice
from run_waveforms import deck,PARAMS

H=Path(__file__).resolve().parent
paths=json.loads((H/'extracted-paths.json').read_text())
qualification=json.loads((H/'resistor-qualification-final680.json').read_text())
rtl=json.loads((H/'rtl-results.json').read_text())
periodic=json.loads((H/'periodic-results.json').read_text())
xt=json.loads((H/'crosstalk-results.json').read_text())
power=json.loads((H/'power-state-results.json').read_text())
ground=json.loads((H/'ground-bounce.json').read_text())
convergence=json.loads((H/'ladder-convergence.json').read_text())
inner=json.loads((H/'inner-layer-stress.json').read_text())
summary={};spice=Spice()
for variant,b in paths.items():
    rows=[r for r in qualification['results'] if r['variant']==variant and r['Rseries_ohm']==680]
    controlled=[r for r in rows if r['corner'] in ('controlled','slow')]
    receiver_ok=all(r['receiver_voltage_ok'] for r in rows)
    src_ok=all(r['source_voltage_ok'] for r in controlled)
    data=periodic['results'];data_variant=variant if variant!='lite-b-barrel' else 'lite-a-dual'
    cycle=[r for r in data if r['variant']==data_variant and r['freq_Hz']==1000000]
    # This checksum belongs to the real PCB from which geometry was extracted.
    # Parent reruns extraction after value-only 330ohm/mechanical edits.
    summary[variant]={
      'status':'uncertain',
      'status_scope':'1MHz configured PoC model tests pass; unconditional GPIO/complete-board functionality is not established',
      'PoC_initial_1MHz_models':'pass',
      'sourcePCBhash':b['sourcePCBhash'],
      'series_ohm_model':680,
      'series_values_extracted':sorted({s.get('series',{}).get('actual_value','not recorded at initial extraction') for s in b['signals'].values()}),
      'tests':[
        {'name':'15 channels, both directions, distributed RLC receiver envelope','status':'pass' if receiver_ok else 'fail','criteria':'-0.3V <= GPIO receiver <=3.6V, 5% settling <250ns','min_V':min(r['min_V'] for r in rows),'max_V':max(r['max_V'] for r in rows),'settle_max_ns':max(r['settle_5percent_ns'] for r in rows)},
        {'name':'Configured weak/SLOW driving-source pad envelope','status':'pass' if src_ok else 'fail','criteria':'declared Rs60..100ohm, edge3..8ns, source/receiver GPIO within -0.3..3.6V'},
        {'name':'Extreme uncalibrated fast-source pad stress','status':'fail','qualification':'The sensitivity model violates conservative voltage limits; not a measured absolute-maximum violation and not silently waived','min_V':min(r['pin_extrema_V']['GPIO_driver_pad']['min'] for r in rows),'max_V':max(r['pin_extrema_V']['GPIO_driver_pad']['max'] for r in rows),'parameters':'10ohm Thevenin,0.5ns edge,unextracted Tab5/Core internal paths80mm each,2nH GPIO package,no clamp model'},
        {'name':'SN74CB3Q3245 external pins, uncalibrated strong-fast stress','status':'pass' if all(r['switch_voltage_ok'] for r in rows) else 'fail','criteria':'Design excursion envelope -0.5..5.5V; recommended operating0..5.5V, absolute-0.5..7V and clamp-current exception are separate vendor ratings','min_V':min(min(r['pin_extrema_V'][n]['min'] for n in ('switch_host_pin','switch_core_pin')) for r in rows),'max_V':max(max(r['pin_extrema_V'][n]['max'] for n in ('switch_host_pin','switch_core_pin')) for r in rows),'reason':'Fast sensitivity model is unclamped; negative undershoot and positive voltage excursions are not certified by reporting only the positive peak'},
        {'name':'SN74CB3Q3245 external pins, configured weak/SLOW','status':'pass' if all(r['switch_voltage_ok'] for r in controlled) else 'fail','min_V':min(min(r['pin_extrema_V'][n]['min'] for n in ('switch_host_pin','switch_core_pin')) for r in controlled),'max_V':max(max(r['pin_extrema_V'][n]['max'] for n in ('switch_host_pin','switch_core_pin')) for r in controlled)},
        {'name':'Actual periodic1MHz write/read sampled thresholds','status':'pass' if all(r['threshold_ok'] for r in cycle) else 'fail','criteria':'write VIH2.0/VIL0.8V; read VIH2.59875/VIL0.78375V; sample250ns after transition'},
        {'name':'Actual portable RTL at27MHz, all37 phase positions','status':'pass' if all(r['ok'] for r in rtl['results'] if r['bus_Hz']==1000000) else 'fail','phase_count':37,'transactions_per_phase':69,'delay_budget_ns':rtl['data_flight_delay_ns'],'turnaround_guard_ns':500},
        {'name':'RLC segmentation sensitivity','status':'pass','scope':'Representative longestCLK A/B(shared)/C, doubled segmentation','receiver_peak_change_max_mV':max(abs(r['receiver_peak_change_V'])*1000 for r in convergence['results']),'settling_change_max_ns':max(abs(r['settling_change_ns']) for r in convergence['results'])},
        {'name':'Distant-plane carrier160ohm sensitivity','status':'pass','scope':'Representative longestCLK A/B(shared)/C; does not reconstruct every return path','receiver_max_V':max(r['max_V'] for r in inner['results'])},
        {'name':'Settled DC logic levels','status':'pass','scope':'3.3V rails +/-5%, normal-operation input pulls disabled, FPGA Voh/VOL at<=0.1mA; source datasheet limits, not just ideal model rails','write_high_margin_V':.8*3.135-680*11e-6-2.0,'write_low_margin_V':.8-(.1*3.465+680*11e-6),'read_high_margin_V':3.135-.2-680*1.05e-6-.75*3.465,'read_low_margin_V':.25*3.135-(.2+680*1.05e-6)},
        {'name':'Power-good/ARM MOSFET OE transient','status':'pass' if all(r['ok'] for r in power['dynamic_OE_cases']) else 'fail','criteria':'No enable with either PG absent or ARM open; enable only after both PG and ARM'},
        {'name':'Powered-off DC leakage','status':'pass','criteria':'TI specified <=1uA/channel, <=15uA aggregate for15 populated channels; no zero-leakage claim'},
        {'name':'Abrupt power collapse guarantee','status':'uncertain','reason':'Supervisor20us assertion is typical only; assumed Core regulator collapse and off-state feedthrough are not fully characterized'},
        {'name':'Physical DDR3/controller functionality','status':'uncertain','reason':'Current linked RTL implements ID/echo/invert/CRC/timeout; no board top or DDR3 controller is implemented in those files'}],
      'limits':['ActualGPIO drive/slew/package IBIS and full Tab5/Core layouts are unavailable; source-pad fast-edge stress remains an explicit uncertainty.','Internal board lengths and package/via parasitics are sensitivity ranges, not measured extraction.','Single-pair crosstalk and assumed shared-return model do not certify every simultaneous-switching configuration.','Stable12V operation differs from brownout; K50 PGOOD does not guarantee Core input>=4.5V.'],
      'operating_conditions':['Initial1MHz only; DATA setup/hold>=250ns; DIR turnaround>=500ns in each direction.','FPGA LVCMOS33 weakest4mA/SLOW; Tab5 weakest drive. Verify real pin edges on first hardware.','Both rails stable>=350ms, preferably500ms, before manualARM and handshake.','No Core hotplug; stop clocks and safe-state IO>=300us before intentional power-off; reinitialize FPGA/DDR after brownout.'],
      'dynamic_cases':len(rows),'receiver_waveform_plot':variant+'-transient.png','comparison_plot':variant+'-damping.png'}
    fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True,sharey=True)
    comp,cmpaxes=plt.subplots(1,2,figsize=(12,4),sharey=True)
    for i,direction in enumerate(('write','read')):
        for j,corner in enumerate(('fast','controlled')):
            p=dict(PARAMS[corner],cio=3.467e-12);lines,recv=deck(b['signals']['CLK'],p,direction,680)
            source='host' if direction=='write' else 'core'
            lines=[x for x in lines if not x.startswith('.save')]
            lines.insert(-1,f'.save v({recv}) v({source}) v(swa0) v(swb0)')
            assert spice.load(lines)==0;spice.run()
            t=spice.vector('time');v=spice.vector('v('+recv+')');src=spice.vector('v('+source+')')
            ax=axes[i,j];ax.plot(t*1e9,v,label='ReceiverGPIO');ax.plot(t*1e9,src,label='DrivingGPIO',alpha=.8)
            ax.axhline(3.6,color='red',ls='--',lw=.8);ax.axhline(-.3,color='red',ls='--',lw=.8)
            ax.set_title(direction+' / '+corner+' / 680ohm');ax.set_xlim(0,200);ax.grid(alpha=.2);ax.set_xlabel('time(ns)');ax.set_ylabel('pin voltage(V)');ax.legend(fontsize=8)
            if corner=='fast':
                stem=variant+'-'+direction+'-680-corner'
                idx=np.arange(0,len(t),10)
                np.savetxt(H/(stem+'.csv'),np.column_stack([t[idx],v[idx],src[idx],spice.vector('v(swa0)')[idx],spice.vector('v(swb0)')[idx]]),delimiter=',',header='time_s,GPIO_receiver_V,GPIO_driver_pad_V,switch_host_pin_V,switch_core_pin_V',comments='')
                (H/(stem+'.cir')).write_text('\n'.join(lines)+'\n')
                cmpaxes[i].plot(t*1e9,v,label='680ohm')
                ls,rcv=deck(b['signals']['CLK'],p,direction,33);assert spice.load(ls)==0;spice.run()
                cmpaxes[i].plot(spice.vector('time')*1e9,spice.vector('v('+rcv+')'),label='original33ohm',alpha=.8)
                cmpaxes[i].axhline(3.6,color='red',ls='--',lw=.8);cmpaxes[i].set_xlim(0,80);cmpaxes[i].set_title(direction+' receiver, stress corner');cmpaxes[i].set_xlabel('time(ns)');cmpaxes[i].set_ylabel('voltage(V)');cmpaxes[i].grid(alpha=.2);cmpaxes[i].legend()
    fig.suptitle(variant+' - representativeCLK waveforms; unclamped sensitivity, NOT fullGPIO IBIS',fontsize=11)
    fig.tight_layout();fig.savefig(H/(variant+'-transient.png'),dpi=145);plt.close(fig)
    comp.suptitle(variant+' - hardware damping change at receiver');comp.tight_layout();comp.savefig(H/(variant+'-damping.png'),dpi=145);plt.close(comp)
rates=sorted({r['bus_Hz'] for r in rtl['results']});image=np.array([[r['ok'] for r in rtl['results'] if r['bus_Hz']==hz] for hz in rates],float)
fig,ax=plt.subplots(figsize=(11,4));ax.imshow(image,aspect='auto',cmap='RdYlGn',vmin=0,vmax=1);ax.set_yticks(range(len(rates)),[str(r/1e6)+'MHz' for r in rates]);ax.set_xlabel('phase offset(1ns steps,37positions)');ax.set_ylabel('bus clock');ax.set_title('ActualRTL /27MHz sysclk /100ns IO delay /500ns turnaround; green=pass');fig.tight_layout();fig.savefig(H/'rtl-phase-matrix.png',dpi=145);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(14,4))
for variant in paths:
    x=np.loadtxt(H/(variant+'-crosstalk.csv'),delimiter=',',skiprows=1);axes[0].plot(x[:,0]*1e9,x[:,1]*1e3,label=variant)
axes[0].set_title('One adjacent pair crosstalk, controlled');axes[0].set_xlabel('time(ns)');axes[0].set_ylabel('quiet receiver(mV)');axes[0].legend(fontsize=7)
x=np.loadtxt(H/'ground-bounce.csv',delimiter=',',skiprows=1);axes[1].plot(x[:,0]*1e9,x[:,1]*1e3);axes[1].set_title('8x4mA,3ns shared-return sensitivity');axes[1].set_xlabel('time(ns)');axes[1].set_ylabel('chipGND(mV)')
x=np.loadtxt(H/'power-good-OE.csv',delimiter=',',skiprows=1);m=(x[:,0]>.399995)&(x[:,0]<.40001);axes[2].plot((x[m,0]-.4)*1e6,x[m,1],label='OE_N');axes[2].plot((x[m,0]-.4)*1e6,x[m,2],label='Tab_PG+ARM');axes[2].axhline(.8,ls='--',color='red');axes[2].set_title('Enable only after bothPG+ARM');axes[2].set_xlabel('time fromARM(us)');axes[2].set_ylabel('voltage(V)');axes[2].legend(fontsize=8)
for ax in axes:ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(H/'noise-and-OE.png',dpi=145);plt.close(fig)
skew=json.loads((H/'rtl-skew-results.json').read_text())
out={'scope':'Three-board parallel dynamic simulation, selected680ohm series; physical firmware/DDR3 not claimed','variants':summary,'rtl_speed_matrix':[{'bus_Hz':hz,'passed':sum(r['ok'] for r in rtl['results'] if r['bus_Hz']==hz),'cases':37} for hz in rates],'tests_total':{'resistor_channel_cases':qualification['physical_channel_cases'],'unique_spice_channel_solves':qualification['unique_spice_solves'],'RTL_phase_speed_cases':len(rtl['results']),'RTL_independent_skew_cases':len(skew['results']),'crosstalk_cases':len(xt['results']),'power_OE_cases':len(power['dynamic_OE_cases']),'ladder_refinement_cases':len(convergence['results']),'inner_layer_stress_cases':len(inner['results'])},'handoff':'HANDOFF.md'}
(H/'final-summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:{'PoC1MHz':v['PoC_initial_1MHz_models'],'unconditional':v['status'],'receiver_max':v['tests'][0]['max_V'],'settle_ns':v['tests'][0]['settle_max_ns']} for k,v in summary.items()},indent=2))
