"""Record the fabrication revision against fixed 047538f, independent of legacy report text.
System Python. Run after model/report JSON regeneration and physical checks.
"""
import json
from pathlib import Path
import subprocess
import numpy as np
import tmds_channel as tc
import tmds_sparam as sp

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'kicad/sim'
BASE = '047538febbbf98b8758caa1441b386347c2afe14'


def old(rel):
    return json.loads(subprocess.check_output(['git','show',BASE+':'+rel],cwd=ROOT))


def main():
    before = old('kicad/sim/tmds_roles.json')
    after = json.loads((HERE/'tmds_roles.json').read_text())
    preserved = all(before[n].get(role,[]) == after[n].get(role,[])
                    for n in before for role in ('main','stub','strap'))
    others = all(before[n]['branch'] == after[n]['branch'] for n in before
                 if n not in ('HDMI_D1P_C','HDMI_D1N_C'))
    assert preserved, 'Unexpected change to the main TMDS paths'
    changed_branches=[n for n in before if before[n]['branch']!=after[n]['branch']]
    tc.load()
    baseline = old('kicad/sim/tmds_sparam.json')
    matrix = json.loads((HERE/'report_matrix.json').read_text())
    result = dict(baseline_commit=BASE, model_changed=False, main_paths_preserved=preserved,
                  other_branches_preserved=others, changed_branches=changed_branches, pairs={}, matrix_max_error_dB=0)
    for tag,p,n in tc.PAIRS:
        M = sp.channel(tag,p,n)
        S = sp.abcd_to_s4(M)
        current = sp.metrics(M)
        sv = float(np.linalg.svd(S,compute_uv=False).max())
        reciprocity = float(abs(S-S.transpose(0,2,1)).max())
        assert sv <= 1+1e-8 and reciprocity < 1e-8
        result['pairs'][tag] = dict(before=baseline[tag], after=current,
                                  maximum_singular_value=sv,reciprocity_error=reciprocity)
        for row in matrix:
            m = sp.metrics(sp.channel(tag,p,n,core_z=row['core_z'],esd_cd=row['esd_cd_pf']*1e-12))
            keys = dict(sdd11_max_1500='s11_max_1500',sdd21_742='s21_742',scd21_max_1500='scd21_max_1500')
            err = max(abs(row['per_pair'][tag][k]-m[v]) for k,v in keys.items())
            result['matrix_max_error_dB'] = max(result['matrix_max_error_dB'],err)
    assert result['matrix_max_error_dB'] < 1e-9
    result['failed_matrix_conditions'] = [dict(core_z=r['core_z'],esd_cd_pf=r['esd_cd_pf'],
        worst_pair=r['worst_pair'],sdd11_max_1500=r['sdd11_max_1500']) for r in matrix if r['sdd11_max_1500']>-10]
    result['comparison_note'] = 'Passive reciprocal model checks do not validate EM accuracy or powered hardware.'
    result['ok'] = True
    (HERE/'poc_fabrication_review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Preserved main paths; changed branches recorded; matrix reproduction and model invariants PASS')


if __name__ == '__main__':
    main()
