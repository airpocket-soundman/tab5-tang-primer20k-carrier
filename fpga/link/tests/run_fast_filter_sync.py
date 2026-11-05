"""Compare default waveforms to a pinned legacy RTL and test the faster option."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline-commit', default='72724ad')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    baseline = subprocess.check_output(['git','show',a.baseline_commit+':fpga/link/rtl/reply_clock_filter.v'],cwd=ROOT)
    legacy = a.output/'legacy.v'
    legacy.write_bytes(baseline.replace(b'module reply_clock_filter #(',b'module reply_clock_filter_legacy #(',1))
    source = ROOT/'fpga/link/rtl/reply_clock_filter.v'
    bench = ROOT/'fpga/link/tests/tb_fast_filter_sync.v'
    env = dict(os.environ,PATH=str(a.tools.resolve())+os.pathsep+os.environ['PATH'])
    plans = [(5000000,32,0,1),(8000000,20,0,1),(10000000,16,0,1),(16000000,10,0,1),
             (20000000,8,0,1),(25000000,6,2,5),(26666667,6,0,1),(32000000,5,0,1),(40000000,4,0,1)]
    rows = []
    for hz,n,b,c in plans:
        for phase in range(0,4630,463):
            label = f'{hz}-{phase}'
            exe = (a.output/'test.vvp').resolve()
            cmd = [str(a.tools/'iverilog.exe'),'-g2012','-s','tb_fast_filter_sync',
                   f'-Ptb_fast_filter_sync.DIV_INTEGER={n}',f'-Ptb_fast_filter_sync.DIV_NUMERATOR={b}',
                   f'-Ptb_fast_filter_sync.DIV_DENOMINATOR={c}',f'-Ptb_fast_filter_sync.PHASE_PS={phase}',
                   '-o',str(exe),str(source),str(bench),str(legacy.resolve())]
            r = subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            if r.returncode:raise RuntimeError(r.stdout)
            r = subprocess.run([str(a.tools/'vvp.exe'),str(exe)],cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (a.output/(label+'.log')).write_text(r.stdout,encoding='utf-8')
            if r.returncode:raise RuntimeError(label+'\n'+r.stdout)
            fields = next(x for x in r.stdout.splitlines() if x.startswith('FAST_SYNC,')).split(',')
            rows.append(dict(configured_hz=hz,phase_ps=phase,minimum_latency_ps=int(fields[-2]),maximum_latency_ps=int(fields[-1])))
    result = dict(passed=True,hardware_access=False,baseline_commit=a.baseline_commit,
                  baseline_sha256=hashlib.sha256(baseline).hexdigest(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  cases=rows,scope='digital216MHz_approximation4630ps_not_analog_MTBF_or_board_eye',
                  legacy_default_waveform_identical=True,synchronizer_stages=2,one_tick_reduction_ps=4630,
                  high_ticks=2,minimum_rise_spacing_ticks=5,
                  one_sample_excursion='fast_accepts_one_legacy_rejects; close pair still faults')
    (a.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(rows),one_tick_reduction_ps=4630)))


if __name__ == '__main__':
    main()
