"""Exercise shared tile RAM, extension ABI, feature-off and abort, without hardware."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from run_fire_tile import pixel

ROOT = Path(__file__).resolve().parents[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, required=True)
    p.add_argument('--output', type=Path, default=ROOT/'fpga/build/all-scenes-tile-tests')
    p.add_argument('--vendor-primitive-lib', type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=str(a.tools.resolve()) + os.pathsep + os.environ['PATH'])
    golden = a.output/'fire.hex'
    golden.write_text(''.join(f'{pixel(288+x,160+y,320,180,65535,2):04x}\n' for y in range(32) for x in range(32)), encoding='ascii')
    wrapper = 'triangle_tile_vendor.v' if a.vendor_primitive_lib else 'triangle_tile.v'
    sources = [f'fpga/gfx/rtl/{f}' for f in [wrapper, 'raster2d.v', 'fire_tile.v',
               'triangle_fragment.v', 'triangle_coverage.v', 'triangle_depth.v']]
    sources += ['fpga/gfx/tests/tb_all_scenes_tile.v']
    extra = []
    if a.vendor_primitive_lib:
        sources += ['fpga/gfx/rtl/tile_dpram_vendor.v', str(a.vendor_primitive_lib.resolve())]
        extra += ['-DVENDOR_RAM']
    executable = (a.output/'test.vvp').resolve()
    for name, command in (
        ('compile', ['iverilog', '-g2012', '-Wall', '-s', 'tb_all_scenes_tile', *extra,
                     '-o', str(executable), *sources]),
        ('run', ['vvp', str(executable), '+fire='+str(golden.resolve())]),
    ):
        command[0] = shutil.which(command[0], path=env['PATH']) or command[0]
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        (a.output/(name+'.log')).write_text(result.stdout, encoding='utf-8')
        print(result.stdout, end='')
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
