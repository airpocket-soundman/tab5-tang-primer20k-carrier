"""Exact Python integer depth oracle plus fixed-width restoring-divider check."""
import argparse,hashlib,json,random
from pathlib import Path
OUT=Path(__file__).resolve().parent
MAX_AREA=2*65535**2


def golden(inp):
    area,wa,wb,wc,za,zb,zc,old,covered=inp
    valid=0<area<=MAX_AREA and min(wa,wb,wc)>=0 and wa+wb+wc==area
    if not valid: return (True,False,0)
    if not covered: return (False,False,0)
    z=(wa*za+wb*zb+wc*zc)//area
    return (False,z>old,z)


def restoring(n,d):
    rem=q=0
    for bit in range(48,-1,-1):
        rem=(rem<<1)|((n>>bit)&1)
        sub=rem>=d
        if sub: rem-=d
        q=(q<<1)|sub
    return q,rem


def vectors():
    result=[]
    for area in (1,2,3,65535,(1<<32)-1,(1<<32),MAX_AREA):
        for depths in ((0,0,0),(65535,65535,65535),(0,65535,1),(1,2,3)):
            wa=area//3;wb=area//3;wc=area-wa-wb
            z=(wa*depths[0]+wb*depths[1]+wc*depths[2])//area
            for old in (0,z,min(65535,z+1),65535):
                result.append((area,wa,wb,wc,*depths,old,1))
    rng=random.Random(0x20261023)
    for _ in range(1024):
        area=rng.randint(1,MAX_AREA);wa=rng.randint(0,area);wb=rng.randint(0,area-wa);wc=area-wa-wb
        result.append((area,wa,wb,wc,*(rng.randrange(65536) for _ in range(4)),rng.randrange(2)))
    for area,wa,wb,wc in ((0,0,0,0),(-1,0,0,0),(1,-1,1,1),(1,0,0,0),(1,1,1,1),
                            (MAX_AREA+1,MAX_AREA+1,0,0),((1<<63)-1,(1<<63)-1,0,0),
                            (1,1<<40,0,0),(1,0,0,-(1<<63))):
        for covered in (0,1): result.append((area,wa,wb,wc,65535,65535,65535,0,covered))
    return result


def render():
    ins=[];outs=[]
    for v in vectors():
        ins.append(''.join(f'{x&((1<<64)-1):016x}' for x in v[:4])+''.join(f'{x:04x}' for x in v[4:8])+f'{v[8]:016x}')
        invalid,passed,z=golden(v);outs.append(f'{(int(invalid)<<16)|(int(passed)<<17)|z:016x}')
    return {'depth_inputs.mem':'\n'.join(ins)+'\n','depth_expected.mem':'\n'.join(outs)+'\n'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in render().items():
        if a.check:
            if (OUT/name).read_text()!=data:p.exit(1,'depth fixture mismatch\n')
        else:(OUT/name).write_text(data,encoding='ascii')
    if not a.check:(OUT/'depth_manifest.json').write_text(json.dumps({'count':len(vectors()),'seed':'0x20261023','rtl_simulation':'not_run',
        'inputs_sha256':hashlib.sha256(render()['depth_inputs.mem'].encode()).hexdigest(),
        'expected_sha256':hashlib.sha256(render()['depth_expected.mem'].encode()).hexdigest()},indent=2)+'\n')
    print(f'{len(vectors())} depth vectors '+('verified' if a.check else 'generated'))
