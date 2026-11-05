"""Offline216->54MHz request FIFO candidate; no integration or hardware."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools',type=Path,required=True)
    p.add_argument('--phases',type=int,default=32)
    p.add_argument('--primitive-lib',type=Path)
    p.add_argument('--physical-ff',action='store_true')
    a=p.parse_args()
    if a.phases<4 or a.phases>128:p.error('phases must be4..128')
    b=a.tools.resolve();env=dict(os.environ,PATH=str(b)+os.pathsep+str(b.parent/'lib')+os.pathsep+os.environ['PATH'])
    with tempfile.TemporaryDirectory(prefix='request-fifo-')as td:
        exe=Path(td)/'fifo.vvp'
        for skew in (0,10000):
            for n in range(a.phases):
                phase=(18520*n)//a.phases
                subprocess.run([str(b/'iverilog.exe'),'-g2012',*(['-DVENDOR_FF'] if a.physical_ff else []),'-s','tb_request_capture_fifo',
                    '-Ptb_request_capture_fifo.SYS_PHASE_PS='+str(phase),
                    '-Ptb_request_capture_fifo.PHYSICAL_FF='+str(int(a.physical_ff)),
                    '-Ptb_request_capture_fifo.CLK_SKEW_PS='+str(skew),'-o',str(exe),
                    str(ROOT/'link/rtl/request_capture_fifo.v'),str(ROOT/'link/tests/tb_request_capture_fifo.v'),*([str(a.primitive_lib)] if a.primitive_lib else [])],check=True,env=env,capture_output=True,timeout=30)
                r=subprocess.run([str(b/'vvp.exe'),str(exe)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
                print(r.stdout,end='',flush=True)
                if r.returncode:raise SystemExit(r.returncode)
    print(f'FIFO digital phase grid PASS: {a.phases} SYS/216 alignments x2 skew models, {a.phases*2*5*1290} exact bytes; not analog/STA/hardware qualification')


if __name__=='__main__':main()
