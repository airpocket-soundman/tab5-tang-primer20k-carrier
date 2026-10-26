"""Audit a committed simulation snapshot without changing its generated files.

python -X utf8 kicad/sim/audit_committed_simulation.py [revision]
Writes audit_<short-sha>_2026-10-24.json next to this script.
Uses only tracked files extracted to a temporary directory; local uncommitted
results and corrections cannot silently enter the target under review.
"""
from pathlib import Path
import hashlib
import importlib
import json
import math
import subprocess
import sys
import tempfile

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent


def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])


def db(v):
    return 20*np.log10(abs(v))


def main():
    sha=git('rev-parse',sys.argv[1] if len(sys.argv)>1 else '6450c42').decode().strip()
    names=git('ls-tree','-r','--name-only',sha,'--','kicad/sim').decode().splitlines()
    output={'revision':sha,'date':'2026-10-24','inputs':{},'results':{}}
    for path in ['kicad/tab5-fpga-carrier.kicad_pcb','kicad/gen/design.py','kicad/sim/stub_tracks.json']:
        blob=git('show',sha+':'+path)
        output['inputs'][path]=hashlib.sha256(blob).hexdigest()
    with tempfile.TemporaryDirectory(prefix='carrier-sim-audit-') as tmp:
        base=Path(tmp)
        for path in names:
            if Path(path).suffix not in ['.py','.json']:continue
            blob=git('show',sha+':'+path)
            dest=base/Path(path).name;dest.write_bytes(blob)
            output['inputs'][path]=hashlib.sha256(blob).hexdigest()
        sys.dont_write_bytecode=True
        sys.path.insert(0,str(base))
        tc=importlib.import_module('tmds_channel')
        sp=importlib.import_module('tmds_sparam')
        rf=importlib.import_module('make_report_figs')
        tc.GEOM_DATA.update(json.loads((base/'tmds_geom.json').read_text()))
        expected=json.loads((base/'tmds_sparam.json').read_text())
        expected_report=json.loads((base/'report_sparam.json').read_text())
        rows={};baseline={};max_error=0.;max_report_error=0.
        for tag,p,n in tc.PAIRS:
            M,lens=sp.build(tag,p,n);s11,s21=sp.abcd_to_s(M)
            baseline[tag]=rf.channel(tag,p,n)
            r11,r21=sp.abcd_to_s(baseline[tag])
            i1=int(np.argmin(abs(sp.F-.825e9)));i2=int(np.argmin(abs(sp.F-1.65e9)))
            actual=dict(sdd11_825M=float(db(s11[i1])),sdd11_1650M=float(db(s11[i2])),
                sdd11_max_dB=float(db(s11).max()),sdd21_825M=float(db(s21[i1])),sdd21_1650M=float(db(s21[i2])))
            max_error=max(max_error,max(abs(v-expected[tag][k]) for k,v in actual.items()))
            rr=dict(s11_825=float(db(r11[i1])),s11_1650=float(db(r11[i2])),
                s21_825=float(db(r21[i1])),s21_1650=float(db(r21[i2])),s11_max=float(db(r11).max()))
            max_report_error=max(max_report_error,max(abs(v-expected_report[tag][k]) for k,v in rr.items()))
            order={}
            for suffix in ['','_C','_K']:
                for net in [p+suffix,n+suffix]:
                    segs=sp.order_segments(tc.segs(None,net))
                    order[net]=dict(segments=len(segs),
                        discontinuous_transitions=sum(math.dist(a[2:4],b[:2])>.060001 for a,b in zip(segs,segs[1:])),
                        planar_mm=sum(math.dist(s[:2],s[2:4]) for s in segs))
            rows[tag]=dict(**actual,section_length_mm=lens,ordering=order,
                s11_worst_to_1650MHz_dB=float(db(s11[sp.F<=1.65e9]).max()),
                s11_worst_to_742_5MHz_dB=float(db(s11[sp.F<=742.5e6]).max()),
                s21_at_sampled_720p_nyquist_dB=float(db(s21[np.argmin(abs(sp.F-371.25e6))])))
        sensitivity=json.loads((base/'report_sensitivity.json').read_text())
        pre=sp.abcd_line(sp.F,100,38.4e-3,3)
        tails={tag:np.linalg.inv(pre)@M for tag,M in baseline.items()}
        grid=np.zeros((len(sensitivity['C']),len(sensitivity['L'])))
        grid21=np.zeros_like(grid)
        for a,c in enumerate(sensitivity['C']):
            for b,l in enumerate(sensitivity['L']):
                socket=sp.abcd_series(sp.F,2j*np.pi*sp.F*l)@sp.abcd_shunt(sp.F,2j*np.pi*sp.F*c)
                vals=[sp.abcd_to_s(pre@socket@tail) for tail in tails.values()]
                grid[a,b]=max(float(db(s11[sp.F<=1.65e9]).max()) for s11,s21 in vals)
                grid21[a,b]=min(float(db(s21[i2])) for s11,s21 in vals)
        output['results']=dict(pairs=rows,
            sampled_label_825MHz_actual_MHz=float(sp.F[i1]/1e6),
            sampled_720p_nyquist_actual_MHz=float(sp.F[np.argmin(abs(sp.F-371.25e6))]/1e6),
            tmds_sparam_max_abs_error_dB=max_error,
            report_sparam_max_abs_error_dB=max_report_error,
            sensitivity_max_abs_error_dB=float(np.max(abs(grid-np.asarray(sensitivity['sdd11'])))),
            sensitivity_insertion_max_abs_error_dB=float(np.max(abs(grid21-np.asarray(sensitivity['sdd21'])))),
            sensitivity_grid_cells=int(grid.size),sensitivity_cells_below_minus10dB=int(np.sum(grid<=-10)),
            sensitivity_mid_s11_dB=float(grid[6,6]),sensitivity_max_s11_dB=float(grid.max()))
        assert max_error<1e-8 and max_report_error<1e-8
        assert output['results']['sensitivity_max_abs_error_dB']<1e-8
        assert output['results']['sensitivity_insertion_max_abs_error_dB']<1e-8
    dest=HERE/f'audit_{sha[:7]}_2026-10-24.json'
    dest.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output['results'],indent=2))
    print('Saved',dest)


if __name__=='__main__':
    main()
