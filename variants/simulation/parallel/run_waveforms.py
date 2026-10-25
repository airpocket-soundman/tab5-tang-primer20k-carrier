"""Finite-edge distributed RLC/link-switch transient sensitivity, ngspice.

Uses extracted physical carrier lengths. Driver R/slew and unknown internal
board paths are deliberately swept assumptions, not vendor IBIS guarantees.
"""
from pathlib import Path
import json
import math
import sys
import numpy as np
from ngspice_shared import Spice

HERE=Path(__file__).resolve().parent
RAW=Path('D:/tmp/carrier-parallel-models');RAW.mkdir(exist_ok=True)
PARAMS={
 'nominal':dict(z=85,ee=3.2,rs=35,tr=2e-9,ron=4,cio=9e-12,tab_mm=30,core_mm=30,c_tab=2e-12,c_core=5e-12,vdd=3.3),
 'slow':dict(z=120,ee=4.1,rs=100,tr=8e-9,ron=9,cio=11e-12,tab_mm=80,core_mm=80,c_tab=5e-12,c_core=8e-12,vdd=3.135),
 'fast':dict(z=120,ee=2.5,rs=10,tr=.5e-9,ron=4,cio=11e-12,tab_mm=80,core_mm=80,c_tab=2e-12,c_core=8e-12,vdd=3.465),
 'controlled':dict(z=120,ee=4.1,rs=60,tr=3e-9,ron=9,cio=11e-12,tab_mm=80,core_mm=80,c_tab=5e-12,c_core=8e-12,vdd=3.465)}

def deck(signal,p,direction,resistance=33,period=200e-9,cycles=1):
    out=['Tab5-Core parallel finite-edge distributed RLC sensitivity',
         '.options reltol=1e-5 abstol=1e-12 method=trap', '.param pi=3.14159265359']
    seq=[0]
    def node():seq[0]+=1;return 'n'+str(seq[0])
    def line(a,b,length_mm,tag,z=None):
        z=z or p['z']; td=length_mm*1e-3*math.sqrt(p['ee'])/299792458
        scale=p.get('segments_scale',1)
        nn=max(2,min(10*scale,math.ceil(length_mm/8)*scale))
        l=td*z/nn;c=td/z/nn
        for i in range(nn):
            nxt=b if i==nn-1 else node();mid=node()
            out.extend([f'R{tag}{i} {a} {mid} {max(length_mm*.004/nn,.005):.12g}',f'L{tag}{i} {mid} {nxt} {max(l,1e-12):.12g}',f'C{tag}{i} {nxt} 0 {max(c,1e-15):.12g}'])
            a=nxt
    host,core='host','core'
    line(host,'header',p['tab_mm'],'tab',85)
    secs=signal['sections']
    line('header','swa0',secs['M']['length_mm'],'m')
    out.extend(['Lpka swa0 swa 3.553n',f'Csw_a swa 0 {p["cio"]:.12g}',f'Rswitch swa swb {p["ron"]}',f'Csw_b swb 0 {p["cio"]:.12g}','Lpkb swb swb0 3.553n'])
    line('swb0','iso',secs['ISO']['length_mm'],'iso')
    out.extend([f'Rseries iso after_r {resistance}','Lseries after_r after_l .5n'])
    line('after_l','socket_a',secs['F']['length_mm'],'f')
    out.extend(['Lsocket socket_a socket_b 2n','Csocket socket_b 0 1p'])
    line('socket_b',core,p['core_mm'],'core',85)
    via_n=signal['total_carrier_vias']
    if via_n:
        # Conservatively aggregate all via barrels and their fringe capacitance
        # at the receiver end. Their physical positions are not inferred here.
        recv=core if direction=='write' else host
        out.extend([f'Lvia {recv} recv {via_n*.9e-9:.12g}',f'Cvia recv 0 {via_n*.3e-12:.12g}'])
    else:recv=core if direction=='write' else host
    source=host if direction=='write' else core
    cap=p['c_core'] if direction=='write' else p['c_tab']
    out.extend([f'Vdrive drive 0 PULSE(0 {p["vdd"]} 10n {p["tr"]} {p["tr"]} {period/2} {period})',f'Rdriver drive dpkg {p["rs"]}','Ldriver dpkg '+source+' 2n',f'Cin {recv} 0 {cap:.12g}',f'Rleak {recv} 0 1e9'])
    out.extend([f'.tran 20p {cycles*period+10e-9:.12g} 0 20p',f'.save v(drive) v({recv}) v({source})','.end'])
    return out,recv

def analyse(t,v,p):
    hi=p['vdd'];valid=t>=10e-9
    tt=t[valid]-10e-9;vv=v[valid]
    # Settling after rising input, before its deliberate falling transition.
    rising=tt<p.get('rise_window_s',80e-9)
    bad=np.flatnonzero(np.abs(vv[rising]-hi)>.05*hi)
    settle=float(tt[rising][bad[-1]]) if len(bad) else 0
    return dict(max_V=float(v.max()),min_V=float(v.min()),overshoot_V=float(v.max()-hi),undershoot_V=float(-v.min()),settle_5percent_ns=settle*1e9,
                high_at_60ns_V=float(np.interp(70e-9,t,v)),rise_VIH_core_ns=float(np.interp(2.0,vv[:np.argmax(vv)+1],tt[:np.argmax(vv)+1]))*1e9)

def main():
    paths=json.loads((HERE/'extracted-paths.json').read_text())
    spice=Spice();results=[];worst={};shown={}
    full='--full' in sys.argv
    resistances=[33] if full else [33,68,100,150,220]
    for variant,board in paths.items():
        signals=board['signals'] if full else {k:board['signals'][k] for k in ('D0','CLK','RDY')}
        for sig,signal in signals.items():
            for corner,p in PARAMS.items():
                for direction in ('write','read'):
                    for rr in resistances:
                        lines,recv=deck(signal,p,direction,rr)
                        spice.messages.clear();spice.exits.clear()
                        assert spice.load(lines)==0
                        spice.run()
                        t=spice.vector('time');v=spice.vector('v('+recv+')')
                        assert len(t)>1000 and t[-1]>=200e-9,(variant,sig,corner,spice.messages[-8:])
                        metric=analyse(t,v,p)
                        row=dict(variant=variant,signal=sig,direction=direction,corner=corner,Rseries_ohm=rr,**metric)
                        results.append(row)
                        tag=(variant,corner,rr)
                        if tag not in worst or metric['overshoot_V']>worst[tag]['overshoot_V']:
                            worst[tag]=row
                        if corner in ('fast','controlled','slow') and sig=='CLK' and rr in (33,100):
                            stem=variant+'-'+direction+'-'+corner+'-'+str(rr)
                            (RAW/(stem+'.cir')).write_text('\n'.join(lines)+'\n')
                            # Deliberately retain only an early, decimated window.
                            mask=t<80e-9
                            idx=np.flatnonzero(mask)[::5]
                            np.savetxt(RAW/(stem+'.csv'),np.column_stack([t[idx],v[idx]]),delimiter=',',header='time_s,receiver_V',comments='')
        print(variant,'completed',len(results),'runs',flush=True)
    name='waveforms-full.json' if full else 'resistor-sensitivity.json'
    (HERE/name).write_text(json.dumps({'results':results,'worst_by_variant_corner_resistance':list(worst.values()),'parameters':PARAMS,'model_limits':['GPIO driver R/slew and internal board paths are explicit assumptions, not full GPIO IBIS models.','Unclamped receiver voltages are reported; no fabricated clamp model is used to hide overshoot.','A lumped multi-section RLC approximation replaces each physical transmission-line section; via parasitics are conservative aggregate estimates.']},indent=2)+'\n')
    print('worst controlled',max(r['overshoot_V'] for r in results if r['corner']=='controlled'))
    print('worst fast',max(r['overshoot_V'] for r in results if r['corner']=='fast'))

if __name__=='__main__':main()
