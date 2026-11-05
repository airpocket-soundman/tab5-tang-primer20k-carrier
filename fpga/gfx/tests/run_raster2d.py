"""Compile and run the shared tile 2D unit against an independent integer oracle."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, help='Existing OSS CAD Suite bin directory')
    p.add_argument('--output', type=Path, default=ROOT/'fpga/build/raster2d-tests')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if a.tools:
        env['PATH'] = str(a.tools.resolve()) + os.pathsep + env['PATH']
    for name, command in (
        ('compile', ['iverilog', '-g2012', '-Wall', '-s', 'tb_raster2d', '-o',
                     str((a.output/'test.vvp').resolve()),
                     'fpga/gfx/rtl/raster2d.v', 'fpga/gfx/tests/tb_raster2d.v']),
        ('run', ['vvp', str((a.output/'test.vvp').resolve())]),
    ):
        command[0] = shutil.which(command[0], path=env['PATH']) or command[0]
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (a.output/(name+'.log')).write_text(result.stdout, encoding='utf-8')
        print(result.stdout, end='')
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
