"""Compare legacy and opt-in active-policy synchronization; no hardware."""
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
    p.add_argument('--waveform-matrix',action='store_true',help='Also repeat the existing92 waveform cases with pipeline enabled')
    a=p.parse_args()
    b=Path(a.iverilog).resolve().parent
    env=dict(os.environ,PATH=str(b)+os.pathsep+str(b.parent/'lib')+os.pathsep+os.environ['PATH'])
    with tempfile.TemporaryDirectory(prefix='filter-active-') as td:
        exe=Path(td)/'active.vvp'
        subprocess.run([a.iverilog,'-g2012','-s','tb_reply_clock_filter_active','-o',str(exe),
                        str(ROOT/'link/rtl/reply_clock_filter.v'),str(ROOT/'link/tests/tb_reply_clock_filter_active.v')],
                       check=True,env=env,timeout=30)
        r=subprocess.run([a.vvp,str(exe)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
        print(r.stdout,end='')
        if r.returncode:raise SystemExit(r.returncode)
        if a.waveform_matrix:
            original=(ROOT/'link/tests/tb_reply_clock_filter.v').read_text()
            before='reply_clock_filter dut('
            if original.count(before)!=1:raise ValueError('Unexpected legacy test fixture')
            fixture=Path(td)/'tb_pipeline_wave.v'
            fixture.write_text(original.replace(before,'reply_clock_filter #(.ACTIVE_PIPELINE(1)) dut('),encoding='utf-8')
            plans=[(32,0,1),(20,0,1),(16,0,1),(10,0,1),(8,0,1),(6,2,5),(6,0,1),(5,0,1),(4,0,1)]
            tests=[]
            for n,b,c in plans:
                for phase in range(0,4630,463):
                    tests.append(dict(PHASE_PS=phase,DIV_INTEGER=n,DIV_NUMERATOR=b,DIV_DENOMINATOR=c))
            tests.extend(dict(NOISE_MODE=mode)for mode in (1,2))
            for params in tests:
                subprocess.run([a.iverilog,'-g2012','-s','tb_reply_clock_filter',
                    *[f'-Ptb_reply_clock_filter.{k}={v}'for k,v in params.items()],
                    '-o',str(exe),str(ROOT/'link/rtl/reply_clock_filter.v'),str(fixture)],check=True,env=env,capture_output=True,timeout=30)
                r=subprocess.run([a.vvp,str(exe)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
                if r.returncode:raise RuntimeError(str(params)+'\n'+r.stdout)
            print('ACTIVE_PIPELINE1 waveform matrix PASS: 90 divider/phase cases, short-pulse rejection and short-spacing fault')


if __name__=='__main__':main()
