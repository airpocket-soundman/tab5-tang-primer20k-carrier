"""mem_bw simulation runner (iverilog only; no programmer, no physical DDR). Result is RTL simulation evidence only."""
import argparse
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--iverilog', default='iverilog')
p.add_argument('--vvp', default='vvp')
args = p.parse_args()
root = Path(__file__).resolve().parents[2]
build = root / 'build/mem-bw-tests'
build.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
tool = Path(args.iverilog).resolve().parent
env['PATH'] = str(tool) + os.pathsep + str(tool.parent / 'lib') + os.pathsep + env['PATH']
sources = [root / 'mem/rtl/mem_bw.v', root / 'mem/tests/tb_mem_bw.v']
for paired, rowpad in ((1, 0), (0, 0), (1, 1)):
    image = build / f'mem_bw_p{paired}_r{rowpad}.vvp'
    subprocess.run([args.iverilog, '-g2012', '-Wall', '-s', 'tb_mem_bw', f'-Ptb_mem_bw.PAIRED={paired}',
                    f'-Ptb_mem_bw.ROWPAD={rowpad}', '-o', str(image), *map(str, sources)],
                   check=True, env=env)
    done = subprocess.run([args.vvp, str(image)], capture_output=True, text=True, env=env, timeout=900)
    if done.returncode != 0 or 'PASS mem_bw' not in done.stdout:
        raise RuntimeError(done.stdout + done.stderr)
    print(done.stdout.strip())
