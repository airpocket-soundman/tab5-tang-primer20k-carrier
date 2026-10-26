"""Coupled RLGC transient equivalents from routed geometry. No solver here."""
import math
C0=299792458.0
CORNERS={
 'nominal':dict(amp=.70,rs=50.,edge=120e-12,zscale=1.,esc=.70e-12,rxcap=.7e-12,package_l=.7e-9),
 'fast_lowZ':dict(amp=.80,rs=40.,edge=60e-12,zscale=.9,esc=.35e-12,rxcap=.4e-12,package_l=.4e-9),
 'weak_highC':dict(amp=.60,rs=60.,edge=220e-12,zscale=1.1,esc=1.2e-12,rxcap=1.5e-12,package_l=1.2e-9),
}

def prbs7():
    state=0x7f;bits=[]
    for _ in range(127):
        bits.append(state&1);feedback=((state>>6)^(state>>5))&1;state=((state<<1)|feedback)&0x7f
    assert len(set(bits))==2
    return bits

def deck(sections,lane,rate,corner,bias=499,pattern='prbs7',step_mm=2.):
    c=CORNERS[corner];ui=1/rate;edge=min(c['edge'],.35*ui)
    bits=([int(i%10<5) for i in range(127)] if lane=='CK' else prbs7() if pattern=='prbs7' else ([1,1,0,1,0,1,0,1,0,0]*13)[:127])
    lines=[f'HDMI {lane} {rate} {corner} {pattern} coupled RLGC analytical driver',
           '* Engineering waveform evaluation; not HDMI compliance, IBIS or a cable model.',
           'Vterm vterm 0 3.3']
    for pol,sgn in [('p',1),('n',-1)]:
        points=[(0,1.2),(ui,1.2)];last=1.2
        for i,bit in enumerate(bits):
            target=1.2+sgn*(1 if bit else -1)*c['amp']/2;t=(i+1)*ui
            if target!=last:points.extend([(t,last),(t+edge,target)])
            last=target
        points.append((129*ui,last))
        lines.append('Vsrc'+pol+' src'+pol+' 0 PWL('+' '.join(f'{t:.14g} {y:.14g}' for t,y in points)+')')
        lines.append(f'Rsrc{pol} src{pol} tx{pol} {c["rs"]}')
    counter=[0];previous=['txp','txn'];delay=0.
    def cell(dl,zo,eo,ze,ee):
        nonlocal previous,delay
        i=counter[0];counter[0]+=1
        zo*=c['zscale'];ze*=c['zscale']
        lo=zo*math.sqrt(eo)/C0*dl;le=ze*math.sqrt(ee)/C0*dl
        co=math.sqrt(eo)/(zo*C0)*dl;ce=math.sqrt(ee)/(ze*C0)*dl
        ls=(lo+le)/2;mut=(le-lo)/2;cm=max((co-ce)/2,0.)
        # Constant-frequency loss envelope at Nyquist, not a broadband skin model.
        surface=math.sqrt(math.pi*(rate/2)*(4e-7*math.pi)/5.8e7)
        resistance=max(.0001,surface/(.2e-3)*.5*dl)
        after=[f'p{i}',f'n{i}']
        for j,pol in enumerate(['p','n']):
            middle=f'r{pol}{i}';lines.extend([f'R{pol}{i} {previous[j]} {middle} {resistance:.12g}',f'L{pol}{i} {middle} {after[j]} {ls:.12g}',f'Cg{pol}{i} {after[j]} 0 {ce:.12g}'])
            conductance=2*math.pi*(rate/2)*ce*.02
            lines.append(f'Rg{pol}{i} {after[j]} 0 {1/max(conductance,1e-15):.12g}')
        if abs(mut)>1e-20:lines.append(f'K{i} Lp{i} Ln{i} {mut/ls:.12g}')
        if cm>1e-20:lines.append(f'Cm{i} {after[0]} {after[1]} {cm:.12g}')
        previous=after;delay+=math.sqrt(eo)/C0*dl
    # Internal Core path: assumed100ohm differential,38.4mm,not vendor SI data.
    for _ in range(20):cell(.0384/20,50,3.,50,3.)
    for pol,node in zip(['p','n'],previous):
        lines.append(f'Lsocket{pol} {node} socket{pol} {c["package_l"]:.12g}')
        lines.append(f'Csocket{pol} socket{pol} 0 {c["rxcap"]:.12g}')
    previous=['socketp','socketn']
    sec=sections[lane]
    for part in ['core','C']:
        rows=sec[part];total=sum(x['dl'] for x in rows);n=max(1,math.ceil(total/(step_mm*1e-3)))
        # Length-weighted lump groups keep short impedance changes in the model.
        cumulative=0.;groups=[[] for _ in range(n)]
        for row in rows:
            index=min(n-1,int((cumulative+row['dl']/2)/total*n));groups[index].append(row);cumulative+=row['dl']
        if part=='C':
            for pol,node in zip(['p','n'],previous):
                lines.extend([f'Lcap{pol} {node} cap{pol} {c["package_l"]:.12g}',f'Cac{pol} cap{pol} ac{pol} 100n'])
            previous=['acp','acn']
        ends=[];arc=0.
        for group in groups:
            if not group:continue
            length=sum(x['dl'] for x in group)
            avg=lambda key:sum(x[key]*x['dl'] for x in group)/length
            cell(length,avg('zo'),avg('eo'),avg('ze'),avg('ee'));arc+=length;ends.append((arc,previous.copy()))
        if part=='C':
            for pol,j in [('P',0),('N',1)]:
                branch=sec['branches'].get(pol)
                if branch:
                    node=min(ends,key=lambda e:abs(e[0]-branch['tap_s']))[1][j];td=max(branch['length']*math.sqrt(3)/C0,1e-13)
                    lines.extend([f'Lbias{pol} {node} br{pol} {85*td:.12g}',f'Cbi{pol} {node} 0 {td/85/2:.12g}',f'Cbo{pol} br{pol} 0 {td/85/2:.12g}',f'Rbias{pol} br{pol} 0 {bias}'])
            # ESD at the actual route crossing, rounded to nearest lump group.
            cross=next((x['s0'] for x in rows if x['x']>=108),total)
            ep,en=min(ends,key=lambda e:abs(e[0]-cross))[1]
            lines.extend([f'Cesdp {ep} 0 {c["esc"]:.12g}',f'Cesdn {en} 0 {c["esc"]:.12g}'])
    for _ in range(6):cell(.011/6,50,2.5,50,2.5)
    for pol,node in zip(['p','n'],previous):
        lines.extend([f'Rterm{pol} {node} vterm 50',f'Crx{pol} {node} 0 {c["rxcap"]:.12g}'])
    lines.extend([f'Brxp rx_p 0 V={{V({previous[0]})}}',f'Brxn rx_n 0 V={{V({previous[1]})}}','Bdiff rx_diff 0 V={V(rx_p)-V(rx_n)}','Bsrcdiff src_diff 0 V={V(srcp)-V(srcn)}',
                  '.options reltol=.002 abstol=1p vntol=1u method=gear itl4=150',
                  '.save v(rx_p) v(rx_n) v(rx_diff) v(src_diff)',
                  f'.tran {ui/100:.12g} {129*ui:.12g} 0 {ui/150:.12g}', '.end'])
    info={'kind':'hdmi','lane':lane,'rate_bps':rate,'corner':corner,'pattern':pattern,'bit_period_s':ui,'edge_s':edge,'bits':bits,'flight_delay_s':delay,'cells':counter[0],'step_mm':step_mm,'receiver_diff_margin_V':.1,'scope':'Coupled RLGC carrier/Core equivalent,assumed Thevenin driver and ideal50ohm-per-leg receiver. Nyquist-fitted constant losses. Excludes actual IBIS,cable,HDMI protocol and compliance.'}
    return '\n'.join(lines)+'\n',info
