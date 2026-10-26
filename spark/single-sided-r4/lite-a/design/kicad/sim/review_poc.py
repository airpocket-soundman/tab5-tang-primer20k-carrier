"""Independent, non-signoff checks for the 2026-10-24 PoC review.

Run from any directory with system Python (numpy/scipy):
  python kicad/sim/review_poc.py
Optional slow numerical check: add --energy-check.
No board, original solver, or existing result file is modified.
The channel comparison deliberately retains the existing section-order and
ideal inner-layer assumptions: its purpose is to expose omitted loading,
not to certify or repair the complete channel model.
"""
from pathlib import Path
import collections
import hashlib
import inspect
import json
import math
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tmds_channel as tc
import tmds_sparam as sp


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    tc.GEOM_DATA.update(json.loads(Path(tc.GEOM).read_text()))
    # Refuse to generate additional cache entries as a side effect of review.
    original_zdiff = tc.zdiff
    def cached_zdiff(w, gap):
        grid = (0.1, 0.13, 0.15, 0.2, 0.3, 0.45, 0.7, 1.0, 1.5)
        key = '%.3f/%.2f' % (round(w, 3), min(grid, key=lambda g: abs(g-min(gap, 1.5))))
        if key not in tc._cache:
            raise ValueError('Missing existing cache entry: ' + key)
        return original_zdiff(w, gap)
    tc.zdiff = cached_zdiff
    result = dict(
        board_sha256=digest(HERE.parent/'tab5-fpga-carrier.kicad_pcb'),
        geometry_sha256=digest(Path(tc.GEOM)),
        source_sha256={p.name:digest(p) for p in [HERE/'tmds_channel.py', HERE/'tmds_sparam.py', Path(__file__)]},
        limitations=['Existing section-order implementation retained; not independently certified',
                     'Inner-layer and via impedances remain idealized',
                     'Bias comparison uses a zero-length, symmetric branch',
                     'Actual long asymmetric bias branches are not simulated',
                     '100-ohm matched ports, no transmitter or cable/sink eye model',
                     'Core impedance sweep is an assumption, not a measured bound'],
    )
    stub_lengths = collections.defaultdict(float)
    for net, layer, pts in json.loads((HERE/'stub_tracks.json').read_text()):
        stub_lengths[net] += sum(math.dist(a,b) for a,b in zip(pts,pts[1:]))
    result['bias_branch_planar_mm'] = dict(stub_lengths)
    result['storage_order_discontinuities'] = {
        name: sum(math.dist(a[2:4],b[:2]) > .001 for a,b in zip(v['segs'],v['segs'][1:]))
        for name,v in tc.GEOM_DATA.items() if v['segs']
    }
    modes = {'VGA60':25.175e6, '480p60':27e6,
             '720p60':74.25e6, '1080p30':74.25e6, '1080p60':148.5e6}
    result['modes'] = {n:dict(pixel_MHz=f/1e6, lane_Mbps=f*10/1e6,
                              nyquist_MHz=f*5/1e6, UI_ps=1e12/(10*f),
                              intra_015UI_ps=.15e12/(10*f),
                              inter_020char_ps=.20e12/f,
                              serial_clock_5x_MHz=5*f/1e6) for n,f in modes.items()}
    sections = {tag:sp.sections(tag,p,n) for tag,p,n in tc.PAIRS}
    result['channel_loading_comparison'] = {}
    for scenario, core_z, bias in [('legacy',100,False), ('bias_998ohm',100,True),
                                  ('core_85_bias',85,True),('core_115_bias',115,True)]:
        pairs = {}
        for tag,p,n in tc.PAIRS:
            mats=[sp.abcd_line(sp.F,core_z,38.4e-3,3)]
            for key in ('core','C','K'):
                mats += [sp.abcd_line(sp.F,z,l,ee) for l,z,ee in sections[tag][key]]
                if key=='core':
                    # Actual two 100nF capacitors plus the legacy ESL assumption.
                    z=2/(2j*np.pi*sp.F*100e-9)+2j*np.pi*sp.F*1.4e-9
                    mats.append(sp.abcd_series(sp.F,z))
                    if bias:
                        mats.append(sp.abcd_shunt(sp.F,np.full(len(sp.F),1/998)))
                if key=='C':
                    # Keep old capacitance for isolated A/B comparison only.
                    mats.append(sp.abcd_shunt(sp.F,2j*np.pi*sp.F*.15e-12))
            mats.append(sp.abcd_line(sp.F,100,11e-3,2.5))
            s11,s21=sp.abcd_to_s(sp.cascade(mats))
            pairs[tag]={}
            for name,pclk in modes.items():
                band=sp.F<=10*pclk
                ny=int(np.argmin(abs(sp.F-5*pclk)))
                pairs[tag][name]=dict(
                    s11_worst_to_lane_rate_dB=float(20*np.log10(abs(s11[band])).max()),
                    s21_at_nearest_nyquist_dB=float(20*np.log10(abs(s21[ny]))),
                    sampled_nyquist_MHz=float(sp.F[ny]/1e6))
        result['channel_loading_comparison'][scenario]=pairs
    result['lumped_bias_only'] = dict(Rdiff_ohm=998,
        s21_dB=float(20*np.log10(2/(2+100/998))),
        s11_dB=float(20*np.log10((100/998)/(2+100/998))))
    if '--energy-check' in sys.argv:
        import microstrip2d as m
        original=m.solve_energy
        src=inspect.getsource(original)
        src=src[:src.index('    # energy =')]+(
            '    return 0.5 * EPS0 * (np.sum(ex * np.diff(phi,axis=0)**2) '
            '+ np.sum(ey * np.diff(phi,axis=1)**2))\n')
        ns=m.__dict__.copy();exec(src,ns)
        rows=[]
        try:
            for dx in [.02104,.01052]:
                for label,fn in [('existing_cell_average',original),
                                 ('discrete_link_energy',ns['solve_energy'])]:
                    m.solve_energy=fn
                    r=m.pair(.2,.13,dx=dx);single=m.single(.35,dx=dx)
                    rows.append(dict(dx_mm=dx,energy=label,zdiff=r['zdiff'],
                                     eeff=r['odd'][1],single_ohm=single[0]))
        finally:
            m.solve_energy=original
        result['energy_check']=rows
    out=HERE/'review_poc_2026-10-24.json'
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Saved',out)
    print('Bias branch lengths (mm):',dict(stub_lengths))
    for scenario,pairs in result['channel_loading_comparison'].items():
        print(scenario, {mode:dict(
            s11_worst_dB=round(max(v[mode]['s11_worst_to_lane_rate_dB'] for v in pairs.values()),2),
            s21_worst_at_nyquist_dB=round(min(v[mode]['s21_at_nearest_nyquist_dB'] for v in pairs.values()),2))
            for mode in ('480p60','720p60','1080p60')})


if __name__=='__main__':
    main()
