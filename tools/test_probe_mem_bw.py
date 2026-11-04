"""Offline test of tools/probe_mem_bw.py with a fake device built from the bit-level model (no UART)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fpga/mem/tests'))
import bw_model, probe_mem_bw as P

class Fake:
    def __init__(s): s.cfg={}; s.words=None; s.gen=0
    def call(s, cmd, **k):
        assert cmd=='mem' and k['action']=='bw'
        op,arg=k['op'],k['arg']; d=dict(device_status=0)
        if 0x60<=op<=0x6a: s.cfg[op]=arg; d['value']=arg
        elif op==0x6b: s.run(); d['value']=1
        elif op==0x6d: s.gen+=1; d['value']=s.gen
        elif op==0x6e: d['value']=s.words[arg]
        elif op==0x6f: d['value']={0:0x0150,1:8|1|2,2:s.gen,3:62,4:1,5:100}[arg]
        return d
    def run(s):
        c=s.cfg; g=lambda o:c[o]
        base=g(0x60)|g(0x61)<<16; n=g(0x62)|g(0x63)<<16; ctl=g(0x66); mode=ctl&3; bl=ctl>>10&7
        data=bw_model.data_stream(g(0x64)|g(0x65)<<16,n); ck=bw_model.checksum(data)
        L=1<<bl; wb=n if mode==0 else 0; rb=n if mode==1 else 0
        cyc=n if mode==0 else n+6
        w=[0]*62; w[0]=0x2|(8 if mode==0 else 16); w[2]=1
        def put(o,v,k): 
            for i in range(k): w[o+i]=v>>(16*i)&0xffff
        put(4,cyc,4); put(8,n//L,4); put(12,wb,4); put(16,rb,4); put(54,ck,8)
        put(38,ck if mode==0 else 0,8); put(46,ck if mode==1 else 0,8)
        s.words=w
j=P.job('w',0,0,4096); dev=P.Device(Fake()); _,words=dev.run(j,1,0.0,sleep=lambda x:None)
r=P.decode_snapshot(words); assert not P.check_result(j,r),P.check_result(j,r)
assert abs(r['efficiency']-1.0)<1e-9 and abs(r['mb_per_s']-1593.0)<1e-6
j=P.job('r',1,0,4096,burst_log2=3); _,words=dev.run(j,1,0.0,sleep=lambda x:None); assert not P.check_result(j,P.decode_snapshot(words))
for bad in (dict(burst_log2=3,beats=12),dict(pattern=5,run=0)):
    try: P.job('x',0,bad.get('pattern',0),bad.get('beats',64),**{k:v for k,v in bad.items() if k in('burst_log2','run')}); raise SystemExit('accepted')
    except ValueError: pass
print('PASS probe_mem_bw offline: decode, bandwidth 1593 MB/s ideal, validation')
