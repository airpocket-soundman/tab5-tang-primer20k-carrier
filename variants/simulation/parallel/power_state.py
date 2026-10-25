"""Dynamic OE MOSFET-chain model plus power-down and Ioff sensitivities."""
from pathlib import Path
import json
import numpy as np
from ngspice_shared import Spice

HERE=Path(__file__).resolve().parent
s=Spice();results=[]
for name,t_tab,t_core,arm in [('staggered',.37,.355,.40),('ARM_open',.37,.355,None),('Tab_absent',None,.355,0),('Core_absent',.37,None,0)]:
    def pg(t,high):
        return 'DC 0' if t is None else f'PWL(0 0 {t} 0 {t+1e-6} {high} .65 {high})'
    # Q3's gate goes high only if the manual jumper is fitted and Tab PGOOD.
    start=None if arm is None or t_tab is None else max(arm,t_tab)
    lines=['OE supervisor/MOS chain transient, conservative high-Vth corner',
      'Vcc vcc 0 3.234','Roe vcc oe 21780','Coe oe 0 30p',
      'Vtab gt 0 '+pg(start,2.757),'Vcore gc 0 '+pg(t_core,3.871),
      'Rtab gt 0 100k','Rcore gc 0 100k',
      'Mtop oe gt mid 0 weak','Mbottom mid gc 0 0 weak',
      'Rleak1 oe mid 3.6Meg','Rleak2 mid 0 3.6Meg',
      '.model weak NMOS(level=1 VTO=2.5 KP=.01 LAMBDA=.02 CGSO=1e-11 CGDO=1e-11)',
      '.tran 10u .65 0 10u','.save v(oe) v(gt) v(gc)','.end']
    assert s.load(lines)==0;s.run();t=s.vector('time');v=s.vector('v(oe)')
    on=np.flatnonzero(v<.8);both_good=None if start is None or t_core is None else max(start,t_core)
    ok=(not len(on)) if both_good is None else (float(t[on[0]])>=both_good and float(v[-1])<.8)
    results.append({'case':name,'ok':ok,'Tab_PGOOD_s':t_tab,'Core_PGOOD_s':t_core,'ARM_s':arm,'first_OE_low_s':float(t[on[0]]) if len(on) else None,'OE_final_V':float(v[-1]),'OE_min_V':float(v.min())})
    idx=np.unique(np.r_[np.arange(0,len(t),100),np.flatnonzero((t>.3999)&(t<.4001))])
    if name=='staggered':
        np.savetxt(HERE/'power-good-OE.csv',np.column_stack([t[idx],v[idx],s.vector('v(gt)')[idx],s.vector('v(gc)')[idx]]),delimiter=',',header='time_s,OE_N_V,Tab_PGOOD_after_ARM_V,Core_PGOOD_V',comments='')
        (HERE/'power-good-OE.cir').write_text('\n'.join(lines)+'\n')
assert all(r['ok'] for r in results),results
fall=[]
for current in (.5,2):
    for cap_u in (176,220,264):
        for pd_us in (20,100):
            slope=current/(cap_u*1e-6)
            threshold=4.271;collapse=3.6
            detect=(5-threshold)/slope
            isolate=detect+pd_us*1e-6+.8e-6 # OE 22k/30pF plus switch disable
            bank=(5-collapse)/slope
            fall.append({'load_A':current,'Cout_uF':cap_u,'supervisor_assert_delay_us':pd_us,'Core_PGOOD_threshold_V':threshold,'assumed_Core_bank_collapse_5V_input_V':collapse,'isolation_after_fall_us':isolate*1e6,'bank_collapse_after_fall_us':bank*1e6,'margin_us':(bank-isolate)*1e6,'ok_under_assumptions':isolate<bank,'delay_status':'20us is TI typical, not guaranteed maximum; 100us is deliberately adverse sensitivity'})
off=[]
for feed_pf in (0,.1,1):
    lines=['Powered-off isolation Ioff/feedthrough sensitivity',
       'Vsignal a 0 PULSE(0 3.465 10n 3n 3n 500n 1u)','Roff a b 3.6Meg',
       'Ca a 0 5p','Cb b 0 13p','Rpull b 0 45k']
    if feed_pf:lines.append(f'Cfeed a b {feed_pf}p')
    lines.extend(['.tran 1n 2u 0 1n','.save v(b) v(a)','.end'])
    assert s.load(lines)==0;s.run();t=s.vector('time');v=s.vector('v(b)')
    off.append({'assumed_cross_port_feedthrough_pF':feed_pf,'max_receiver_with_45k_pulldown_V':float(v.max()),'DC_Ioff_bound_per_channel_uA':1,'15channel_DC_bound_uA':15,'capacitive_charge_per_edge_pC':feed_pf*3.465,'feedthrough_status':'Sensitivity assumption: off-port Cio5pF is NOT a specified cross-port capacitance; no full off-state transfer model was available'})
    if feed_pf==1:
        np.savetxt(HERE/'power-off-feedthrough.csv',np.column_stack([t[::5],v[::5]]),delimiter=',',header='time_s,off_receiver_with_pulldown_V',comments='')
        (HERE/'power-off-feedthrough.cir').write_text('\n'.join(lines)+'\n')
report={'dynamic_OE_cases':results,'power_down_sensitivity':fall,'power_off_feedthrough':off,'PoC_conditions':['Stop host clocks, drive control/data safe low or high-Z and wait >=300us before intentional Core power-off; do not hot-plug Core.','Wait >=350ms after both rails are stable before manual ARM; use both PGOOD indication and startup handshake.','Configure RDY/data input weak pull-downs when FPGA unpowered; do not interpret floating data as valid response.'],'limits':['TPS3839 assertion20us is typical only; no maximum was found, so abrupt rail collapse and fault/hotplug backpower immunity cannot be certified.','Core3V3 collapse at Core5V3.6V is an assumed buck/dropout envelope, not an extracted transient model of the complete Core.','MOS level1 high-Vth model is a sensitivity model, not manufacturer 2N7002 SPICE.','OE power-state checks do not constitute physical leakage measurements.']}
(HERE/'power-state-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=1))
