"""Full pin-level color/Z comparison and candidate limits for bbox traversal."""
import argparse
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.triangle_tile import TriangleTile
from reference.link_protocol import request


def candidate_limit(xy):
    xmin=max(0,min(xy[::2])//16);xmax=min(31,max(xy[::2])//16)
    ymin=max(0,min(xy[1::2])//16);ymax=min(31,max(xy[1::2])//16)
    if xmin>xmax or ymin>ymax:return 0
    ax,ay,bx,by,cx,cy=xy
    if (bx-ax)*(cy-ay)==(by-ay)*(cx-ax): return 1
    return (xmax-xmin+1)*(ymax-ymin+1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
    args=p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp):p.error('existing Icarus/vvp required')
    model,vectors=TriangleTile(),[]
    def exchange(op,value=0,b=None,cap=1024):
        if b is None:a,b=value&255,(value>>8)&255
        else:a=value
        q=request(op,len(vectors)&255,a,b);r=model.exchange(q);vectors.append((q,r,cap))
    triangles=[(0,0,16,0,0,16),(8,8,24,8,8,24),(-1,-1,17,-1,-1,17),
               (-48,-32,-1,-32,-1,-1),(-1,0,-1,32,-1,64),
               (512,0,528,0,512,32),(0,512,32,512,0,528),
               (496,496,512,496,496,512),(511,511,527,511,511,527),
               (-32768,-32768,32767,-32768,0,32767),
               (-32768,0,-32767,16,-32766,0),(32767,0,32766,16,32765,0),
               (0,0,256,256,496,496),(120,120,120,120,120,120),
               (8,8,40,8,8,40),(8,40,40,8,8,8)]
    rng=random.Random(20261103)
    for _ in range(16):
        x,y=rng.randint(-48,520),rng.randint(-48,520)
        triangles.append(tuple(v for _ in range(3) for v in (x+rng.randint(-32,32),y+rng.randint(-32,32))))
    total_cap=0
    for index,xy in enumerate(triangles):
        exchange(0x2b,0x0841)
        for k,v in enumerate([*xy,100+index,400+index,900+index,0xf800+index]):exchange(0x21+k,v&65535)
        cap=candidate_limit(xy);total_cap+=cap;exchange(0x2c,cap=cap)
        for plane in (0,1):
            for row in range(32):exchange(0x2f,row,plane)
    with tempfile.TemporaryDirectory(prefix='triangle-bbox-') as td:
        td=Path(td);vf=td/'vectors.txt';exe=td/'test.vvp'
        vf.write_text(''.join(f'{len(r)} {cap} '+' '.join(f'{b:02x}' for b in q+r)+'\n' for q,r,cap in vectors),encoding='ascii')
        sources=['link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v',
                 'gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','platform/dock/tab5_dock_top.v','gfx/tests/tb_triangle_bbox.v']
        subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_triangle_bbox','-o',str(exe),*[str(ROOT/s) for s in sources]],check=True)
        subprocess.run([args.vvp,str(exe),'+vectors='+str(vf)],check=True,timeout=180)
    print(f'PASS bbox {len(triangles)} triangles,{len(vectors)} wire transactions,{len(triangles)*2048} color/depth pixels; candidate cap sum{total_cap} versus previous{len(triangles)*1024}; no hardware access')
if __name__=='__main__':main()
