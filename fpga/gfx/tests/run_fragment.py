"""Run only with an existing Icarus/vvp; never install or access devices."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--iverilog',default='iverilog');parser.add_argument('--vvp',default='vvp');args=parser.parse_args()
if not shutil.which(args.iverilog) or not shutil.which(args.vvp):
    parser.exit(2,'FRAGMENT RTL NOT RUN: existing Icarus/vvp not found; no install/device action.\n')
subprocess.run([sys.executable,str(ROOT/'gfx/tests/generate_fragment_vectors.py'),'--check'],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='fragment-rtl-') as directory:
    executable=Path(directory)/'fragment.vvp'
    subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_triangle_fragment','-o',str(executable),
                    *(str(ROOT/'gfx/rtl'/name) for name in ('triangle_coverage.v','triangle_depth.v','triangle_fragment.v')),
                    str(ROOT/'gfx/tests/tb_triangle_fragment.v')],cwd=ROOT,check=True)
    subprocess.run([args.vvp,str(executable)],cwd=ROOT,check=True)
