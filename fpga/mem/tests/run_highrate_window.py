"""Bounded phase3 window sensitivity; no hardware, synthesis or FS writes."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--iverilog',required=True);ap.add_argument('--vvp',required=True);ap.add_argument('--report',required=True);args=ap.parse_args()
root=Path(__file__).resolve().parents[2];build=root/'build/memv1-highrate-window';build.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();tool=Path(args.iverilog).resolve().parent;env['PATH']=str(tool)+os.pathsep+str(tool.parent/'lib')+os.pathsep+env['PATH']
def crc(b):
 c=65535
 for v in b:
  c^=v<<8
  for _ in range(8):c=((c<<1)^0x1021)&65535 if c&32768 else (c<<1)&65535
 return c
header=bytes.fromhex('5a005c020100');payload=bytes(((i*73)^(i>>3)^((i>>8)*29)^0xa7)&255 for i in range(4096))
expected=b'\xc3'*8+header+crc(header).to_bytes(2,'little')+payload+crc(header+payload).to_bytes(2,'little')
vec=build/'expected.hex';vec.write_text('\n'.join(f'{b:02x}' for b in expected)+'\n',encoding='ascii')
sources=[root/'link/rtl/reply_clock_filter.v',root/'link/rtl/reply_phase_delay.v',root/'mem/rtl/memv1_reply_raw.v',root/'mem/tests/tb_memv1_highrate_window.v']
image=build/'window.vvp';subprocess.run([args.iverilog,'-g2012','-s','tb_memv1_highrate_window','-o',str(image),*map(str,sources)],check=True,env=env)
rows=[]
for period,high in ((37500,18750),(31250,15625),(31250,12500),(31250,18750)):
 for phase in (0,1500,3000):
  for wire,tco in ((0,0),(2000,2000),(5000,2000)):
   for jitter in (0,200):
    command=[args.vvp,str(image),f'+VEC={vec}',f'+PERIOD={period}',f'+HIGH={high}',f'+PHASE={phase}',f'+WIRE={wire}',f'+TCO={tco}',f'+JITTER={jitter}']
    p=subprocess.run(command,check=True,env=env,capture_output=True,text=True,timeout=20)
    line=next(x for x in p.stdout.splitlines() if x.startswith('WINDOW,'));v=list(map(int,line.split(',')[1:]));keys=('period_ps','high_ps','sample_phase_ps','one_way_wire_ps','output_tco_ps','assumed_sampler_jitter_ps','unique_full_frame_matches','frame_offset','raw_rises','clean_rises','reply_rises','minimum_filter_latency_ps','maximum_filter_latency_ps','filter_fault_seen','first_bad_expected_byte')
    row=dict(zip(keys,v));row['full_4kib_frame_passed']=row['unique_full_frame_matches']==1;rows.append(row)
report={'scope':'Isolated real filter/phase3/serializer RTL plus synchronous128bit memory fixture; not a P4/IO/PLL hardware timing guarantee','sampling':'physical falling, initial CLK HIGH established at DIR0; complete tagged4KiB RD plus both CRCs checked','jitter_assumption':'0 or alternating +/-200ps sampler period perturbation, hypothetical sensitivity only, not measured PLL jitter','conditions':rows,'sources':{str(p.relative_to(root)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'lf_sha256':hashlib.sha256(p.read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()} for p in sources}}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
for period,high in sorted({(r['period_ps'],r['high_ps']) for r in rows}):
 selected=[r for r in rows if r['period_ps']==period and r['high_ps']==high];print(period,high,'fullframe',sum(r['full_4kib_frame_passed'] for r in selected),'/',len(selected),'edgecounts all matched',flush=True)
