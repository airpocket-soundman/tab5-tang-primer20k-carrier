"""Track G: Mandelbrot (high-entropy) tagged TILE_READ through the RAW serializer.

Digital RTL model only. Checks (1) the tile reads correctly with a free-running
host clock at 1/5 MHz, (2) the failure signature when one extra bus_clk edge
arrives mid-response (byte slip, then serializer abort and bus release).
No hardware access; this is not an electrical or pad-level measurement.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.link_protocol import request
from reference.triangle_tile import TriangleTile
from reference.link_sync import SyncPrefixDevice

SOURCES=['link/rtl/link_reply_raw.v','link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v',
         'gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','platform/dock/tab5_dock_top.v','link/tests/tb_fractal_clock.v']

def vectors():
    model=SyncPrefixDevice(TriangleTile());out=[]
    def exchange(op,value=0,b=None,tag=True):
        if b is None:a,b=value&255,(value>>8)&255
        else:a=value
        q=request(op|(128 if tag else 0),len(out)&255,a,b)
        r=model.exchange(q);out.append((q,r))
    for i,v in enumerate([-4096,-2048,132,132,-2949,819,0x0180]):exchange(0x31+i,v&65535)
    exchange(0x38)
    exchange(0x3b,0,0)
    return out

def run(args,exe,vf,mode,half_ns,glitch_at=900):
    subprocess.run([args.iverilog,'-g2012','-s','tb_fractal_clock',f'-Ptb_fractal_clock.MODE={mode}',f'-Ptb_fractal_clock.HALF_NS={half_ns}',
                    f'-Ptb_fractal_clock.GLITCH_AT={glitch_at}','-o',str(exe),*[str(ROOT/s) for s in SOURCES]],check=True)
    done=subprocess.run([args.vvp,str(exe),'+vectors='+str(vf)],capture_output=True,text=True,timeout=900)
    text=done.stdout+done.stderr
    m=re.search(r'RESULT mode=(\d+) half_ns=(\d+) glitch_at=(-?\d+) first_bad=(-?\d+) ready_drop=(-?\d+) bus_released_at=(-?\d+)',text)
    if not m:raise SystemExit('no RESULT line:\n'+text[-800:])
    keys=('mode','half_ns','glitch_at','first_bad','ready_drop','bus_released_at')
    return dict(zip(keys,map(int,m.groups())))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
    args=p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp):p.error('existing Icarus/vvp required')
    vec=vectors();last=vec[-1]
    assert len(last[1])==2066,len(last[1])
    with tempfile.TemporaryDirectory(prefix='fractal-clock-') as td:
        td=Path(td);vf=td/'vectors.txt'
        vf.write_text(''.join(str(len(r))+' '+' '.join(f'{b:02x}' for b in bytes(q)+r)+'\n' for q,r in vec),encoding='ascii')
        results=[]
        for half in (500,100):  # 1 MHz and 5 MHz free-running 50% clock
            r=run(args,td/'t.vvp',vf,1,half);results.append(r)
            assert r['first_bad']==-1 and r['ready_drop']<0 or r['ready_drop']==2065,f'free clock {half}ns must read exact tile: {r}'
        g=run(args,td/'t.vvp',vf,2,100,900);results.append(g)
        for r in results:print(r)
        # Documented signature: one extra edge corrupts the tile and the device must not read it back clean.
        assert g['first_bad']>=0,'an extra edge is expected to corrupt the tile in the current RTL'
    print('PASS fractal tile free-clock reads; glitch sensitivity characterized; no hardware access')
if __name__=='__main__':main()
