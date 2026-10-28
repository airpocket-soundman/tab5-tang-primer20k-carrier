"""Run only desktop simulation; never opens USB/serial or programs devices."""
import argparse, shutil, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--iverilog', default='iverilog')
p.add_argument('--vvp', default='vvp')
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
if not shutil.which(a.iverilog) or not shutil.which(a.vvp):
    p.exit(2, 'Icarus Verilog and vvp required. No hardware action taken.\n')
with tempfile.TemporaryDirectory(prefix='link-bringup-') as d:
    for name in ('tb_link_bringup', 'tb_link_vectors'):
        exe=Path(d)/(name+'.vvp')
        subprocess.run([a.iverilog,'-g2012','-Wall','-s',name,'-o',str(exe),str(root/'link/rtl/link_bringup.v'),str(root/f'link/tests/{name}.v')],check=True,cwd=root)
        subprocess.run([a.vvp,str(exe)],check=True,cwd=root)
