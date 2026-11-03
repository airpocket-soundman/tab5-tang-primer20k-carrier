"""Experimental RAW tagged serializer across real Dock pins, ROW/TILE CRCs."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.link_protocol import request,seal,crc_valid
from reference.triangle_tile import TriangleTile
from reference.link_sync import SyncPrefixDevice

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
    args=p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp):p.error('existing Icarus/vvp required')
    model=SyncPrefixDevice(TriangleTile());vectors=[]
    def exchange(op,value=0,b=None,tag=True):
        if b is None:a,b=value&255,(value>>8)&255
        else:a=value
        q=request(op|(128 if tag else 0),len(vectors)&255,a,b)
        r=model.exchange(q);vectors.append((q,r));return r
    exchange(1,tag=False);exchange(4,tag=False)
    for tag in (False,True):
        exchange(0x3c,tag=tag);exchange(0x3c,1,tag=tag)
        exchange(0x3b,0,0,tag=tag);exchange(0x3b,1,0,tag=tag);exchange(0x3b,0,2,tag=tag)
    for op in (1,2,3,4):
        for value in (0,0xffff,0xa55a):exchange(op,value)
    # Untagged known operations are unchanged, and malformed tags get the
    # ordinary error frame because their request CRC cannot authenticate tag.
    for op in (1,2,3,4):exchange(op,0x55aa,tag=False)
    for byte in (0,1,3,6,7):
        q=bytearray(request(0x81,17,0,0));q[byte]^=1;vectors.append((q,model.exchange(q)))
    exchange(0x7f);exchange(0x2f,0,0);exchange(0x2b)
    for i,v in enumerate([8,8,40,8,8,40,100,500,900,0xf81f]):exchange(0x21+i,v)
    exchange(0x2c)
    for tag in (False,True):
        for plane in (0,1):exchange(0x3b,0,plane,tag=tag)
    for plane in (0,1):
        for row in range(32):exchange(0x2f,row,plane)
    for i,v in enumerate([-4096,-2048,132,132,-2949,819,0x0180]):exchange(0x31+i,v&65535)
    exchange(0x30);exchange(0x38);exchange(0x39);exchange(0x3a)
    for tag in (False,True):
        for plane in (0,1):exchange(0x3b,0,plane,tag=tag)
    for plane in (0,1):
        for row in range(32):exchange(0x2f,row,plane)
    exchange(0x37,0x0380);exchange(0x38)
    for plane in (0,1):
        for row in range(32):exchange(0x2f,row,plane)
        exchange(0x3b,0,plane)
    # Last untagged valid frac DRAW leaves parameters for the bench's abort
    # checks and verifies that mode changes are per request, not persistent.
    exchange(0x38,tag=False);exchange(0x2f,31,1,tag=False)
    with tempfile.TemporaryDirectory(prefix='link-sync-') as td:
        td=Path(td);vf=td/'vectors.txt';exe=td/'test.vvp'
        vf.write_text(''.join(str(len(r))+' '+' '.join(f'{b:02x}' for b in bytes(q)+r)+'\n' for q,r in vectors),encoding='ascii')
        sources=['link/rtl/link_reply_raw.v','link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v',
                 'gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','platform/dock/tab5_dock_top.v','link/tests/tb_link_sync.v']
        subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_link_sync','-Ptb_link_sync.FAST_REPLY_ENABLE=1','-o',str(exe),*[str(ROOT/s) for s in sources]],check=True)
        subprocess.run([args.vvp,str(exe),'+vectors='+str(vf)],check=True,timeout=180)
    print(f'PASS LINK sync {len(vectors)} wire transactions; tagged ID/echo/invert/CAPS/triangle/fractal/ROW plus untagged/error/timeout/reset paths; no hardware access')
if __name__=='__main__':main()
