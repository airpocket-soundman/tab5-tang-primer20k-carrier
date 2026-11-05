"""Exact sum-of-tile cycle accounting and native frame-timing codec; no hardware."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools',type=Path,required=True)
    p.add_argument('--zig',type=Path,required=True)
    p.add_argument('--vendor-primitive-lib',type=Path)
    a=p.parse_args()
    b=a.tools.resolve();env=dict(os.environ,PATH=str(b)+os.pathsep+str(b.parent/'lib')+os.pathsep+os.environ['PATH'])
    with tempfile.TemporaryDirectory(prefix='frame-timing-')as td:
        td=Path(td);native=td/'header.exe';sim=td/'timer.vvp'
        subprocess.run([str(a.zig), 'cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'host'),
                       str(ROOT/'gfx/tests/frame_timing_header.c'),'-o',str(native)],check=True,env=env,timeout=180)
        r=subprocess.run([str(native)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=30)
        print(r.stdout,end='');assert r.returncode==0
        wrapper='triangle_tile_vendor.v'if a.vendor_primitive_lib else'triangle_tile.v'
        sources=[ROOT/'gfx/rtl'/n for n in [wrapper,'triangle_fragment.v','triangle_coverage.v','triangle_depth.v']]
        sources+=[ROOT/'gfx/tests/tb_frame_timing.v']
        flags=[]
        if a.vendor_primitive_lib:
            flags=['-DVENDOR_RAM'];sources += [ROOT/'gfx/rtl/tile_dpram_vendor.v',a.vendor_primitive_lib.resolve()]
        subprocess.run([str(b/'iverilog.exe'),'-g2012','-s','tb_frame_timing',*flags,'-o',str(sim),*map(str,sources)],check=True,env=env,timeout=30)
        r=subprocess.run([str(b/'vvp.exe'),str(sim)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=120)
        print(r.stdout,end='')
        if r.returncode:raise SystemExit(r.returncode)


if __name__=='__main__':main()
