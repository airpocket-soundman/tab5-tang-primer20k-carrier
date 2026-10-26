from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;ROOT=H.parents[2]
(H/'cases').mkdir(exist_ok=True)
cases=[]
for v in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
    d=json.loads((ROOT/'variants'/v/'kicad/sim/power_dc_check.json').read_text())
    base={'variant':v,'path_R':max(d['path_resistance_ohm'].values()),'hdmi_load':0 if v=='lite-c-dnp' else .05,'source_pcb_sha256':hashlib.sha256((ROOT/'variants'/v/'kicad/tab5-fpga-carrier.kicad_pcb').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'ldo_trace_L':3e-9 if v=='lite-c-dnp' else 6e-9,'ldo_trace_R':.005 if v=='lite-c-dnp' else .011}
    for suffix,delta in [
      ('nominal',{}),
      ('low-supply-cold',{'vin':11.4,'temp':0,'rsource':.5,'rptc':.1,'cout':176e-6,'L':12e-6,'esr':.04,'cin_bulk':80e-6,'cin_ceramic':8e-6,'vref':1.196,'rtop_mult':.99,'rbot_mult':1.01,'ldo_ref_mult':.98}),
      ('high-supply-hot',{'vin':12.6,'temp':50,'cout':264e-6,'L':18e-6,'esr':.01,'dcr':.0505,'vref':1.245,'rtop_mult':1.01,'rbot_mult':.99,'ldo_ref_mult':1.02,'path_R':base['path_R']*(1+.00393*65)}),
      ('one-amp-step',{'core_load':1.,'cout':176e-6,'L':18e-6,'esr':.04,'vref':1.196,'rtop_mult':.99,'rbot_mult':1.01,'path_R':base['path_R']*(1+.00393*65),'rsource':.5}),
      ('ldo-50mA-sensitivity',{'ldo_load':.05,'c33':17.6e-6,'ldo_ref_mult':.98}),
      ('ldo-loop-slow',{'ldo_loop_mult':.5,'ldo_load':.05,'c33':17.6e-6,'ldo_ref_mult':.98}),
      ('ldo-loop-fast',{'ldo_loop_mult':2.,'ldo_load':.05,'c33':17.6e-6,'ldo_ref_mult':1.02}),
      ('switch-cycle',{'switch_off':True,'stop':.055}),
      ('ldo-minimum-load-steps',{'ldo_minimum_steps':True,'ldo_ref_mult':.98,'c33':17.6e-6}),
      ('ldo-minimum-slow-loop',{'ldo_minimum_steps':True,'ldo_ref_mult':.98,'c33':17.6e-6,'ldo_loop_mult':.5}),
      ('softstart-fast',{'softstart':.0054}),
      ('softstart-slow',{'softstart':.010}),
      ('low-esr-sensitivity',{'esr':.002,'cout':264e-6,'L':18e-6}),
      ('combined-loop-worst',{'vin':11.4,'vref':1.196,'rtop_mult':.99,'rbot_mult':1.01,'esr':.002,'cout':176e-6,'L':12e-6,'pwm_tau':1.25e-6,'path_R':base['path_R']*(1+.00393*65)}),
      ('slow-input-ramp',{'ramp':.02,'stop':.06,'settled_start':.04}),
      ('brownout-PG',{'kind':'drop','stop':.7,'time_mult':15,'settled_start':.015,'maxstep':5e-6}),
      ('reverse-input',{'kind':'reverse','stop':2.,'maxstep':100e-6}),
    ]:
        c=dict(base,name=v+'-'+suffix,**delta);cases.append(c)
    if v=='lite-a-dual':
        cases.append(dict(base,name=v+'-PD-stairs',kind='pd',stop=.045,settled_start=.020))
        cases.append(dict(base,name=v+'-PD-low-ENA',kind='pd',stop=.045,settled_start=.020,en_threshold=1.,en_hysteresis=.325))
        cases.append(dict(base,name=v+'-PD-high-ENA',kind='pd',stop=.045,settled_start=.020,en_threshold=1.3,en_hysteresis=.325))
    # A/B have the same regulator/HDMI/loading and copper resistance; one
    # shared manufacturer's switching case exercises their common circuit.
    if v in ('lite-a-dual','lite-c-dnp'):
        cases.append(dict(base,name=v+'-vendor-startup',model='vendor',stop=.012,maxstep=1e-7,settled_start=.0088,core_step_s=.009,core_return_s=.011))
cal=dict(kind='barrel',vin=15,input_direct=True,rsource=.01,rptc=.001,path_R=.001,contact_R=0,return_R=0,hdmi_load=0,include_ldo=False,esr=.02,dcr=.027,stop=.0115,settled_start=.0088,rbot_mult=3240/3246.433841613379,core_baseline=.75,core_load=2.25,core_step_s=.009,core_return_s=.010)
cases.append(dict(cal,name='calibration-vendor-EVM',model='vendor',maxstep=1e-7))
cases.append(dict(cal,name='calibration-average-EVM',maxstep=2e-7))
for c in cases:(H/'cases'/(c['name']+'.json')).write_text(json.dumps(c,indent=2)+'\n')
(H/'cases/index.json').write_text(json.dumps([c['name'] for c in cases],indent=2)+'\n')
print(len(cases),'cases prepared')
