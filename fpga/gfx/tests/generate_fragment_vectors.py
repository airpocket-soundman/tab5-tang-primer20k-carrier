"""Candidate fragment oracle; host fixtures do not demonstrate RTL execution."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from generate_vectors import coverage, Vertex


def golden(values):
    ax,ay,bx,by,cx,cy,za,zb,zc,old,x,y,color=values
    covered,deg,_,area,wa,wb,wc=coverage((Vertex(ax,ay,za),Vertex(bx,by,zb),Vertex(cx,cy,zc)),x,y)
    z=(wa*za+wb*zb+wc*zc)//area if covered and not deg else 0
    return (int(covered),int(deg),0,int(covered and z>old),z,x,y,color)


def vectors():
    result=[]
    for coords in ((0,0,128,0,0,128),(0,0,0,128,128,0),
                   (0,0,128,128,256,256),(-32768,-32768,32767,-32768,0,32767)):
        for x,y in ((0,0),(1,1),(7,7),(8,0),(1023,511)):
            for depths in ((0,0,0),(65535,65535,65535),(0,10000,65535)):
                base=(*coords,*depths,0,x,y,0x1234)
                z=golden(base)[4]
                for old in (0,z,min(65535,z+1)):
                    result.append((*coords,*depths,old,x,y,0x1234))
    rng=random.Random(0x20261023)
    for _ in range(256):
        coords=tuple(rng.randint(-32768,32767) for _ in range(6))
        result.append((*coords,*(rng.randrange(65536) for _ in range(4)),
                       rng.randrange(16),rng.randrange(16),rng.randrange(65536)))
    return result


def render():
    encode=lambda values: ''.join(f'{v&((1<<64)-1):016x}' for v in values)
    return {'fragment_inputs.mem':'\n'.join(encode(v) for v in vectors())+'\n',
            'fragment_expected.mem':'\n'.join(encode(golden(v)) for v in vectors())+'\n'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    files=render()
    for name,data in files.items():
        path=OUT/name
        if args.check:
            if not path.exists() or path.read_text()!=data:parser.exit(1,'fragment fixture mismatch\n')
        else:path.write_text(data,encoding='ascii')
    if not args.check:
        (OUT/'fragment_manifest.json').write_text(json.dumps({
            'count':len(vectors()),'seed':'0x20261023','rtl_simulation':'not_run','synthesis':'not_run',
            'sha256':{name:hashlib.sha256(data.encode()).hexdigest() for name,data in files.items()}},indent=2)+'\n')
    print(f'{len(vectors())} fragment vectors '+('checked' if args.check else 'generated'))
