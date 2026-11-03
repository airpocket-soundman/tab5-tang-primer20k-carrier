"""Exercise the dock top against the independent GFX model in Icarus."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reference.gfx_bench import GfxBench
from reference.link_protocol import request
from tools.dock_gfx_demo import exercise

p = argparse.ArgumentParser()
p.add_argument('--iverilog', default='iverilog')
p.add_argument('--vvp', default='vvp')
a = p.parse_args()
if not shutil.which(a.iverilog) or not shutil.which(a.vvp):
    p.exit(2, 'Icarus Verilog and vvp required; no device access.\n')
model = GfxBench()
vectors = []
def exchange(frame):
    reply = model.exchange(frame)
    vectors.append((frame, reply))
    return reply
for op, x, y in [(0x13,1,1), (0x14,1,1), (0x16,1,1),
                 (0x15,31,31), (0x16,2,1), (0x16,0,1),
                 (0x13,32,0), (0x14,0,32), (0x15,255,0),
                 (0x10,0,0), (0x11,0x34,0x12)]:
    exchange(request(op, len(vectors) & 255, x, y))
bad = bytearray(request(0x12, len(vectors) & 255, 0, 0))
bad[6] ^= 1
exchange(bad)
exercise(exchange)
for op, x, y in [(0x15,31,31), (0x16,1,1), (0x14,31,31),
                 (0x16,1,2), (0x16,33,1), (0x17,0,0)]:
    exchange(request(op, len(vectors) & 255, x, y))
with tempfile.TemporaryDirectory(prefix='dock-gfx-') as d:
    d = Path(d)
    vector_file = d/'vectors.txt'
    vector_file.write_text(''.join(' '.join(f'{b:02x}' for b in req+reply)+'\n' for req, reply in vectors), encoding='ascii')
    exe = d/'bench.vvp'
    subprocess.run([a.iverilog, '-g2012', '-Wall', '-s', 'tb_bench_dock', '-o', str(exe),
                    str(ROOT/'link/rtl/triangle_batch.v'),str(ROOT/'link/rtl/link_bringup.v'), str(ROOT/'gfx/rtl/gfx_bench.v'),
                    str(ROOT/'platform/dock/tab5_dock_top.v'), str(ROOT/'gfx/tests/tb_bench_dock.v')], check=True)
    subprocess.run([a.vvp, str(exe), '+vectors='+str(vector_file)], check=True)
print(f'PASS dock GFX: {len(vectors)} oracle transactions, 1024 image pixels; no hardware access')
