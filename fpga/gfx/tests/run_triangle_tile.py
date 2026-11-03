"""Full color/depth oracle through Dock pins; no hardware access."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reference.triangle_tile import TriangleTile
from reference.link_protocol import request
from tools.dock_triangle_demo import exercise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', default='iverilog')
    p.add_argument('--vvp', default='vvp')
    args = p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp):
        p.error('existing Icarus and vvp required')
    oracle, vectors = TriangleTile(), []
    def exchange(frame):
        expected = oracle.exchange(frame)
        vectors.append((frame, expected))
        return expected
    # Reject uninitialized, out-of-range, unknown, malformed CRC/length/magic.
    for op,a,b in [(0x2c,0,0),(0x2d,0,0),(0x2e,32,0),(0x2d,0,255),
                   (0x2c,1,0),(0x2f,0,0),(0x10,0,0)]:
        exchange(request(op,len(vectors)&255,a,b))
    for index in (0,3,6):
        bad=bytearray(request(0x2b,31,0,0)); bad[index]^=1; exchange(bad)
    exchange(request(0x2b,32,0,0))
    exchange(request(0x21,33,0,0))
    exchange(request(0x2c,34,0,0))  # A partial parameter set cannot draw.
    _, report = exercise(exchange)
    # After CLEAR, an incomplete register file must still reject DRAW.
    # Reset is exercised in the Verilog bench, which also checks bus release.
    with tempfile.TemporaryDirectory(prefix='triangle-tile-') as tmp:
        tmp=Path(tmp)
        vf=tmp/'vectors.txt'
        vf.write_text(''.join(' '.join(f'{b:02x}' for b in q+r)+'\n' for q,r in vectors),encoding='ascii')
        exe=tmp/'test.vvp'
        sources=['link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/triangle_tile.v',
                 'gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v',
                 'platform/dock/tab5_dock_top.v','gfx/tests/tb_triangle_tile_dock.v']
        subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_triangle_tile_dock','-o',str(exe),
                        *[str(ROOT/s) for s in sources]],check=True)
        subprocess.run([args.vvp,str(exe),'+vectors='+str(vf)],check=True,timeout=180)
    print(f'PASS {len(vectors)} wire transactions; {report}; no hardware access')


if __name__ == '__main__': main()
