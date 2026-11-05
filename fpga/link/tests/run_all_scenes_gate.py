"""Functional mapped-Gowin reproduction. Ideal PLL outputs; no SDF or timing proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, required=True)
    p.add_argument('--netlist', type=Path, required=True)
    p.add_argument('--primitive-lib', type=Path, required=True)
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bus8', action='store_true')
    p.add_argument('--top-module', default='tab5_dock_all_scenes_top')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ,PATH=str(a.tools.resolve())+os.pathsep+os.environ['PATH'])
    original_bench = ROOT/'fpga/link/tests/tb_all_scenes_gate.v'
    bench = a.output/'bench.v'
    bench.write_text(original_bench.read_text().replace('tab5_dock_all_scenes_top dut(',a.top_module+' dut(',1),encoding='utf-8')
    sim = (a.output/'gate.vvp').resolve()
    manifest = dict(scope='functional_post_PnR_ideal_PLL_no_SDF_no_STA',
                    bus='8MHz_31.25ns_setup_62.5ns_high_31.25ns_hold' if a.bus8 else '1.667MHz',
                    sha256={str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest()
                            for x in [a.netlist,a.primitive_lib,a.vectors,bench,original_bench]})
    for name, cmd in [
        ('compile',['iverilog','-g2012','-s','tb_all_scenes_gate',*(['-DBUS8'] if a.bus8 else []),
                    '-o',str(sim),str(a.netlist.resolve()),str(bench),str(a.primitive_lib.resolve())]),
        ('run',['vvp',str(sim),'+vectors='+str(a.vectors.resolve())]),
    ]:
        cmd[0] = shutil.which(cmd[0],path=env['PATH']) or cmd[0]
        with (a.output/(name+'.log')).open('w',encoding='utf-8') as log:
            try:
                r = subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
                manifest[name+'_returncode'] = r.returncode
            except subprocess.TimeoutExpired:
                manifest[name+'_timeout'] = True
                manifest[name+'_returncode'] = -1
        print(name,manifest[name+'_returncode'],flush=True)
        if manifest[name+'_returncode']:
            break
    manifest['passed'] = manifest.get('run_returncode') == 0
    (a.output/'result.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return 0 if manifest['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
