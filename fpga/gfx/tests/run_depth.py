"""Desktop depth RTL run, only if an existing Icarus is available."""
import argparse,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');a=p.parse_args()
if not shutil.which(a.iverilog) or not shutil.which(a.vvp):p.exit(2,'DEPTH RTL NOT RUN: existing Icarus/vvp not found; no install/device action.\n')
subprocess.run([sys.executable,str(ROOT/'gfx/tests/generate_depth_vectors.py'),'--check'],check=True,cwd=ROOT)
with tempfile.TemporaryDirectory(prefix='game-depth-rtl-') as d:
    exe=Path(d)/'depth.vvp'
    subprocess.run([a.iverilog,'-g2012','-Wall','-s','tb_triangle_depth','-o',str(exe),str(ROOT/'gfx/rtl/triangle_depth.v'),str(ROOT/'gfx/tests/tb_triangle_depth.v')],check=True,cwd=ROOT)
    subprocess.run([a.vvp,str(exe)],check=True,cwd=ROOT)
