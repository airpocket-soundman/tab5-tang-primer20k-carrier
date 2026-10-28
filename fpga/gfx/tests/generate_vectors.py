"""Generate coverage-only G0 vectors from the existing integer game reference."""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.game_gpu_reference import Vertex,edge,inclusive
OUT=Path(__file__).resolve().parent


def coverage(vertices,x,y):
    a,b,c=vertices
    signed_area=edge(a,b,c.x,c.y)
    if signed_area==0:
        return (False,True,False,0,0,0,0)
    swapped=signed_area<0
    if swapped: b,c=c,b
    area=abs(signed_area)
    p=(x*16+8,y*16+8)
    weights=(edge(b,c,*p),edge(c,a,*p),edge(a,b,*p))
    covered=all(w>0 or w==0 and inclusive(u,v) for w,(u,v) in zip(weights,((b,c),(c,a),(a,b))))
    wa,wb,wc=weights
    return (covered,False,swapped,area,wa,wc if swapped else wb,wb if swapped else wc)


def vectors():
    result=[]
    def add(coords,x,y):
        vertices=tuple(Vertex(coords[i],coords[i+1],0) for i in (0,2,4))
        result.append((tuple(coords)+(x,y),coverage(vertices,x,y)))
    # Edge-aligned and fractional samples, both windings, shared diagonal.
    triangles=[(0,0,128,0,0,128),(128,0,128,128,0,128),
        (8,8,120,8,8,120),(8,8,8,120,120,8),
        (-32768,-32768,32767,-32768,-32768,32767),
        (-32768,-32768,32767,32767,-32768,32767),
        (-32768,32767,32767,-32768,32767,32767),
        (0,0,0,0,0,0),(-32768,-32768,0,0,32767,32767),
        (-8,-8,136,8,8,136)]
    for tri in triangles:
        for y in range(8):
            for x in range(8):
                add(tri,x,y)
                add(tri[:2]+tri[4:]+tri[2:4],x,y)
    # Deterministic extreme-coordinates and random samples, including off-target.
    rng=random.Random(0x20261023)
    extreme=(-32768,-32767,-1,0,1,32766,32767)
    for i in range(2048):
        coords=tuple(rng.choice(extreme) if i%2 else rng.randint(-32768,32767) for _ in range(6))
        add(coords,rng.randrange(1024),rng.randrange(512))
    return result


def render_files():
    inputs=[]; expected=[]
    for inp,out in vectors():
        inputs.append(''.join(f'{v&0xffff:04x}' for v in inp))
        covered,deg,swap,area,wa,wb,wc=out
        flags=int(covered)|(int(deg)<<1)|(int(swap)<<2)
        expected.append(''.join(f'{v&((1<<64)-1):016x}' for v in (flags,area,wa,wb,wc)))
    return {'inputs.mem':'\n'.join(inputs)+'\n','expected.mem':'\n'.join(expected)+'\n'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in render_files().items():
        path=OUT/name
        if a.check:
            if not path.exists() or path.read_text()!=data: p.exit(1,f'fixture mismatch: {name}\n')
        else: path.write_text(data,encoding='ascii')
    manifest={'count':len(vectors()),'seed':'0x20261023','rtl_simulation':'not_run',
        'inputs_sha256':hashlib.sha256(render_files()['inputs.mem'].encode()).hexdigest(),
        'expected_sha256':hashlib.sha256(render_files()['expected.mem'].encode()).hexdigest()}
    if not a.check: (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'{len(vectors())} coverage vectors '+('verified' if a.check else 'generated'))
