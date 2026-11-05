"""Byte-exact registered DATA pipeline versus frozen legacy and integer oracle."""
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
    old = subprocess.check_output(['git','show',a.baseline_commit+':fpga/link/rtl/link_reply_raw.v'],cwd=ROOT)
    legacy = a.output/'legacy.v'
    legacy.write_bytes(old.replace(b'module link_reply_raw(',b'module link_reply_raw_legacy(',1))
    source = ROOT/'fpga/link/rtl/link_reply_raw.v'
    bench = ROOT/'fpga/link/tests/tb_registered_reply.v'
    exe = (a.output/'test.vvp').resolve()
    env = dict(os.environ,PATH=str(a.tools.resolve())+os.pathsep+os.environ['PATH'])
    for name,cmd in [('compile',[str(a.tools/'iverilog.exe'),'-g2012','-s','tb_registered_reply','-o',str(exe),str(source),str(bench),str(legacy.resolve())]),
                     ('run',[str(a.tools/'vvp.exe'),str(exe)])]:
        r = subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (a.output/(name+'.log')).write_text(r.stdout,encoding='utf-8')
        print(r.stdout,end='')
        if r.returncode:
            raise SystemExit(r.returncode)
    report = dict(passed=True,hardware_access=False,scope='digital byte/CRC/retirement equivalence, no analog pad/MTBF claim',
                  baseline_commit=a.baseline_commit,baseline_sha256=hashlib.sha256(old).hexdigest(),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),bench_sha256=hashlib.sha256(bench.read_bytes()).hexdigest())
    (a.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
