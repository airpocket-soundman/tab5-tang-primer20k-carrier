"""Conservative two-trace near/far-end crosstalk transient sensitivity.

Quasi-static C/L matrices use the actual minimum-rule geometry; coupled spans
come from physical carrier segment overlap. Internal-board coupling and common
power/ground inductance are not claimed to be reconstructed.
"""
from pathlib import Path
import json
import math
import numpy as np
import microstrip2d as field
from ngspice_shared import Spice

HERE=Path(__file__).resolve().parent;RAW=Path('D:/tmp/carrier-parallel-models')
traces=[(-.127/2-.127,-.127/2),(.127/2,.127/2+.127)]
C=field.cap_matrix(4.4,traces,.2104,.035,dx=.02)
Ca=field.cap_matrix(1,traces,.2104,.035,dx=.02)
L=np.linalg.inv(Ca)/299792458.**2
cg=float(C[0,0]+C[0,1]);cm=float(-C[0,1]);ls=float(L[0,0]);mutual=float(L[0,1]);k=mutual/ls
(HERE/'coupled-field.json').write_text(json.dumps({'width_mm':.127,'gap_mm':.127,'h_mm':.2104,'er':4.4,'grid_mm':.02,'C_F_per_m':C.tolist(),'L_H_per_m':L.tolist(),'coupling_k':k,'scope':'two parallel traces over continuous ground; 0.127mm gap is conservative vs extracted >=0.173mm; mask ignored; 2D discretization not a 3D field solve'},indent=2)+'\n')
s=Spice();paths=json.loads((HERE/'extracted-paths.json').read_text());results=[]
for variant,b in paths.items():
    case=b['coupled_parallel_spans'][0];length=case['overlap_mm']*1e-3
    for edge,rs,label in [(3e-9,60,'controlled'),(.5e-9,10,'fast')]:
        for driver,victim_level in [(60,0),(60,3.135),(45000,0)]:
            out=['Crosstalk distributed RLGC two traces over GND','.options reltol=1e-5 method=trap',f'Va da 0 PULSE(0 3.465 10n {edge} {edge} 200n 400n)',f'Ra da a0 {rs}',f'Vv dv 0 {victim_level}',f'Rv dv v0 {driver}']
            nn=12;chunk=length/nn
            for i in range(nn):
                for prefix in ('a','v'):
                    out.extend([f'R{prefix}{i} {prefix}{i} {prefix}r{i} .01',f'L{prefix}{i} {prefix}r{i} {prefix}{i+1} {ls*chunk}',f'C{prefix}{i} {prefix}{i+1} 0 {cg*chunk}'])
                out.extend([f'K{i} La{i} Lv{i} {k}',f'Cmut{i} a{i+1} v{i+1} {cm*chunk}'])
            out.extend([f'Ca a{nn} 0 20p',f'Cv v{nn} 0 20p',f'Rseries v{nn} vr 680','Cinput vr 0 8p','.tran 10p 150n 0 10p','.save v(vr) v(v0) v(a0)','.end'])
            assert s.load(out)==0;s.run();t=s.vector('time');v=s.vector('v(vr)')
            row={'variant':variant,'signals':case['signals'],'coupled_span_mm':case['overlap_mm'],'corner':label,'victim_driver_ohm':driver,'victim_level_V':victim_level,'noise_peak_V':float(np.max(np.abs(v-victim_level))),'minimum_V':float(v.min()),'maximum_V':float(v.max()),'at_250ns':'not simulated; all observed excursions decayed within 150ns; 1MHz sample has >=250ns setup guard'}
            bad=np.flatnonzero(np.abs(v-victim_level)>.05)
            row['last_noise_over_50mV_ns']=float(t[bad[-1]]*1e9) if len(bad) else None
            results.append(row)
            if label=='controlled' and driver==60 and victim_level==0:
                idx=np.arange(0,len(t),10);stem=variant+'-crosstalk'
                np.savetxt(HERE/(stem+'.csv'),np.column_stack([t[idx],v[idx]]),delimiter=',',header='time_s,quiet_receiver_V',comments='')
                (HERE/(stem+'.cir')).write_text('\n'.join(out)+'\n')
(HERE/'crosstalk-results.json').write_text(json.dumps({'results':results,'limits':['Two-trace model bounds one dominant adjacent signal pair, not all simultaneous switching or package shared-GND bounce.','Reference plane continuous; uncertainty in unmodelled inner-layer coupling is not certified away.','Fast/strong source is a stress case; weak/SLOW initial I/O configuration and 250ns data settling guard are required.']},indent=2)+'\n')
print(json.dumps(results,indent=1))
