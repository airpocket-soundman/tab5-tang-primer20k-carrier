"""Run available feature checks and report every planned function without hardware access."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
RTL_NAMES = ('bringup', 'dock_gfx', 'coverage', 'depth', 'fragment', 'mac', 'requant', 'dot')
COMPONENTS = ('mac', 'requant', 'dot', 'coverage', 'depth', 'fragment')
HOST_DIRS = {'host.gfx':'gfx/tests', 'host.npu':'npu/tests', 'host.codec':'host/tests'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_results(matrix, checks):
    result = []
    for feature in matrix['features']:
        statuses = {name:checks.get(name, {'status':'not_run'})['status'] for name in feature['checks']}
        if 'failed' in statuses.values():
            status = 'failed'
        elif feature['readiness'] == 'planned':
            status = 'not_ready'
        elif statuses and all(value == 'passed' for value in statuses.values()):
            status = 'passed'
        else:
            status = 'partial'
        result.append({'id':feature['id'], 'name':feature['name'], 'readiness':feature['readiness'],
                       'verification':status, 'checks':statuses, 'missing':feature['missing']})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rtl', action='store_true')
    parser.add_argument('--synth', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--cc', type=Path, help='C compiler; zig.exe automatically uses the cc subcommand')
    parser.add_argument('--require-complete', action='store_true', help='Exit 2 unless every feature check has passed')
    parser.add_argument('--list', action='store_true', help='List readiness without running tests')
    args = parser.parse_args()
    matrix_path = ROOT/'validation/feature_matrix.json'
    matrix = json.loads(matrix_path.read_text(encoding='utf-8'))
    if args.list:
        for item in matrix['features']:
            print(f"{item['id']}: {item['readiness']} - {item['name']}")
        return 0
    run_dir = ROOT/'build/feature-tests/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:10])
    run_dir.mkdir(parents=True)
    checks = {name:{'status':'not_run', 'reason':'Hardware checks require a separate physical test' if name.startswith('hardware.') else 'Not selected'}
              for item in matrix['features'] for name in item['checks']}
    report = {'status':'running', 'hardware_access':'none', 'run_dir':str(run_dir),
              'matrix_sha256':sha(matrix_path), 'checks':checks, 'sources':{}}
    # Record the actual source tree, including tests and models; do not use old reports as evidence.
    for folder in ('gfx', 'npu', 'link', 'host', 'reference', 'tools', 'simulation', 'builds', 'platform', 'constraints'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and path.suffix in ('.v', '.py', '.c', '.h', '.json', '.cst', '.sdc', '.tcl'):
                report['sources'][str(path)] = sha(path)
    child_env = os.environ.copy()
    cc = args.cc
    if cc is None:
        found = shutil.which('cc') or shutil.which('gcc')
        if found:
            cc = Path(found)
        else:
            spec = importlib.util.find_spec('ziglang')
            if spec and spec.origin:
                candidate = Path(spec.origin).parent/'zig.exe'
                if candidate.is_file():
                    cc = candidate
    if cc:
        cc = cc.resolve()
        child_env['CARRIER_CC_JSON'] = json.dumps([str(cc)]+(['cc'] if cc.stem.lower() == 'zig' else []))
        report['c_compiler'] = {'path':str(cc), 'sha256':sha(cc)}

    def save():
        report['features'] = feature_results(matrix, checks)
        report['summary'] = dict(Counter(item['verification'] for item in report['features']))
        text = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
        (run_dir/'report.json').write_text(text, encoding='utf-8')
        (ROOT/'build/feature-tests/latest.json').write_text(text, encoding='utf-8')

    def execute(name, command, timeout=240):
        entry = {'status':'running', 'command':[str(x) for x in command], 'log':str(run_dir/(name+'.log'))}
        checks[name] = entry
        save()
        try:
            proc = subprocess.run(entry['command'], cwd=ROOT, env=child_env, capture_output=True,
                                  text=True, encoding='utf-8', errors='replace', timeout=timeout)
            output = proc.stdout+proc.stderr
            Path(entry['log']).write_text(output, encoding='utf-8')
            entry.update(returncode=proc.returncode, log_sha256=sha(Path(entry['log'])),
                         status='passed' if proc.returncode == 0 else 'failed')
            if proc.returncode == 0 and (re.search(r'OK \(skipped=\d+\)', output) or 'Ran 0 tests' in output):
                entry.update(status='blocked', reason='Tests skipped: see log; not a full pass')
        except (OSError, subprocess.SubprocessError) as exc:
            entry.update(status='blocked', reason=str(exc))
        print(f"{name}: {entry['status']}", flush=True)
        save()
        return entry['status'] == 'passed'

    for name, directory in HOST_DIRS.items():
        execute(name, [sys.executable, '-m', 'unittest', 'discover', '-s', directory, '-p', 'test_*.py', '-v'])
    if args.rtl:
        local = ROOT/'build/windows-tools/oss-cad-suite/bin'
        compiler = local/'iverilog.exe'
        runtime = local/'vvp.exe'
        command = [sys.executable, ROOT/'tools/run_existing_rtl.py', '--require', '--output', run_dir/'rtl.json']
        if compiler.is_file() and runtime.is_file():
            command += ['--iverilog', compiler, '--vvp', runtime]
            report['rtl_tools'] = {str(p):sha(p) for p in (compiler, runtime)}
        execute('rtl.group', command)
        if (run_dir/'rtl.json').is_file():
            rtl = json.loads((run_dir/'rtl.json').read_text(encoding='utf-8'))
            entries = {item['name']:item for item in rtl['suites']}
            for name in RTL_NAMES:
                checks['rtl.'+name] = entries.get(name, {'status':'blocked', 'reason':rtl.get('reason', rtl.get('error', 'Suite did not finish'))})
        else:
            for name in RTL_NAMES:
                checks['rtl.'+name] = {'status':'blocked', 'reason':'RTL group produced no report'}
    if args.synth:
        for name in COMPONENTS:
            execute('synth.'+name, [sys.executable, ROOT/'builds/components/build.py', name])
            manifest = ROOT/f'build/component-{name}/manifest.json'
            if checks['synth.'+name]['status'] == 'passed' and manifest.is_file():
                checks['synth.'+name]['manifest'] = json.loads(manifest.read_text(encoding='utf-8'))
    if args.build:
        for name in ('link', 'gfx'):
            execute('build.'+name, [sys.executable, ROOT/'tools/dock_dev.py', 'build', name])
            manifest = ROOT/f'build/dock-oss-{name}/manifest.json'
            if checks['build.'+name]['status'] == 'passed' and manifest.is_file():
                checks['build.'+name]['manifest'] = json.loads(manifest.read_text(encoding='utf-8'))
    # Detect edits during the run instead of associating results with a mixed source revision.
    changed = [name for name, digest in report['sources'].items() if not Path(name).is_file() or sha(Path(name)) != digest]
    if changed:
        checks['sources.stability'] = {'status':'failed', 'changed':changed}
    statuses = [item['status'] for item in checks.values()]
    report['status'] = 'failed' if 'failed' in statuses else ('incomplete' if 'blocked' in statuses else 'completed')
    save()
    print(f"Feature readiness: {report['summary']}; report: {run_dir/'report.json'}")
    if report['status'] == 'failed':
        return 1
    if report['status'] == 'incomplete' or (args.require_complete and any(item['verification'] != 'passed' for item in report['features'])):
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
