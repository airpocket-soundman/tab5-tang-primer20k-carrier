"""Run independent focused tests of the bounded primitive simulation models."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p=argparse.ArgumentParser()
p.add_argument('--iverilog',default='iverilog')
p.add_argument('--vvp',default='vvp')
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='gowin-bench-model-') as tmp:
    for top in ('tb_gowin_bench_models','tb_gowin_bench_unsupported','tb_gowin_bench_nonzero_init','tb_gowin_bench_unsupported_alu'):
        binary=Path(tmp)/(top+'.vvp')
        subprocess.run([a.iverilog,'-g2012','-Wall','-s',top,'-o',str(binary),
                        str(root/'simulation/gowin_bench_models.v'),
                        str(root/'simulation/tests/tb_gowin_bench_models.v')],check=True)
        result=subprocess.run([a.vvp,str(binary)],text=True,capture_output=True)
        if top != 'tb_gowin_bench_models':
            if result.returncode==0 or 'unsupported configuration' not in result.stdout+result.stderr:
                raise RuntimeError('unsupported parameters were not rejected: '+result.stdout+result.stderr)
            print('PASS unsupported configuration rejected')
        else:
            print(result.stdout,end='')
            if result.returncode:
                raise RuntimeError(result.stderr)
