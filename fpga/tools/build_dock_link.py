"""Build and simulate Dock link v0 with OSS CAD Suite; never programs hardware."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    suite, out = args.suite.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(suite/'bin') + os.pathsep + str(suite/'lib') + os.pathsep + env['PATH']
    sources = ['fpga/platform/dock_link_top.v', 'fpga/link/rtl/link_bringup.v']
    cst = 'fpga/constraints/dock/tab5_dock_link_v0.cst'
    def run(name, cmd):
        cmd[0] = shutil.which(cmd[0], path=env['PATH']) or cmd[0]
        result = subprocess.run(cmd, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        (out/(name+'.log')).write_text(result.stdout, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'{name} failed ({result.returncode}): {result.stdout[-3000:]}')
        print(name + ': passed', flush=True)
    run('link-tests', [sys.executable, 'fpga/link/tests/run_rtl.py'])
    run('dock-test-compile', ['iverilog', '-g2012', '-s', 'tb_dock_link_top', '-o',
                            str(out/'dock.vvp'), *sources, 'fpga/link/tests/tb_dock_link_top.v'])
    run('dock-test', ['vvp', str(out/'dock.vvp')])
    # Yosys uses forward slashes inside its own command language.
    synth = (out/'synth.json').as_posix()
    run('synth', ['yosys', '-Q', '-T', '-p',
                 f'read_verilog {" ".join(sources)}; synth_gowin -top dock_link_top -family gw2a -json "{synth}"'])
    run('pnr', ['nextpnr-himbaechel', '--json', str(out/'synth.json'), '--write', str(out/'pnr.json'),
                '--device', 'GW2A-LV18PG256C8/I7', '--vopt', 'family=GW2A-18',
                '--vopt', 'cst='+cst, '--freq', '27'])
    run('pack', ['gowin_pack', '-d', 'GW2A-18', '--sspi_as_gpio',
                 '-o', str(out/'dock_link_v0.fs'), str(out/'pnr.json')])
    files = [*sources, cst, 'fpga/link/tests/tb_dock_link_top.v', 'fpga/tools/build_dock_link.py']
    manifest = {
        'device': 'GW2A-LV18PG256C8/I7', 'board': 'official Tang Primer 20K Dock',
        'sys_clk_hz': 27000000, 'bus_clk_max_hz': 5000,
        'suite_version': (suite/'VERSION').read_text().strip(),
        'sha256': {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
        'bitstream_sha256': hashlib.sha256((out/'dock_link_v0.fs').read_bytes()).hexdigest(),
        'hardware_programmed': False, 'physical_link_tested': False,
    }
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(out/'dock_link_v0.fs')

if __name__ == '__main__':
    main()
