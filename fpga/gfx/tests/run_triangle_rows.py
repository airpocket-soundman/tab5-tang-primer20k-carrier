"""Exercise variable-length triangle rows through Dock pins; no device access."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.triangle_tile import TriangleTile, ROW
from reference.link_protocol import request
from tools.dock_triangle_demo import exercise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',default='iverilog')
    p.add_argument('--vvp',default='vvp')
    args=p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp): p.error('existing Icarus/vvp required')
    model,vectors=TriangleTile(),[]
    def exchange(q):
        r=model.exchange(q); vectors.append((q,r)); return r
    for row,plane in [(0,0),(31,1),(32,0),(0,2),(255,255)]:
        exchange(request(ROW,len(vectors),row,plane))
    bad=bytearray(request(ROW,17,0,0));bad[6]^=1;exchange(bad)
    _,report=exercise(exchange,comprehensive=True,bulk=True)
    # Range and CRC rejection remain short replies after initialization too.
    exchange(request(ROW,21,32,0));exchange(request(ROW,22,0,2));exchange(bad)
    with tempfile.TemporaryDirectory(prefix='triangle-rows-') as td:
        td=Path(td);vf=td/'vectors.txt';exe=td/'test.vvp'
        vf.write_text(''.join(str(len(r))+' '+' '.join(f'{b:02x}' for b in q+r)+'\n' for q,r in vectors),encoding='ascii')
        sources=['link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v',
                 'gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v',
                 'platform/dock/tab5_dock_top.v','gfx/tests/tb_triangle_rows.v']
        subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_triangle_rows','-o',str(exe),
                       *[str(ROOT/s) for s in sources]],check=True)
        subprocess.run([args.vvp,str(exe),'+vectors='+str(vf)],check=True,timeout=180)
    print(f'PASS triangle ROW {len(vectors)} oracle transactions, {report}; no hardware access')


if __name__=='__main__':main()
