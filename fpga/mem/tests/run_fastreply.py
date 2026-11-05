"""Offline MEMV1 full-path frequency checks; never opens a device."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--iverilog',default='iverilog');ap.add_argument('--vvp',default='vvp');ap.add_argument('--report');ap.add_argument('--quick',action='store_true');ap.add_argument('--full-regression',action='store_true');ap.add_argument('--tx-mhz',type=float,default=2);ap.add_argument('--sample-offset-ns',type=float,default=0);ap.add_argument('--phase-ticks',type=int,choices=(0,3),default=0);args=ap.parse_args()
root=Path(__file__).resolve().parents[2];build=root/f'build/memv1-fast-tests-phase{args.phase_ticks}';build.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();td=Path(args.iverilog).resolve().parent;env['PATH']=str(td)+os.pathsep+str(td.parent/'lib')+os.pathsep+env['PATH']
vectors=build/'vectors.hex';subprocess.run([sys.executable,str(root/'mem/tests/memv1_model.py'),'--vectors',str(vectors)],check=True,env=env)
sources=[root/f'mem/rtl/{n}.v' for n in ('memv1_crc32b','mem_adapter','memv1_bridge','memv1_sys','memv1_reply_raw','mem_mailbox','mem_bist','mem_v1_core')]+[root/'link/rtl/reply_clock_filter.v',root/'link/rtl/reply_phase_delay.v',root/'mem/tests/tb_mem_v1_core.v']
initial_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+[root/'mem/tests/tb_memv1_fast_fault.v']}
results=[]
conditions=[(20,args.tx_mhz,0)] if args.quick or args.full_regression else [(hz,args.tx_mhz,phase) for hz in (5,8,10,16,20) for phase in (0,12,24)]
for hz,tx,phase in conditions:
 image=build/f'full-{hz}-{tx}-{phase}-{args.sample_offset_ns}-{int(args.full_regression)}.vvp'
 command=[args.iverilog,'-g2012','-s','tb_mem_v1_core','-Ptb_mem_v1_core.FAST_REPLY_ENABLE=1',f'-Ptb_mem_v1_core.REPLY_PHASE_TICKS={args.phase_ticks}',f'-Ptb_mem_v1_core.QUICK={0 if args.full_regression else 2}',f'-Ptb_mem_v1_core.RX_HALF={500/hz}',f'-Ptb_mem_v1_core.TX_HALF={500/tx}',f'-Ptb_mem_v1_core.SYS_PHASE={phase}',f'-Ptb_mem_v1_core.DATA_DELAY={phase/4}',f'-Ptb_mem_v1_core.SAMPLE_OFFSET={args.sample_offset_ns}','-o',str(image),*map(str,sources)]
 subprocess.run(command,check=True,env=env)
 r=subprocess.run([args.vvp,str(image),f'+VEC={vectors}'],env=env,capture_output=True,text=True,timeout=180)
 print(r.stdout.strip(),flush=True)
 if r.returncode or ('PASS mem_v1_core' if args.full_regression else 'PASS memv1 fast fullpath') not in r.stdout:raise RuntimeError(r.stdout+r.stderr)
 results.append({'rx_mhz':hz,'tx_mhz':tx,'reply_phase_ticks':args.phase_ticks,'sys_phase_ns':phase,'output_delay_ns':phase/4,'sample_offset_ns':args.sample_offset_ns,'full_regression':args.full_regression,'output':[l for l in r.stdout.splitlines() if l.startswith('PASS')]})
fault_source=root/'mem/tests/tb_memv1_fast_fault.v'
fault_image=build/'fault.vvp'
subprocess.run([args.iverilog,'-g2012','-s','tb_memv1_fast_fault',f'-Ptb_memv1_fast_fault.REPLY_PHASE_TICKS={args.phase_ticks}','-o',str(fault_image),*map(str,sources[:-1]),str(fault_source)],check=True,env=env)
fault=subprocess.run([args.vvp,str(fault_image)],check=True,env=env,capture_output=True,text=True,timeout=30)
if 'PASS memv1 fast fault' not in fault.stdout:raise RuntimeError(fault.stdout+fault.stderr)
print(fault.stdout.strip(),flush=True)
results.append({'control_fault_test':True,'output':fault.stdout.strip()})
sources.append(fault_source)
assert initial_hashes=={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'Sources changed during simulation; discard mixed-version results'
report={'scope':'RTL full path with independent native controller model; host samples at raw rising edge plus specified offset; not P4 NEG/POS qualification or physical timing/DDR proof','results':results,'sources':initial_hashes}
if args.report:Path(args.report).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
