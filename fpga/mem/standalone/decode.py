"""Decode and independently validate standalone 111-byte UART records."""
import argparse, json, struct, sys
from functools import lru_cache
from pathlib import Path

def crc16(data):
    c=0xffff
    for b in data:
        c ^= b << 8
        for _ in range(8): c=((c<<1)^0x1021 if c&0x8000 else c<<1)&0xffff
    return c

@lru_cache(maxsize=26)
def expected_checksum(seed, beats):
    mask=(1<<32)-1; m64=(1<<64)-1
    keys=[0x9e3779b9,0x243f6a88,0xb7e15162,0x85ebca6b]
    lanes=[(seed^keys[0]) or keys[0],*keys[1:]]; a=b=0
    for _ in range(beats):
        fold=(lanes[3]<<32|lanes[2])^(lanes[1]<<32|lanes[0])
        a=(a+fold)&m64; b=(((b<<1)|(b>>63))&m64)^fold
        for j,x in enumerate(lanes):
            x=(x^((x<<13)&mask))&mask; x=(x^(x>>17))&mask; lanes[j]=(x^((x<<5)&mask))&mask
    return (b<<64)|a

def expected_job(job):
    if job<2:return (job,0)
    group,phase=divmod(job-2,4)
    return ((0,group+1),(1,0),(0,0),(1,group+1))[phase]

def decode(data,beats=65536):
    pos=0; records=[]; errors=[]
    while pos<len(data):
        if data[pos:pos+4]!=b'DBW1': errors.append(f'unexpected byte at offset {pos}');break
        f=data[pos:pos+111]
        if len(f)!=111: errors.append(f'truncated record at {pos}');break
        if crc16(f[:109])!=int.from_bytes(f[109:111],'little'): errors.append(f'CRC mismatch at {pos}');break
        job,mode,bl,flags,err=struct.unpack_from('<5B',f,4);seed=struct.unpack_from('<I',f,9)[0]
        cyc,cmd,wb,rb,cs,ws=struct.unpack_from('<6Q',f,13)
        cw=int.from_bytes(f[61:77],'little');cr=int.from_bytes(f[77:93],'little');ce=int.from_bytes(f[93:109],'little')
        r=dict(job=job,mode=mode,burst_log2=bl,flags=flags,error=err,seed=seed,cycles=cyc,commands=cmd,wbeats=wb,rbeats=rb,cmd_stall=cs,wd_stall=ws,ck_wr=f'{cw:032x}',ck_rd=f'{cr:032x}',ck_exp=f'{ce:032x}',mb_per_s=((wb if mode==0 else rb)*16*99.5625/cyc if cyc else 0))
        records.append(r);pos+=111
        if job!=len(records)-1 or job>=26: errors.append(f'wrong job sequence at record {len(records)-1}');break
        if err or flags&4: errors.append(f'job {job}: device error {err}, flags {flags:02x}');break
        if (mode,bl)!=expected_job(job): errors.append(f'job {job}: unexpected mode/burst');break
        if seed!=(0x12345678 ^ (job>>1)) or flags!=(1 if mode==0 else 2): errors.append(f'job {job}: unexpected seed/flags');break
        if cyc<beats or cmd!=beats//(1<<bl) or wb!=(beats if mode==0 else 0) or rb!=(beats if mode==1 else 0): errors.append(f'job {job}: invalid counters');break
        expected=expected_checksum(seed,beats)
        if ce!=expected or (cw if mode==0 else cr)!=expected: errors.append(f'job {job}: checksum mismatch');break
    if len(records)!=26 and not errors: errors.append(f'incomplete capture: {len(records)}/26 records')
    return {'records':records,'errors':errors,'complete':not errors and len(records)==26}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--beats',type=int,default=65536);p.add_argument('--json',type=Path);a=p.parse_args()
    result=decode(a.capture.read_bytes(),a.beats)
    if a.json:a.json.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    for r in result['records']:print(' '.join(f'{k}={v}' for k,v in r.items()))
    for e in result['errors']:print('ERROR:',e,file=sys.stderr)
    sys.exit(not result['complete'])
