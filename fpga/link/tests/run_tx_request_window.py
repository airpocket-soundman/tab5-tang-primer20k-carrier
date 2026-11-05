"""TX frequency/SYS phase/DATA window sweep on the immutable 8877 RTL snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'fpga'))
from reference.link_protocol import request,seal,crc16


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools',type=Path,required=True)
    p.add_argument('--primitive-lib',type=Path,required=True)
    p.add_argument('--rtl-root',type=Path,default=ROOT/'fpga/build/speed-filter-v1/source_snapshot')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--phases',type=int,default=10)
    p.add_argument('--quick',action='store_true')
    p.add_argument('--request-ff',action='store_true')
    p.add_argument('--request-fifo',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=[]
    packets=[]
    q=request(2,0x11,0x5a,0xa5);packets.append((q,seal(bytes([0x5a,0,q[2],2,0x5a,0xa5])),0))
    records={
        0x41:[[600+n,0,620+n,50,630+n,100,n*503&65535,n*997&65535,n*1997&65535,n*313&65535]for n in range(64)],
        0x6e:[[(n*7)%32,(n*11)%32,(n*17)%32,(n*23)%32,n*503&65535,n*449&65535,n*13&255,0,0,0]for n in range(64)],
        0x5f:[[(i*197)^0xa753 for i in range(n*10,n*10+10)]for n in range(64)],
    }
    for kind,(op,recs) in enumerate(records.items(),1):
        q=request(op,0x20+kind,64,1)
        payload=b''.join((v&65535).to_bytes(2,'little')for rec in recs for v in rec)
        wire=q+payload+crc16(q[:6]+payload).to_bytes(2,'little')
        packets.append((wire,seal(bytes([0x5a,0,q[2],2,64,1])),kind))
    vf=a.output/'vectors.txt';vf.write_text(''.join(f'{len(q)} {len(r)} {kind} '+' '.join(f'{b:02x}'for b in q+r)+'\n'for q,r,kind in packets),encoding='ascii')
    names=['link/rtl/triangle_batch.v','link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
           'gfx/rtl/triangle_tile_vendor.v','gfx/rtl/tile_dpram_vendor.v','gfx/rtl/raster2d.v','gfx/rtl/fire_tile.v',
           'gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage_pipeline.v','gfx/rtl/triangle_depth.v']
    if a.request_fifo:names.append('link/rtl/request_capture_fifo.v')
    sources=[a.rtl_root/n for n in names]
    bench=ROOT/'fpga/link/tests/tb_tx_request_window.v'
    env=dict(os.environ,PATH=str(a.tools.resolve())+os.pathsep+os.environ['PATH'])
    plans=[(10000000,100000,50000),(16000000,62500,31250),(20000000,50000,25000)]
    if not a.quick:plans += [(26666667,37500,18750),(32000000,31250,12500)]
    for hz,period,high in plans:
        profiles=[('falling_edge',period-high,high)]
        if not a.quick:profiles += [('short_hold_8ns',period-high,8000),('late_data_2ns',-2000,high),('same_edge',0,high)]
        for profile,setup,hold in profiles:
            for phase in [1+n*18518//a.phases for n in range(a.phases)]:
                label=f'{hz}-{profile}-{phase}';exe=(a.output/'test.vvp').resolve()
                params=dict(PERIOD_PS=period,HIGH_PS=high,SETUP_PS=setup,HOLD_PS=hold,PHASE_PS=phase)
                cmd=[str(a.tools/'iverilog.exe'),'-g2012','-s','tb_tx_request_window',*[f'-Ptb_tx_request_window.{k}={v}'for k,v in params.items()],
                     *(['-DREQUEST_FF'] if a.request_ff else []),*(['-DREQUEST_FIFO'] if a.request_fifo else []),'-o',str(exe),*map(str,sources),str(bench),str(a.primitive_lib.resolve())]
                r=subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
                if r.returncode:raise RuntimeError(r.stdout)
                r=subprocess.run([str(a.tools/'vvp.exe'),str(exe),'+vectors='+str(vf.resolve())],cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
                (a.output/(label+'.log')).write_text(r.stdout,encoding='utf-8')
                if r.returncode:raise RuntimeError(label+'\n'+r.stdout)
                result=[list(map(int,line.split(',')[1:]))for line in r.stdout.splitlines()if line.startswith('TXWINDOW,')]
                if len(result)!=4:raise RuntimeError('Incomplete packet cases')
                for values in result:
                    rows.append(dict(configured_hz=hz,profile=profile,period_ps=period,high_ps=high,
                                     setup_ps=setup,hold_ps=hold,phase_ps=phase,kind=values[5],request_bytes=values[6],
                                     response_exact=bool(values[7]),all_640_staging_words_exact=bool(values[8]),wait_sys_cycles=values[9]))
            chosen=[x for x in rows if x['configured_hz']==hz and x['profile']==profile]
            print(hz,profile,sum(x['response_exact']and x['all_640_staging_words_exact']for x in chosen),'/',len(chosen),flush=True)
    summary=[]
    for hz,_,_ in plans:
        for profile in sorted({r['profile']for r in rows if r['configured_hz']==hz}):
            group=[r for r in rows if r['configured_hz']==hz and r['profile']==profile]
            summary.append(dict(configured_hz=hz,profile=profile,passed=sum(r['response_exact']and r['all_640_staging_words_exact']for r in group),cases=len(group)))
    report=dict(hardware_access=False,scope='digital RTL on immutable 8877 source, ideal pin levels, no analog setup/hold or MTBF/physical qualification',
                rtl_snapshot=str(a.rtl_root.resolve()),sys_period_ps=18518,sampler_period_ps=4630,
                packet_kinds=['scalar8','TRI_BATCH64/1290bytes','R2_BATCH64/1290bytes','UPLOAD64/1290bytes'],
                poison_outside_data_window=True,sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources+[bench]},
                primitive_lib_sha256=hashlib.sha256(a.primitive_lib.read_bytes()).hexdigest(),cases=rows,summary=summary)
    (a.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
