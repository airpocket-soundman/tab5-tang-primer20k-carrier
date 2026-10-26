"""Netlists: TI's unmodified switching model, and its compensation-network average.

The average plant keeps the vendor error-amplifier R/C/opamp, input feed-forward,
soft-start and enable pullup. It does not invent a regulated ideal 5V source.
XC6206 is a separately identified, typical-curve fitted PI/pass-current model.
"""
from pathlib import Path
H=Path(__file__).resolve().parent
LIB=(H/'models/TPS5430_TRANS.LIB').as_posix()

def safe_functions(lines):
    # ngspice has a statistical limit() in some parser contexts. Never rely
    # on PSpice's scoped compatibility helpers in our own main circuit.
    return [lines[0],'.func clamp(x,a,b) {min(max(x,a),b)}','.func sel(a,b,c) {a?b:c}']+[l.replace('limit(', 'clamp(').replace('if(', 'sel(') for l in lines[1:]]

def average_controller(c):
    return [
    '* Derived from TI TPS5430_TRANS compensation R/C and opamp parameters',
    f'Veref eref 0 {c.get("vref",1.221)}',
    'Bss 0 ss I={if(V(active)>.5,V(eref)*.001,-V(ss))}',
    f'Css ss 0 {8e-6*c.get("softstart",.008)/.008}',
    'Rss ss 0 1G','Bref ref 0 V={min(max(V(ss),0),V(eref))}',
    'R_EA3 ea ea_r3 3.27Meg','R_EA1 fb ea_r1 260k',
    'C_EA2 ea_r3 ea_in 30p','C_EA1 ea_r1 ea_in 20p',
    'R_EA2 fb ea_in 2.75Meg','C_EA3 ea ea_in 1p','V_EA vdd 0 3.3',
    'Xea ref ea_in vdd 0 ea stdopamp GAIN=206.538K RIN=20MEG RINC=1E9 ROUT=1 SLEWRATE=1.5Meg FPOLE1=14.96 FPOLE2=10MEG VDROPOH=0 VDROPOL=0 VOFFS=0 IBIAS=0 IOFFS=0',
    f'Venth enth 0 {c.get("en_threshold",1.15)}',f'Venhys enhys 0 {c.get("en_hysteresis",.45)}',
    'Vvinth vinth 0 5.3','Vvinhys vinhys 0 .33',
    'Xena en enth enhys enstate COMPHYS_BASIC_GEN',
    'Xvin vin vinth vinhys vinstate COMPHYS_BASIC_GEN',
    'Bactive active 0 V={if((V(enstate)>.5)&&(V(vinstate)>.5),1,0)}',
    'B_duty dutycommand 0 V={if((V(active)>.5)&&(V(fb)<1.125*V(eref)),limit((V(ea)-.3)/max(.0375*V(vin),.05),0,.87)*limit((4-I(L1))/.2,0,1),0)}',
    # A PWM cycle cannot respond infinitely fast to the OVP comparator.
    # 0.25us duty smoothing is below the 2us switching period and prevents
    # a continuous-time average model's zero-time chatter at the boundary.
    'R_duty dutycommand duty 1',f'C_duty duty 0 {c.get("pwm_tau",.25e-6)}',
    'B_ph phdrv 0 V={V(duty)*V(vin)-(1-V(duty))*.4}',
    'R_switch phdrv ph .1',
    # A series ideal diode prevents an averaged asynchronous buck from sinking
    # negative inductor current. Low-load DCM accuracy is a calibration limit.
    'Dav ph li_block DAVG','.model DAVG D(Is=1p Rs=.0001 N=.01 Eg=0 Xti=0 Tnom=25)',
    'Bin vin 0 I={max(0,V(duty)*I(L1))+(.003*V(active)+15u*(1-V(active)))*limit(V(vin),0,1)}',
    ]

def ldo(c):
    vref=3.3*c.get('ldo_ref_mult',1)
    kp=.04635*c.get('ldo_loop_mult',1)
    ki=1271.95*c.get('ldo_loop_mult',1)**2
    # R/C integrator + pass source: output capacitor and current limit remain
    # dynamic. A broad loop-multiplier sensitivity exposes the non-vendor fit.
    return [
      '* XC6206 typical family load-transient fit, NOT vendor transistor model',
      'R_ldoin vout ldo_lin .008',f'L_ldoin ldo_lin ldo_vin {c.get("ldo_trace_L",6e-9)}',
      'R_c10 ldo_vin c10internal .01',f'C_c10 c10internal 0 {c.get("c10_effective",6.4e-6)}',
      f'B_ldoref ldoref 0 V={{min({vref},max(0,V(ldo_vin)-.25))}}',
      f'B_pi_cmd icmd 0 V={{{kp}*(V(ldoref)-V(v33raw))+V(integ)}}',
      'R_passdriver icmd passcmd 1','C_passdriver passcmd 0 200n','C_ldo_pin v33raw 0 100p',
      # Smooth anti-windup back-calculation avoids an ideal zero-time
      # integration gate chattering at the pass-current clamp boundary.
      f'B_integ 0 integ I={{{ki}*(V(ldoref)-V(v33raw))*limit((V(ldo_vin)-1.8)/.1,0,1)+10000*(limit(V(icmd),0,.2)-V(icmd))-(1-limit((V(ldo_vin)-1.8)/.1,0,1))*V(integ)/.01}}',
      'C_integ integ 0 1','R_integ integ 0 1G',
      'B_pass ldo_vin v33raw I={limit(V(passcmd),0,.2)*limit((V(ldo_vin)-V(v33raw))/.25,0,1)}',
      'D_ldoreverse v33raw ldo_vin DREV','.model DREV D(Is=1n N=1.2 Rs=1)',
      f'R33trace v33raw v33lc {c.get("ldo_trace_R",.011)}',f'L33trace v33lc c33in {c.get("ldo_trace_L",6e-9)}',
      'R33esr c33in c33int .01',f'C33 c33int 0 {c.get("c33",22e-6)}',
      'B33load v33raw 0 I={limit(V(v33raw),0,1)*V(ldocurrent)}',
      ('Vldocurrent ldocurrent 0 PWL(0 0 14.999m 0 15m .005 28m .005 28.001m .01 45m .01)' if c.get('ldo_minimum_steps') else 'Vldocurrent ldocurrent 0 PWL(0 '+str(c.get('ldo_baseline',.01))+' 28m '+str(c.get('ldo_baseline',.01))+' 28.001m '+str(c.get('ldo_load',.01))+' 45m '+str(c.get('ldo_load',.01))+')'),
    ]

def make(c):
    if c.get('reference_minimal'):return minimal_reference(c)
    kind=c.get('kind','barrel')
    if kind=='pd':wave='PWL(0 0 .05m 5 4m 5 4.1m 9 8m 9 8.1m '+str(c.get('vin',12))+' 45m '+str(c.get('vin',12))+')'
    elif kind=='drop':wave='PWL(0 0 .2m '+str(c.get('vin',12))+' 35m '+str(c.get('vin',12))+' 40m 5 45m 0)'
    elif kind=='reverse':wave='PWL(0 0 .1m -12 45m -12)'
    elif kind=='steady':wave=str(c.get('vin',15))
    else:wave='PWL(0 0 '+str(c.get('ramp',.0002))+' '+str(c.get('vin',12))+' 45m '+str(c.get('vin',12))+')'
    switched=c.get('model')=='vendor'
    lines=[c['name'],'.include "'+LIB+'"',f'.param temper={c.get("temp",25)}',f'.temp {c.get("temp",25)}',
      'Vsource supply 0 '+wave, f'Rsource supply dc {c.get("rsource",.2)}',
      f'Rptc dc dc_protected {0 if kind=="pd" else c.get("rptc",.05)}',
      ('Rdirect dc_protected vin .001' if c.get('input_direct') else 'Dinput dc_protected vin D54'),'.model D54 D(Is=50u Rs=.02 N=1.2 Cjo=200p Tt=8n Bv=40 Ibv=1m)',
      'Dtvs 0 vin TVS15','.model TVS15 D(Is=1n N=1.5 Rs=.1 Bv=18 Ibv=1m Cjo=1n)',
      'Rbulk vin cbulk .3',f'Cbulk cbulk 0 {c.get("cin_bulk",100e-6)}',
      'Rceramic vin ccer .01',f'Cceramic ccer 0 {c.get("cin_ceramic",12e-6)}',
      'Rena vin en 100k','Renb en 0 15k',
      'Vswitch swcontrol 0 '+('PWL(0 0 30m 0 30.001m 1 36m 1 36.001m 0)' if c.get('switch_off') else '0'),
      'Soff en 0 swcontrol 0 SWOFF','.model SWOFF SW(Ron=.1 Roff=1e12 Vt=.5 Vh=.1)',
      'Rtop vout fb '+str(1e4*c.get('rtop_mult',1)),
      'Rbot fb 0 '+str(3300*c.get('rbot_mult',1)),
      'Rtrim1 fb rtrim '+str(1e5*c.get('rbot_mult',1)),
      'Rtrim2 rtrim 0 '+str(1e5*c.get('rbot_mult',1)),
    ]
    if switched:
      lines += ['XU boot en 0 nc nc1 0 ph vin fb TPS5430_TRANS MODE='+str(c.get('mode',0)), 'Cboot boot ph 10n', 'Dcatch 0 ph D54',f'Rl ph li {c.get("dcr",.045)}']
    else:
      lines += ['Benpull vin en I={5u*limit(V(vin),0,1)}']+average_controller(c)+[f'Rl li_block li {c.get("dcr",.045)}']
    lines += [f'L1 li vout {c.get("L",15e-6)}'+(' IC='+str(c.get('initial_current',.75)) if c.get('mode') else ''),
      'Resr vout capout '+str(c.get('esr',.04)),
      'Cout capout 0 '+str(c.get('cout',220e-6))+(' IC=5' if c.get('mode') else ''),
      'Rpath vout vcore '+str(c.get('path_R',.13675)+c.get('contact_R',.02)+c.get('return_R',.03)),
      'Ccore vcore 0 '+str(c.get('ccore',10e-6))+(' IC=5' if c.get('mode') else ''),
      'Vload load0 0 '+(f'PWL(0 .75 .4m .75 .401m 2.25 .8m 2.25 .801m .75)' if c.get('mode') else f'PWL(0 {c.get("core_baseline",.05)} {c.get("core_step_s",.02)} {c.get("core_baseline",.05)} {c.get("core_step_s",.02)+1e-6} {c.get("core_load",.5)} {c.get("core_return_s",.035)} {c.get("core_load",.5)} {c.get("core_return_s",.035)+1e-6} {c.get("core_baseline",.05)} {max(c.get("stop",.045),c.get("core_return_s",.035)+.010)} {c.get("core_baseline",.05)})'),
      'Bcore vcore 0 I={limit(V(vcore),0,1)*V(load0)}',
      'Rbleed vout 0 10k',
      'Bhdmi vout 0 I={max(V(vout),0)*'+str(c.get('hdmi_load',.05))+'/5}',
    ]
    if c.get('include_ldo',True):lines+=ldo(c)
    else:lines += ['R33dummy v33raw 0 1k','Ractive_dummy active 0 1k'] if switched else ['R33dummy v33raw 0 1k']
    if not switched and c.get('mode'):lines+=['.ic V(ss)=1.221 V(ea)=.4875']
    lines += ['.options reltol=.002 abstol=1n vntol=10u itl4=200 method=gear',
      '.save v(vout) v(vcore) v(v33raw) v(vin) v(en) '+('' if switched else 'v(active) ')+'i(L1) i(Vsource)',
      f'.tran {c.get("maxstep",2e-6)} {c.get("stop",.045)} 0 {c.get("maxstep",2e-6)} uic','.end']
    if c.get('tab_load',0)>0:
        lines.insert(-3,f'Btab vin 0 I={{{c["tab_load"]}*limit((V(vin)-5.5)/.5,0,1)}}')
    if c.get('time_mult',1)!=1:
        import re
        def val(s):
            for suff,m in [('m',1e-3),('u',1e-6),('n',1e-9)]:
                if s.endswith(suff):return float(s[:-1])*m
            return float(s)
        out=[]
        for l in lines:
            if 'PWL(' in l:
                a,tail=l.split('PWL(',1);body,z=tail.split(')',1);parts=body.split()
                for i in range(0,len(parts),2):parts[i]=str(val(parts[i])*c['time_mult'])
                l=a+'PWL('+' '.join(parts)+')'+z
            out.append(l)
        lines=out
    return safe_functions(lines)

def minimal_reference(c):
    """Manufacturer-loop bench without uncharacterized Core/LDO parasitics."""
    switched=c.get('model')=='vendor'
    lines=[c['name'],'.include "'+LIB+'"','.param temper=25',
      'Vsource src 0 PWL(0 0 10u 0 20u 12)','Rsource src vin .1','Cin vin 0 20u',
      'Rena vin en 100k','Renb en 0 15k','Rtop vout fb 10k','Rbot fb 0 3246.43384']
    if switched:lines+=['XU boot en 0 nc nc1 0 ph vin fb TPS5430_TRANS MODE=0','Cboot boot ph 10n','Dcatch 0 ph D54','Rdcr ph li .045']
    else:lines+=['Ienpull vin en 5u']+average_controller(c)+['Rdcr li_block li .045']
    lines += ['L1 li vout 15u','Resr vout capout .04','Cout capout 0 220u','Rload vout 0 10',
      '.model D54 D(Is=50u Rs=.02 N=1.2 Cjo=200p Tt=8n Bv=40 Ibv=1m)',
      'Rcore vout vcore .001','Rcore_bleed vcore 0 1G','R33dummy v33raw 0 1k',
      'Istep vout 0 PWL(0 0 9m 0 9.001m .5 10m .5 10.001m 0)',
      '.options reltol=.003 abstol=1n vntol=10u itl4=200 method=gear',
      '.save v(vout) v(vcore) v(v33raw) v(vin) v(en) '+('' if switched else 'v(active) ')+'i(L1) i(Vsource)',
      f'.tran {c.get("maxstep",1e-7)} {c.get("stop",.011)} 0 {c.get("maxstep",1e-7)} uic','.end']
    return safe_functions(lines)
