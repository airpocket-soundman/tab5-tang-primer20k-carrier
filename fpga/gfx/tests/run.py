"""Run with an existing Icarus only; no installation or hardware access."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');a=p.parse_args()
if not shutil.which(a.iverilog) or not shutil.which(a.vvp):
    p.exit(2,'RTL NOT RUN: existing Icarus/vvp not found; no installation or device action.\n')
subprocess.run([sys.executable,str(ROOT/'gfx/tests/generate_vectors.py'),'--check'],check=True,cwd=ROOT)
with tempfile.TemporaryDirectory(prefix='game-rtl-') as directory:
    exe=Path(directory)/'coverage.vvp'
    subprocess.run([a.iverilog,'-g2012','-Wall','-s','tb_triangle_coverage','-o',str(exe),str(ROOT/'gfx/rtl/triangle_coverage.v'),str(ROOT/'gfx/tests/tb_triangle_coverage.v')],check=True,cwd=ROOT)
    subprocess.run([a.vvp,str(exe)],check=True,cwd=ROOT)
