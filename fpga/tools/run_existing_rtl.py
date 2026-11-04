"""Run RTL benches only with existing Icarus/vvp. Never installs or uses devices."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/rtl-check/status.json')
    parser.add_argument('--require', action='store_true', help='Fail if existing tools are unavailable')
    parser.add_argument('--iverilog', help='Path to an existing Icarus compiler')
    parser.add_argument('--vvp', help='Path to an existing vvp runtime')
    args = parser.parse_args()
    report = dict(status='not_run', device_access='none', installation='none', suites=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    compiler, runtime = shutil.which(args.iverilog or 'iverilog'), shutil.which(args.vvp or 'vvp')
    if not compiler or not runtime:
        report['reason'] = 'Existing iverilog/vvp unavailable; no installation attempted'
        save()
        print('RTL NOT RUN: ' + report['reason'])
        return 2 if args.require else 0
    compiler, runtime = str(Path(compiler).resolve()), str(Path(runtime).resolve())
    report.update(compiler=compiler, runtime=runtime, status='running')
    child_env = os.environ.copy()
    child_env['PATH'] = os.pathsep.join([str(Path(compiler).resolve().parent),
                                         str(Path(runtime).resolve().parent),
                                         child_env.get('PATH','')])
    def run(command):
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180, env=child_env)
        if result.returncode:
            raise RuntimeError(' '.join(map(str, command))+'\n'+result.stdout+result.stderr)
        return result.stdout.strip()
    try:
        for name, script in (
            ('bringup', 'link/tests/run_rtl.py'),
            ('dock_gfx', 'gfx/tests/run_bench.py'),
            ('triangle_tile', 'gfx/tests/run_triangle_tile.py'),
            ('triangle_rows', 'gfx/tests/run_triangle_rows.py'),
            ('coverage', 'gfx/tests/run.py'),
            ('depth', 'gfx/tests/run_depth.py'),
            ('fragment', 'gfx/tests/run_fragment.py'),
            ('edge_monitor', 'link/tests/run_edge_monitor.py')):
            output = run([sys.executable, str(ROOT/script), '--iverilog', compiler, '--vvp', runtime])
            report['suites'].append(dict(name=name, status='passed', output=output))
            print(name + ': passed')
            save()
        folder = ROOT/'build/rtl-check/compute'
        sources = [str(p) for p in sorted((ROOT/'npu/rtl').glob('*.v'))]
        for name, generator, top in (
            ('mac', 'generate_vectors.py', 'tb_int8_mac_lane'),
            ('requant', 'generate_requant_vectors.py', 'tb_int8_requantize'),
            ('dot', 'generate_dot_vectors.py', 'tb_int8_dot_job')):
            run([sys.executable, str(ROOT/'npu/tests'/generator), '--output', str(folder)])
            binary = folder/(name+'.vvp')
            run([compiler, '-g2012', '-Wall', '-s', top, '-o', str(binary), *sources, str(folder/(top+'.v'))])
            output = run([runtime, str(binary)])
            report['suites'].append(dict(name=name, status='passed', output=output))
            print(name + ': passed')
            save()
        report['status'] = 'passed'
        save()
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report.update(status='failed', error=str(exc))
        save()
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
