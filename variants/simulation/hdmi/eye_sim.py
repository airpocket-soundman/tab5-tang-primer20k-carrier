"""Conditional 4-port/time-domain TMDS PoC eye model, never HDMI compliance.

Actual carrier copper + official Core P/N lengths. Calibrated linear LVDS source
matches 250/350mV across 100ohm; source impedance is an assumed sensitivity.
Receiver is 50ohm/line to 3.3V, not a measured sink. AC coupling is 100nF/line.
No transistor clamp, PLL jitter, crosstalk, cable S-parameters or calibrated
socket model is available. Source edge and added cable loss are explicit cases.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['lite-a-dual','lite-b-barrel'],required=True);ap.add_argument('--tdr-only',action='store_true')
a=ap.parse_args();HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
manifest=json.loads((HERE/'input_manifest.json').read_text())
record=manifest['variants'][a.variant]
assert hashlib.sha256((ROOT/record['source_pcb']).read_bytes()).hexdigest()==record['source_pcb_sha256'],'PCB changed; prepare inputs again'
sys.path.insert(0,str(HERE/'models'/a.variant))
import tmds_sparam as sp
sp.tc.load();sp.R_BIAS=510
F=np.r_[np.geomspace(1,10e6,90),np.linspace(10.001e6,3.3e9,490)]
sp.F=F
CORE=json.loads((HERE/'core_lengths.json').read_text())['pairs']
CASES=[
 dict(name='nominal',core_z=100,core_ee=3,esd_pf=.35,socket_nH=1,socket_pF=.3,VOD=.350,Rs=100,rise_ns=.3,Rrx=50,Vdd=3.3,cable_loss_db=0,Cac_nF=100),
 dict(name='weak_high_Rs',core_z=85,core_ee=3.6,esd_pf=.5,socket_nH=3,socket_pF=1,VOD=.250,Rs=1000,rise_ns=.3,Rrx=55,Vdd=3.135,cable_loss_db=3,Cac_nF=80),
 dict(name='weak_slow_low_Rs',core_z=115,core_ee=2.5,esd_pf=.5,socket_nH=3,socket_pF=1,VOD=.250,Rs=25,rise_ns=.6,Rrx=45,Vdd=3.135,cable_loss_db=3,Cac_nF=80),
 dict(name='low_Z_fast',core_z=85,core_ee=2.5,esd_pf=.2,socket_nH=0,socket_pF=0,VOD=.250,Rs=25,rise_ns=.3,Rrx=45,Vdd=3.3,cable_loss_db=0,Cac_nF=100),
 dict(name='weak_slow_high_Rs',core_z=115,core_ee=3.6,esd_pf=.5,socket_nH=3,socket_pF=1,VOD=.250,Rs=1000,rise_ns=.6,Rrx=55,Vdd=3.135,cable_loss_db=3,Cac_nF=80)]
for case,scale in zip(CASES,(1.,.9,1.1,.9,1.1)):case['carrier_zscale']=scale
if a.tdr_only:
    CASES=CASES[:1];CASES[0]['Cac_nF']=1e12
OUT=HERE/('tdr' if a.tdr_only else 'results')/a.variant;OUT.mkdir(parents=True,exist_ok=True)

def diagonal_line(z,ee,lp,ln):
    g=sp._loss(F,z,ee)+1j*2*np.pi*F*np.sqrt(ee)/sp.C0
    A=np.zeros((len(F),2,2),complex);B=A.copy();C=A.copy()
    for i,L in enumerate((lp,ln)):
        A[:,i,i]=np.cosh(g*L);B[:,i,i]=z*np.sinh(g*L);C[:,i,i]=np.sinh(g*L)/z
    return sp.blocks(A,B,C,A)

def channel(tag,p,n,o):
    if tag not in sp._SEC:sp._SEC[tag]=sp.sections(p,n)
    sec=sp._SEC[tag];zero=np.zeros(len(F),complex);jw=2j*np.pi*F
    lengths=CORE[tag]
    M=diagonal_line(o['core_z']/2,o['core_ee'],lengths['P']['all_mm']*1e-3,lengths['N']['all_mm']*1e-3)
    def add(m):
        nonlocal M
        M=M@m
    if o['socket_nH']:add(sp.series_line(F,jw*o['socket_nH']*1e-9/2,jw*o['socket_nH']*1e-9/2))
    if o['socket_pF']:add(sp.shunt_line(F,jw*o['socket_pF']*1e-12*2,jw*o['socket_pF']*1e-12*2))
    for s in sec['core']:add(sp.coupled(F,s['zo']*o['carrier_zscale'],s['eo'],s['ze']*o['carrier_zscale'],s['ee'],s['dl']))
    zcap=1/(jw*o['Cac_nF']*1e-9)+jw*.7e-9+.05
    add(sp.series_line(F,zcap,zcap))
    chain=sec['C'];s_esd=sp._x_cross(chain,sp.ESD_XC)
    ycd=jw*o['esd_pf']*1e-12*2
    events=[(s_esd,'P',ycd),(s_esd,'N',ycd)]
    for line in ('P','N'):
        b=sec['branches'].get(line)
        if b:events.append((b['tap_s'],line,sp.branch_admittance(F,b['length'])))
    groups=sp._shunt_groups(events,zero);j=0
    for s in chain:
        while j<len(groups) and groups[j][0]<=s['s0']+1e-12:
            add(sp.shunt_line(F,groups[j][1],groups[j][2]));j+=1
        add(sp.coupled(F,s['zo']*o['carrier_zscale'],s['eo'],s['ze']*o['carrier_zscale'],s['ee'],s['dl']))
    while j<len(groups):add(sp.shunt_line(F,groups[j][1],groups[j][2]));j+=1
    add(sp.uncoupled(F,50,11e-3,2.5))
    return M

def transfer(M,o):
    A,B,C,D=M[:,:2,:2],M[:,:2,2:],M[:,2:,:2],M[:,2:,2:]
    G=A+B/o['Rrx']+(o['Rs']/2)*(C+D/o['Rrx'])
    v=np.tile(np.array([.5,-.5])*(1+o['Rs']/100),(len(F),1))
    out=np.linalg.solve(G,v[...,None])[...,0]
    hd=out[:,0]-out[:,1];hc=(out[:,0]+out[:,1])/2
    attenuation=10**(-o['cable_loss_db']/20)
    return hd*attenuation,hc*attenuation

def delay(H):
    use=(F>=20e6)&(F<=120e6)
    return float(-np.polyfit(2*np.pi*F[use],np.unwrap(np.angle(H[use])),1)[0])

state=0x5173;half=[]
for _ in range(2000):
    half.append(1 if state&0x4000 else -1)
    state=((state<<1)|(((state>>14)^(state>>13))&1))&0x7fff
bits=np.r_[half,-np.array(half)]
SPB=32;src=np.repeat(bits,SPB);N=len(src)
rows=[];clock_rows=[];start=time.time()
for ci,o in enumerate(CASES):
    response={}
    for tag,p,n in sp.tc.PAIRS:
        M=channel(tag,p,n,o);hd,hc=transfer(M,o)
        response[tag]=(hd,hc,delay(hd))
        if ci==0:
            s11,s21,scd=sp.mixed(sp.abcd_to_s4(M))
            np.savetxt(OUT/(tag+'-frequency.csv'),np.column_stack([F,hd.real,hd.imag,s11.real,s11.imag,s21.real,s21.imag]),delimiter=',',header='f_Hz,Hvoltage_real,Hvoltage_imag,Sdd11_real,Sdd11_imag,Sdd21_real,Sdd21_imag',comments='')
    if a.tdr_only:continue
    for rate_name,rate in [('480p',251.75e6),('720p',742.5e6)]:
        UI=1/rate;dt=UI/SPB;freq=np.fft.rfftfreq(N,dt)
        tau=o['rise_ns']*1e-9/np.log(9)
        source_shape=1/(1+2j*np.pi*freq*tau)
        # Smooth bandwidth limit is an explicit model limit, not FPGA edge data.
        window=np.ones_like(freq);roll=(freq>2.5e9)&(freq<3.3e9)
        window[roll]=.5*(1+np.cos(np.pi*(freq[roll]-2.5e9)/.8e9));window[freq>=3.3e9]=0
        X=np.fft.rfft(src*o['VOD'])*source_shape*window
        # Forwarded pixel clock is five high / five low serial UIs, not PRBS.
        clock_src=np.where((np.arange(N)//(5*SPB))%2==0,1.,-1.)
        hdck=response['CK'][0]
        Hck=np.interp(freq,F,hdck.real,left=0,right=0)+1j*np.interp(freq,F,hdck.imag,left=0,right=0);Hck[0]=0
        clock_wave=np.fft.irfft(np.fft.rfft(clock_src*o['VOD'])*source_shape*window*Hck,n=N)
        def crossing(kbit,rising=True):
            hint=kbit*SPB+(response['CK'][2]+tau*np.log(2))/dt
            lo=max(1,int(hint-SPB));hi=min(N-1,int(hint+SPB))
            candidates=[]
            for ii in range(lo,hi):
                if (clock_wave[ii]<=0<clock_wave[ii+1]) if rising else (clock_wave[ii]>=0>clock_wave[ii+1]):
                    candidates.append(ii-clock_wave[ii]/(clock_wave[ii+1]-clock_wave[ii]))
            assert candidates,'No forwarded-clock crossing'
            return min(candidates,key=lambda x:abs(x-hint))
        cr=crossing(1000);cf=crossing(1005,False);cr2=crossing(1010)
        clock_delay=cr*dt-1000*UI
        clock_rows.append(dict(case=o['name'],mode=rate_name,pixel_clock_MHz=rate/10e6,
            actual_clock_crossing_delay_ns=clock_delay*1e9,duty_fraction=(cf-cr)/(cr2-cr),
            period_ns=(cr2-cr)*dt*1e9,peak_diff_V=float(max(abs(clock_wave)))))
        idx=np.arange(998*SPB,1022*SPB,2)
        np.savetxt(OUT/f'{rate_name}-{o["name"]}-forwarded-clock.csv',np.column_stack([(idx-1000*SPB)*dt*1e9,clock_src[idx]*o['VOD'],clock_wave[idx]]),delimiter=',',header='t_ns,source_clock_differential_V,receiver_clock_differential_V',comments='')
        fig,axes=plt.subplots(2,2,figsize=(10,6),sharex=True,sharey=True)
        for ax,(tag,_,_) in zip(axes.flat,sp.tc.PAIRS):
            hd,hc,gd=response[tag]
            Hd=np.interp(freq,F,hd.real,left=0,right=0)+1j*np.interp(freq,F,hd.imag,left=0,right=0);Hd[0]=0
            Hc=np.interp(freq,F,hc.real,left=0,right=0)+1j*np.interp(freq,F,hc.imag,left=0,right=0);Hc[0]=0
            wave=np.fft.irfft(X*Hd,n=N);cm=np.fft.irfft(X*Hc,n=N)
            k=np.arange(32,len(bits)-32)
            ph=np.linspace(0,1,129)
            signed=[]
            for phase in ph:
                pos=(k+phase)*SPB+clock_delay/dt
                val=np.interp(pos,np.arange(N),wave)
                signed.append(float(np.min(bits[k]*val)))
            signed=np.array(signed)
            centre=signed[64]
            good=signed>=.1
            centre_run=0
            if good[64]:
                l=r=64
                while l>0 and good[l-1]:l-=1
                while r<len(good)-1 and good[r+1]:r+=1
                centre_run=ph[r]-ph[l]
            vcm=o['Vdd']*510/(510+o['Rrx'])
            row=dict(case=o['name'],mode=rate_name,bitrate_Mbps=rate/1e6,pair=tag,
                signed_center_min_V=float(centre),eye_height_at_clock_center_V=float(2*centre),
                width_over_100mV_UI=float(centre_run),data_minus_clock_delay_ps=(gd-response['CK'][2])*1e12,
                source_filter_clock_shift_ps=(clock_delay-response['CK'][2])*1e12,
                source_VOD_V=o['VOD'],receiver_DC_common_V=vcm,common_AC_peak_V=float(max(abs(cm))),
                max_abs_differential_V=float(max(abs(wave))),
                pass_internal=bool(centre>=.1 and centre_run>=.5 and abs(gd-response['CK'][2])<.2*UI),
                source_pattern='PRBS stress' if tag=='CK' else 'PRBS data',
                note='CK PRBS row is an additional channel stress; actual forwarded 5/5 clock is saved separately')
            rows.append(row)
            for kk in k[::17][:180]:
                pos=(kk+np.linspace(-.5,1.5,2*SPB+1))*SPB+clock_delay/dt
                y=np.interp(pos,np.arange(N),wave)
                ax.plot(np.linspace(-.5,1.5,len(y)),y*1e3,color='#135e96',alpha=.10,lw=.6)
            ax.axhline(100,color='r',lw=.5);ax.axhline(-100,color='r',lw=.5);ax.axvline(.5,color='k',lw=.5)
            ax.set_title(f'{tag}: centre {centre*1e3:.0f}mV, width {centre_run:.2f}UI')
            ax.set_xlim(-.2,1.2);ax.set_ylim(-450,450);ax.grid(alpha=.15)
            if ci in (0,2):
                first=1200*SPB;last=first+24*SPB
                indices=np.arange(first,last,2)
                np.savetxt(OUT/f'{rate_name}-{o["name"]}-{tag}-wave.csv',np.column_stack([(indices-first)*dt*1e9,src[indices]*o['VOD'],wave[indices],cm[indices]+vcm]),delimiter=',',header='t_ns,ideal_loaded_source_V,receiver_differential_V,receiver_common_V',comments='')
        fig.suptitle(f'{a.variant} / {rate_name} / {o["name"]}\nConditional linear source; 3.3GHz bandwidth; no jitter/noise/IBIS')
        fig.supxlabel('serial UI (clock-aligned)');fig.supylabel('receiver differential mV')
        fig.tight_layout();fig.savefig(OUT/f'{rate_name}-{o["name"]}-eye.png',dpi=140);plt.close(fig)
    print(a.variant,o['name'],'done',round(time.time()-start,1),flush=True)
if a.tdr_only:
    fig,ax=plt.subplots(figsize=(9,5));tdr=[]
    for tag,_,_ in sp.tc.PAIRS:
        data=np.loadtxt(OUT/(tag+'-frequency.csv'),delimiter=',',skiprows=1)
        freq=np.fft.rfftfreq(4096,20e-12)
        r=np.interp(freq,data[:,0],data[:,3],left=data[0,3],right=0)+1j*np.interp(freq,data[:,0],data[:,4],left=0,right=0)
        window=np.ones_like(freq);roll=(freq>2.5e9)&(freq<3.3e9)
        window[roll]=.5*(1+np.cos(np.pi*(freq[roll]-2.5e9)/.8e9));window[freq>=3.3e9]=0
        h=np.fft.fftshift(np.fft.irfft(r*window,n=4096));rho=np.cumsum(h)
        z=100*(1+rho)/(1-rho);tt=(np.arange(4096)-2048)*20e-12
        use=(tt>=-.3e-9)&(tt<3e-9)
        ax.plot(tt[use]*1e9,z[use],label=tag)
        np.savetxt(OUT/(tag+'-tdr.csv'),np.column_stack((tt[use],rho[use],z[use])),delimiter=',',header='t_s,reflection_step,equivalent_Z_ohm',comments='')
        tdr.append(dict(pair=tag,min_Z_ohm=float(z[use].min()),max_Z_ohm=float(z[use].max())))
    ax.axhline(100,color='k',lw=.5);ax.set(xlabel='time ns',ylabel='band-limited equivalent ohm',title='Early-time model TDR; AC capacitors shorted for ns scale; 100ohm reference')
    ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(OUT/'early_tdr.png',dpi=140)
    (OUT/'tdr_summary.json').write_text(json.dumps(dict(variant=a.variant,source_pcb_sha256=record['source_pcb_sha256'],scope='Approximate band-limited early-time TDR of the analytical channel. Not measured TDR or full-board EM. 100nF is replaced by a short only for the ns-scale view; microsecond AC settling is separate.',results=tdr),indent=2)+'\n')
    print('TDR done',a.variant);raise SystemExit
result=dict(variant=a.variant,source_pcb_sha256=record['source_pcb_sha256'],scope=__doc__,
    deterministic_PRBS_bits=len(bits),samples_per_UI=SPB,frequency_points=len(F),
    thresholds=dict(signed_center_min_V=.1,width_over_100mV_UI=.5,abs_data_clock_skew_max_UI=.2),
    conditions=CASES,results=rows,forwarded_clock=clock_rows,elapsed_s=time.time()-start,
    limits=['Not an HDMI compliance mask or measured receiver tolerance.','Core impedance/epsilon, source impedance/edge and socket L/C are sensitivity assumptions, not calibration or guaranteed bounds.','Actual cable, die/package, connector, nonlinear clamps, crosstalk, noise and receiver PLL are not characterized.','The common-mode DC estimate assumes the receiver termination is powered; AC startup transient is treated separately.'])
(OUT/'eye_results.json').write_text(json.dumps(result,indent=2)+'\n')
with (OUT/'eye_results.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({'variant':a.variant,'cases':len(rows),'480p_misses':sum(not r['pass_internal'] for r in rows if r['mode']=='480p'),'720p_misses':sum(not r['pass_internal'] for r in rows if r['mode']=='720p'),'elapsed_s':time.time()-start}))
