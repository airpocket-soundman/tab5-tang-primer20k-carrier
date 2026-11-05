"""Existing SYS27 request RTL, POS5 failure control and NEG+preamble1 WR/CANCEL."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--iverilog',required=True);ap.add_argument('--vvp',required=True);ap.add_argument('--report',required=True);args=ap.parse_args()
root=Path(__file__).resolve().parents[2];build=root/'build/memv1-tx-hold';build.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();tool=Path(args.iverilog).resolve().parent;env['PATH']=str(tool)+os.pathsep+str(tool.parent/'lib')+os.pathsep+env['PATH']
vec=build/'vectors.hex';subprocess.run([sys.executable,str(root/'mem/tests/memv1_model.py'),'--vectors',str(vec)],check=True,env=env)
sources=[root/f'mem/rtl/{n}.v' for n in ('memv1_crc32b','mem_adapter','memv1_bridge','memv1_sys','memv1_reply_raw','mem_mailbox','mem_bist','mem_v1_core')]+[root/'link/rtl/reply_clock_filter.v',root/'link/rtl/reply_phase_delay.v',root/'mem/tests/tb_mem_v1_core.v']
results=[]
for negative in (0,1):
 image=build/f'tx5-neg{negative}.vvp'
 cmd=[args.iverilog,'-g2012','-s','tb_mem_v1_core','-Ptb_mem_v1_core.FAST_REPLY_ENABLE=1','-Ptb_mem_v1_core.REPLY_PHASE_TICKS=0','-Ptb_mem_v1_core.QUICK=2','-Ptb_mem_v1_core.TX_HALF=100.0','-Ptb_mem_v1_core.RX_HALF=100.0',f'-Ptb_mem_v1_core.TX_NEG_PREAMBLE={negative}','-o',str(image),*map(str,sources)]
 subprocess.run(cmd,check=True,env=env)
 p=subprocess.run([args.vvp,str(image),f'+VEC={vec}'],env=env,capture_output=True,text=True,timeout=90)
 expected_pass=negative==1
 if expected_pass:assert p.returncode==0 and 'checks=12' in p.stdout and 'PASS memv1 fast fullpath' in p.stdout,p.stdout+p.stderr
 else:assert p.returncode!=0 and 'FAIL case 100 status 1 want 0' in p.stdout,p.stdout+p.stderr
 print(('NEG+p1 PASS' if expected_pass else 'POS5 expected CRC failure'),p.stdout.strip(),flush=True)
 results.append({'tx_hz':5000000,'tx_negative_with_physical_preamble1':bool(negative),'rx_hz':5000000,'rx_model':'host samples old data at raw rising, not P4 IO timing qualification','passed':expected_pass,'expected_failure_control':not expected_pass,'output':p.stdout,'stderr':p.stderr,'scope':'one preamble per complete physical burst; DIR1 boundary clears partial RX; never insert a new preamble mid-WR/CANCEL'})
Path(args.report).write_text(json.dumps({'scope':'Offline SYS27 request/data-hold and complete-DIR-boundary test; not hardware/clock-jitter signoff','results':results,'sources':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},indent=2)+'\n',encoding='utf-8')
