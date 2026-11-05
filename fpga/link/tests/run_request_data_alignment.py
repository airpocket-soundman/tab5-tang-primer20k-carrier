"""Synthetic8MHz DATA/CLK-skew stress; not physical/electrical qualification."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',required=True)
    p.add_argument('--vvp',required=True)
    a=p.parse_args()
    b=Path(a.iverilog).resolve().parent
    env=dict(os.environ,PATH=str(b)+os.pathsep+str(b.parent/'lib')+os.pathsep+os.environ['PATH'])
    sources=['link/rtl/triangle_batch.v','link/rtl/link_bringup.v','link/rtl/link_bringup_filtered.v',
             'link/rtl/reply_clock_filter.v','gfx/rtl/triangle_tile.v','gfx/rtl/raster2d.v','gfx/rtl/fire_tile.v',
             'gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v',
             'link/tests/tb_request_data_alignment.v']
    with tempfile.TemporaryDirectory(prefix='request-alignment-')as td:
        exe=Path(td)/'align.vvp'
        for filtered in (False,True):
            for skew in (0,10000,20000):
                cmd=[a.iverilog,'-g2012','-s','tb_request_data_alignment',
                     '-Ptb_request_data_alignment.CLK_SKEW_PS='+str(skew)]
                if filtered:cmd.append('-DFILTERED_CORE')
                subprocess.run([*cmd,'-o',str(exe),*[str(ROOT/s)for s in sources]],env=env,check=True,capture_output=True,timeout=30)
                r=subprocess.run([a.vvp,str(exe)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
                print(('filtered'if filtered else'portable')+' '+r.stdout.strip(),flush=True)
                if r.returncode:raise SystemExit(r.returncode)


if __name__=='__main__':main()
