"""Regression helpers; all injected defects are saved into a temporary directory."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import pcbnew
HERE=Path(__file__).resolve().parent
PCB=HERE.parent/'tab5-fpga-carrier.kicad_pcb'
CASES=[]

def run_case(test, checker, label, expected, board_mutation=None, roles_mutation=None, error_key=None):
    with tempfile.TemporaryDirectory(prefix='carrier-check-') as temp:
        base=Path(temp)
        board=pcbnew.LoadBoard(str(PCB))
        if board_mutation:board_mutation(board)
        path=base/'input.kicad_pcb';pcbnew.SaveBoard(str(path),board)
        output=base/'result.json'
        env={k:v for k,v in os.environ.items() if k not in ('CHECK_PCB','CHECK_ROLES','CHECK_JSON')}
        env.update(CHECK_PCB=str(path),CHECK_JSON=str(output))
        if roles_mutation:
            roles=json.loads((HERE/'tmds_roles.json').read_text())
            roles_mutation(roles)
            role_path=base/'roles.json';role_path.write_text(json.dumps(roles))
            env['CHECK_ROLES']=str(role_path)
        result=subprocess.run([sys.executable,'-X','utf8',str(HERE/checker)],env=env,capture_output=True,text=True,timeout=60)
        test.assertTrue(output.exists(),result.stdout+result.stderr)
        report=json.loads(output.read_text())
        test.assertEqual(result.returncode,0 if expected else 1,result.stdout+result.stderr)
        test.assertEqual(report['ok'],expected)
        if error_key:test.assertTrue(report[error_key],report)
        CASES.append(dict(case=label,expected_ok=expected,actual_ok=report['ok'],exit_code=result.returncode))

def footprint(board,ref='U4'):
    return next(f for f in board.GetFootprints() if f.GetReference()==ref)

def pad(board,num='3'):
    return next(p for p in footprint(board).Pads() if p.GetNumber()==num)

def run_suite(module, output):
    import unittest
    if '--case' in sys.argv:
        name=sys.argv[sys.argv.index('--case')+1]
        suite=unittest.defaultTestLoader.loadTestsFromName(name,module)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        Path(os.environ['REGRESSION_CASE_JSON']).write_text(json.dumps(CASES))
        sys.exit(0 if result.wasSuccessful() else 1)
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    tests=[test for group in suite for test in group]
    passed=True
    # Isolate board mutation/destruction: KiCad SWIG ownership is process-local.
    with tempfile.TemporaryDirectory(prefix='carrier-regression-') as temp:
        for index,test in enumerate(tests):
            name=test.id().split('.',1)[1]
            record=Path(temp)/('case%d.json'%index)
            env=dict(os.environ,REGRESSION_CASE_JSON=str(record))
            run=subprocess.run([sys.executable,'-X','utf8',str(Path(module.__file__).resolve()),'--case',name],
                               env=env,capture_output=True,text=True,timeout=90)
            passed &= run.returncode==0
            if record.exists():CASES.extend(json.loads(record.read_text()))
            print(name, 'OK' if run.returncode==0 else 'FAILED',flush=True)
            if run.returncode:print(run.stdout+run.stderr,flush=True)
    (HERE/output).write_text(json.dumps(dict(ok=passed,tests=len(tests),cases=CASES),indent=1)+'\n')
    sys.exit(0 if passed else 1)
