"""fire_pixel RTL vs fpga/reference/fire_g0.py. Existing Icarus/vvp only; no install, no devices."""
import argparse
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference import fire_g0 as F

def vectors():
    rng=random.Random(20261104)
    v=[(0,0,0,1),(639,359,0,6),(320,180,17,4),(0,383,65535,6),(639,0,65535,2),(671,383,65535,6),
       (320,359,0,6),(320,0,4095,2),(1,1,1,1),(638,358,65534,5)]
    for octaves in (1,2,3,4,5,6):
        for _ in range(60):
            v.append((rng.randrange(0,672),rng.randrange(0,384),rng.choice([0,1,17,403,4095,65535,rng.randrange(65536)]),octaves))
    return v

parser=argparse.ArgumentParser();parser.add_argument('--iverilog',default='iverilog');parser.add_argument('--vvp',default='vvp');args=parser.parse_args()
if not shutil.which(args.iverilog) or not shutil.which(args.vvp):
    parser.exit(2,'FIRE PIXEL RTL NOT RUN: existing Icarus/vvp not found; no install/device action.\n')
vec=vectors()
with tempfile.TemporaryDirectory(prefix='fire-pixel-') as directory:
    d=Path(directory)
    lines=[]
    for x,y,frame,octaves in vec:
        exp=F.color(x,y,frame,octaves)
        lines.append('%016x'%((x<<45)|(y<<35)|(frame<<19)|(octaves<<16)|exp))
    (d/'vec.mem').write_text('\n'.join(lines)+'\n')
    exe=d/'fire_pixel.vvp'
    subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_fire_pixel','-o',str(exe),
                    str(ROOT/'gfx/rtl/fire_pixel.v'),str(ROOT/'gfx/tests/tb_fire_pixel.v')],cwd=ROOT,check=True)
    subprocess.run([args.vvp,str(exe),'+VEC='+str(d/'vec.mem'),'+COUNT=%d'%len(vec)],cwd=ROOT,check=True)
