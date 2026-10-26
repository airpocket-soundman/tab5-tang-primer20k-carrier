"""Recheck the other session's R3 remediation from a fixed Git snapshot.

System Python with numpy/scipy, plus KiCad 10 Python/CLI. No hardware access.
  python -X utf8 kicad/sim/audit_handover.py [revision]
Only the new handover evidence JSON is written to this checkout. All checker
outputs, injected faults and DRC results are generated in a temporary snapshot.
"""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[2]
KPY=Path('C:/Program Files/KiCad/10.0/bin/python.exe')
KCLI=KPY.with_name('kicad-cli.exe')

NUMERIC=r'''
from pathlib import Path
import sys,json,numpy as np
root=Path(sys.argv[1]);sim=root/'kicad/sim';sys.path.insert(0,str(sim))
import tmds_channel as tc,tmds_sparam as sp
tc.load();saved=json.loads((sim/'tmds_sparam.json').read_text())
out={'pairs':{},'matrix':[],'matrix_max_error_dB':0.0}
matrix=json.loads((sim/'report_matrix.json').read_text())
for tag,p,n in tc.PAIRS:
 M=sp.channel(tag,p,n);metrics=sp.metrics(M);S=sp.abcd_to_s4(M)
 out['pairs'][tag]={'metrics':metrics,'max_error_dB':max(abs(v-saved[tag][k]) for k,v in metrics.items()),
  'maximum_singular_value':float(np.linalg.svd(S,compute_uv=False).max()),
  'reciprocity_error':float(abs(S-S.transpose(0,2,1)).max())}
 for record in matrix:
  z,c=record['core_z'],record['esd_cd_pf']
  m=sp.metrics(sp.channel(tag,p,n,core_z=z,esd_cd=c*1e-12))
  expected=record['per_pair'][tag]
  lookup={'sdd11_max_1500':'s11_max_1500','sdd21_742':'s21_742','scd21_max_1500':'scd21_max_1500'}
  error=max(abs(v-m[lookup[k]]) for k,v in expected.items())
  out['matrix_max_error_dB']=max(error,out['matrix_max_error_dB'])
  out['matrix'].append({'pair':tag,'core_z':z,'esd_cd_pf':c,'metrics':m,'error_dB':error})
out['matrix_goal_failures']=[{k:r[k] for k in ['core_z','esd_cd_pf','worst_pair','sdd11_max_1500']} for r in matrix if r['sdd11_max_1500']>-10]
S=sp.abcd_to_s4(sp.uncoupled(sp.F,50,.01,3))
out['matched_line']={'reflection':float(abs(S[:,:2,:2]).max()),'cross_transmission':float(max(abs(S[:,2,1]).max(),abs(S[:,3,0]).max()))}
out['ok']=(max(x['max_error_dB'] for x in out['pairs'].values())<1e-8 and out['matrix_max_error_dB']<1e-8
 and max(x['maximum_singular_value'] for x in out['pairs'].values())<=1+1e-8
 and max(x['reciprocity_error'] for x in out['pairs'].values())<1e-8)
Path(sys.argv[2]).write_text(json.dumps(out,indent=2),encoding='utf-8')
sys.exit(0 if out['ok'] else 1)
'''


def main():
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
    sha=git('rev-parse',sys.argv[1] if len(sys.argv)>1 else '851adf4').decode().strip()
    result={'target_revision':sha,'date':'2026-10-24','checks':{},'manifest':{}}
    with tempfile.TemporaryDirectory(prefix='carrier-handover-') as temp:
        base=Path(temp)
        with tarfile.open(fileobj=io.BytesIO(git('archive',sha))) as archive:
            archive.extractall(base,filter='data')
        manifest=json.loads((base/'kicad/sim/manifest_r3.json').read_text())
        for rel,rec in manifest['files'].items():
            data=(base/rel).read_bytes()
            if rel.endswith(('.py','.json','.csv','.kicad_pcb','.kicad_sch','.kicad_mod','.md','.html')):
                data=data.replace(b'\r\n',b'\n')
            result['manifest'][rel]={'actual':hashlib.sha256(data).hexdigest(),'expected':rec['sha256']}
        assert all(v['actual']==v['expected'] for v in result['manifest'].values())
        print('Verified manifest:',len(result['manifest']),'files',flush=True)
        tasks=[('continuity','check_continuity.py','continuity_report.json'),
               ('negative_continuity','check_negative.py','negative_report.json'),
               ('esd','check_esd_footprint.py','esd_footprint_check.json'),
               ('classification','check_classification.py','classification_report.json'),
               ('regression_esd','test_esd_check.py','regression_esd.json'),
               ('regression_classification','test_classification_check.py','regression_classification.json')]
        for name,script,output in tasks:
            p=subprocess.run([str(KPY),'-X','utf8',str(base/'kicad/sim'/script)],cwd=base,capture_output=True,text=True,encoding='utf-8',timeout=180)
            report=json.loads((base/'kicad/sim'/output).read_text(encoding='utf-8'))
            result['checks'][name]={'exit_code':p.returncode,'report':report}
            assert p.returncode==0 and report['ok'],name+': '+p.stdout+p.stderr
            print(name,'PASS',flush=True)
        p=subprocess.run([str(KCLI),'pcb','drc','--severity-error','--all-track-errors','--format','json',
                          '--output',str(base/'drc.json'),str(base/'kicad/tab5-fpga-carrier.kicad_pcb')],capture_output=True,timeout=90)
        drc=json.loads((base/'drc.json').read_text(encoding='utf-8'))
        result['drc']={'exit_code':p.returncode,'violations':len(drc['violations']),'unconnected_items':len(drc['unconnected_items'])}
        assert p.returncode==0 and not drc['violations'] and not drc['unconnected_items']
        print('DRC PASS',flush=True)
        num=base/'numeric.json'
        p=subprocess.run([sys.executable,'-X','utf8','-c',NUMERIC,str(base),str(num)],capture_output=True,text=True,timeout=180)
        assert p.returncode==0,p.stderr
        result['numeric']=json.loads(num.read_text(encoding='utf-8'))
        print('Numeric reproduction, matrix, passivity and reciprocity PASS',flush=True)
    result['ok']=True
    dest=ROOT/'kicad/sim'/f'handover_{sha[:7]}_2026-10-24.json'
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Saved',dest,flush=True)


if __name__=='__main__':main()
