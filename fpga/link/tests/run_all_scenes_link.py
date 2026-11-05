"""Pin-level 2D/upload batch CRC staging and shared tile-RAM oracle; no hardware."""
import argparse
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'fpga'))
from reference.link_protocol import crc16, request, seal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', type=Path, required=True)
    p.add_argument('--output', type=Path, default=ROOT/'fpga/build/all-scenes-link-tests')
    p.add_argument('--fast-reply', action='store_true')
    p.add_argument('--registered-input', action='store_true')
    p.add_argument('--vendor-primitive-lib', type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    canvas = [0]*1024
    vectors = []
    seq = 0

    def next_request(op, value=0, tag=False):
        nonlocal seq
        q = request(op | (128 if tag else 0), seq & 255, value & 255, value >> 8)
        seq += 1
        return q

    def reply(q, status, value):
        return (b'\xc3'*8 if q[1] & 128 else b'') + seal(bytes([0x5a,status,q[2],2,value&255,value>>8]))

    def scalar(op, value=0, status=0, result=None, tag=False):
        q = next_request(op, value, tag)
        vectors.append((q, reply(q, status, value if result is None else result)))

    def pixels():
        q = next_request(0x3b, tag=True)
        header = bytes([0x5a,0,q[2],2,0,0])
        data = b''.join(v.to_bytes(2,'little') for v in canvas)
        vectors.append((q,b'\xc3'*8+seal(header)+data+crc16(header+data).to_bytes(2,'little')))

    def put(x,y,color):
        if 0 <= x < 32 and 0 <= y < 32:
            canvas[y*32+x] = color

    def draw(record):
        x0,y0,x1,y1,ink,rg,b,kind,_,_ = record
        if kind == 0:
            put(x0,y0,ink)
        elif kind == 1:
            x,y = x0,y0
            dx,dy = abs(x1-x0),-abs(y1-y0)
            sx,sy = (1 if x0 < x1 else -1),(1 if y0 < y1 else -1)
            error = dx+dy
            while True:
                put(x,y,ink)
                if (x,y) == (x1,y1):
                    break
                twice = error*2
                if twice >= dy:
                    error += dy; x += sx
                if twice <= dx:
                    error += dx; y += sy
        elif kind == 2:
            for y in range(max(0,y0),min(31,y1)+1):
                for x in range(max(0,x0),min(31,x1)+1):
                    put(x,y,ink)
        elif kind == 3 and 0 <= x0 < 32 and 0 <= y0 < 32:
            old = canvas[y0*32+x0]
            r = min(255,(old>>11)*255//31+(rg>>8))
            g = min(255,((old>>5)&63)*255//63+(rg&255))
            blue = min(255,(old&31)*255//31+b)
            put(x0,y0,((r&248)<<8)|((g&252)<<3)|(blue>>3))

    def batch(op, records, *, corrupt=None, tag=False, abort=False):
        q = next_request(op, 256|len(records), tag)
        data = b''.join((v&65535).to_bytes(2,'little') for rec in records for v in rec)
        wire = bytearray(q+data+crc16(q[:6]+data).to_bytes(2,'little'))
        if corrupt is not None:
            wire[corrupt] ^= 1
        if abort:
            vectors.append((wire[:20],b''))
        else:
            vectors.append((wire,reply(q,1 if corrupt is not None else 0,256|len(records))))
            if op == 0x6e and corrupt is None:
                for rec in records:
                    draw(rec)

    scalar(0x60,result=0x011f)
    scalar(0x70,result=0x0101,tag=True)
    scalar(0x2b,0x0042,result=0)
    canvas[:] = [0x0042]*1024
    # Native scene_2d.cpp Wire frame0/load0, first nonempty tile (32,0).
    # Reproduce with fpga/gfx/tests/wire_first_tile.cpp against the host sources.
    wire_records = [[20,17,75,17,35793,35960,136,1,0,0],
                    [20,72,20,17,35793,35960,136,1,0,0],
                    [31,28,64,28,35793,35960,136,1,0,0],
                    [31,61,31,28,35793,35960,136,1,0,0],
                    [20,17,31,28,35793,35960,136,1,0,0]]
    batch(0x6e,wire_records,tag=True)
    pixels()
    # Small gate-level reproduction shares precisely the RTL oracle vectors.
    (a.output/'wire-first-vectors.txt').write_text(''.join(f'{len(q)} {len(r)} '+' '.join(f'{v:02x}' for v in bytes(q)+r)+'\n' for q,r in vectors),encoding='ascii')
    rng = random.Random(20261105)
    records = []
    for n in range(64):
        kind = n%4
        coords = [rng.randrange(-8,40) for _ in range(4)]
        if kind in (0,3):
            coords[:2] = [n%32,(n*7)%32]
        if kind == 2:
            coords = [min(coords[0],coords[2]),min(coords[1],coords[3]),max(coords[0],coords[2]),max(coords[1],coords[3])]
        records.append(coords+[rng.randrange(65536),0x3264,0xc8,kind,0,0])
    batch(0x6e,records,tag=True)
    pixels()
    for offset in (8,31,647,1287,1288,1289):
        batch(0x6e,records,corrupt=offset,tag=bool(offset&1))
        pixels()
    # Upload uses a separate staging bank. A corrupted bank cannot advance the cursor.
    scalar(0x6d,result=0)
    upload = [(n*197)^0xa753 for n in range(1024)]
    upload = [v&65535 for v in upload]
    batch(0x5f,[upload[n:n+10] for n in range(0,640,10)],tag=True)
    batch(0x5f,[upload[n:n+10] for n in range(640,1020,10)],corrupt=100)
    batch(0x5f,[upload[n:n+10] for n in range(640,1020,10)])
    for n in range(1020,1024):
        scalar(0x6c,upload[n],result=n+1)
    canvas[:] = upload
    pixels()
    # Switching back to 2D must neither reuse nor alias the upload bank.
    batch(0x6e,records[:2],tag=True)
    pixels()
    # Truncated staging -> ARM drop -> no leaked execution after rearm.
    batch(0x6e,records,abort=True)
    scalar(0x2d,status=5,result=0)
    scalar(0x6b,status=5,result=0)
    scalar(0x2b,0x1234,result=0)
    canvas[:] = [0x1234]*1024
    pixels()
    batch(0x6e,records[:1])
    pixels()
    scalar(0x6d,result=0)
    batch(0x5f,[upload[:10]],abort=True)
    scalar(0x6c,0x1234,status=5,result=0)
    scalar(0x2b,0x5678,result=0)
    canvas[:] = [0x5678]*1024
    pixels()

    off = []
    for op in [0x5e,0x5f,*range(0x60,0x79)]:
        q = next_request(op, 0x101 if op in (0x5f,0x6e) else 0, tag=bool(op&1))
        off.append((q,reply(q,2,0)))
    sources = ['link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/triangle_tile.v',
               'gfx/rtl/raster2d.v','gfx/rtl/fire_tile.v','gfx/rtl/triangle_fragment.v',
               'gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_all_scenes_link.v']
    shared_flags = []
    if a.registered_input:
        shared_flags.append('-DREGISTERED_INPUT')
    if a.fast_reply:
        sources.append('link/rtl/link_reply_raw.v')
        shared_flags.append('-DFAST_REPLY')
    paths = [str(ROOT/'fpga'/s) for s in sources]
    if a.vendor_primitive_lib:
        paths[sources.index('gfx/rtl/triangle_tile.v')] = str(ROOT/'fpga/gfx/rtl/triangle_tile_vendor.v')
        paths += [str(ROOT/'fpga/gfx/rtl/tile_dpram_vendor.v'), str(a.vendor_primitive_lib.resolve())]
        shared_flags.append('-DVENDOR_RAM')
    env = dict(os.environ,PATH=str(a.tools.resolve())+os.pathsep+os.environ['PATH'])
    for label, rows, flags in [('enabled',vectors,[]),('disabled',off,['-DFEATURE_OFF'])]:
        vf = a.output/(label+'.txt')
        vf.write_text(''.join(f'{len(q)} {len(r)} '+' '.join(f'{v:02x}' for v in bytes(q)+r)+'\n' for q,r in rows),encoding='ascii')
        sim = (a.output/(label+'.vvp')).resolve()
        for step, cmd in [('compile',['iverilog','-g2012','-Wall',*shared_flags,*flags,'-s','tb_all_scenes_link','-o',str(sim),*paths]),
                          ('run',['vvp',str(sim),'+vectors='+str(vf.resolve())])]:
            cmd[0] = shutil.which(cmd[0],path=env['PATH']) or cmd[0]
            result = subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (a.output/(label+'-'+step+'.log')).write_text(result.stdout,encoding='utf-8')
            print(result.stdout,end='')
            if result.returncode:
                raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
