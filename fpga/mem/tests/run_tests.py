"""Independent-shim tests only; does not invoke programmer or physical DDR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser()
p.add_argument('--iverilog',default='iverilog')
p.add_argument('--vvp',default='vvp')
p.add_argument('--primitive-lib',help='Optional official GW2A prim_sim.v for clock-init cone audit')
p.add_argument('--zig',help='Optional Zig executable for portable C codec checks')
args=p.parse_args()
root=Path(__file__).resolve().parents[2]
import os
SFX=('-'+os.environ['MEM_IP_TAG']) if os.environ.get('MEM_IP_TAG') else ''
build=root/f'build/mem-tests{SFX}'
build.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
tool=Path(args.iverilog).resolve().parent
env['PATH']=str(tool)+os.pathsep+str(tool.parent/'lib')+os.pathsep+env['PATH']
results=[]
cases={'mem_deep_monitor':['mem_deep_monitor'],'mem_bist':['mem_bist'],'mem_mailbox':['mem_mailbox'],'mem_link':['mem_link'],
       'mem_heartbeat_abort':['mem_bist','mem_mailbox']}
for name,modules in cases.items():
    sources=[root/f'mem/rtl/{module}.v' for module in modules]+[root/f'mem/tests/tb_{name}.v']
    image=build/f'{name}.vvp'
    subprocess.run([args.iverilog,'-g2012','-s',f'tb_{name}','-o',str(image),*map(str,sources)],check=True,env=env)
    completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
    if 'PASS ' not in completed.stdout:
        raise RuntimeError(completed.stdout+completed.stderr)
    print(completed.stdout.strip())
    results.append({'name':name,'output':completed.stdout.strip(),
                    'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
if args.zig:
    executable=build/'test_mem_protocol.exe'
    source=root/'mem/tests/test_mem_protocol.c'
    subprocess.run([args.zig,'cc','-std=c99','-Wall','-Wextra','-Werror',str(source),'-o',str(executable)],check=True,timeout=60)
    completed=subprocess.run([str(executable)],capture_output=True,text=True,check=True,timeout=10)
    if 'PASS mem_protocol 622 checks' not in completed.stdout:raise RuntimeError(completed.stdout)
    print(completed.stdout.strip())
    sources=[source,root/'host/mem_protocol.h',root/'host/link_protocol.h']
    results.append({'name':'mem_protocol_c','output':completed.stdout.strip(),
                    'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
if args.primitive_lib:
    subprocess.run([sys.executable,str(root/'mem/tests/project_vendor_clock_cone.py')],check=True)
    cone=root/f'build/mem-clock-cone{SFX}'
    sources=[cone/'tb_vendor_init.v',cone/'MemClockCone.v',Path(args.primitive_lib)]
    image=cone/'test.vvp'
    subprocess.run([args.iverilog,'-g2012','-s','tb_vendor_init','-o',str(image),*map(str,sources)],check=True,env=env,timeout=30)
    completed=subprocess.run([args.vvp,'-i',str(image)],capture_output=True,text=True,check=True,env=env,timeout=60)
    if 'PASS vendor initialization model' not in completed.stdout:raise RuntimeError(completed.stdout)
    print(completed.stdout.strip())
    results.append({'name':'vendor_clock_init_cone','scope':'pre-calibration clock cone only; no DRAM/full calibration proof',
                    'output':completed.stdout.strip(),'projection':json.loads((cone/'projection.json').read_text()),
                    'sources':{str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
# Same bench with the vendor-conformant paired write issue (IPUG281 4.4.6).
sources=[root/'mem/rtl/mem_bist.v',root/'mem/tests/tb_mem_bist.v']
image=build/'mem_bist_paired.vvp'
subprocess.run([args.iverilog,'-g2012','-s','tb_mem_bist','-Ptb_mem_bist.PAIRED=1','-o',str(image),*map(str,sources)],check=True,env=env)
completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
if 'PASS mem_bist paired' not in completed.stdout:
    raise RuntimeError(completed.stdout+completed.stderr)
print(completed.stdout.strip())
results.append({'name':'mem_bist_paired','output':completed.stdout.strip(),
                'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
report={'scope':'RTL simulations, not physical DDR proof','tests':results}
sources=[root/'mem/rtl/mem_bist.v',root/'mem/rtl/mem_mailbox.v',root/'mem/tests/tb_mem_heartbeat_abort.v']
for hb_pipe in (1,2,3,4):
  image=build/f'mem_heartbeat_abort_pipe{hb_pipe}.vvp'
  subprocess.run([args.iverilog,'-g2012','-s','tb_mem_heartbeat_abort',f'-Ptb_mem_heartbeat_abort.PIPE={hb_pipe}','-o',str(image),*map(str,sources)],check=True,env=env)
  completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
  if 'PASS ' not in completed.stdout:
    raise RuntimeError(completed.stdout+completed.stderr)
  print(f'(PIPELINE={hb_pipe}) '+completed.stdout.strip())
  results.append({'name':f'mem_heartbeat_abort_pipelined{hb_pipe}','output':completed.stdout.strip(),'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
image=build/'mem_heartbeat_abort_pipe.vvp'
subprocess.run([args.iverilog,'-g2012','-s','tb_mem_heartbeat_abort','-Ptb_mem_heartbeat_abort.PIPE=1','-o',str(image),*map(str,sources)],check=True,env=env)
completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
if 'PASS ' not in completed.stdout:
    raise RuntimeError(completed.stdout+completed.stderr)
print('(PIPELINE=1) '+completed.stdout.strip())
results.append({'name':'mem_heartbeat_abort_pipelined','output':completed.stdout.strip(),
                'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
for paired,pipe in ((0,1),(1,1),(0,2),(1,2),(0,3),(1,3),(0,4),(1,4)):
    sources=[root/'mem/rtl/mem_bist.v',root/'mem/tests/tb_mem_bist.v']
    image=build/f'mem_bist_pipe{paired}_{pipe}.vvp'
    subprocess.run([args.iverilog,'-g2012','-s','tb_mem_bist',f'-Ptb_mem_bist.PAIRED={paired}',f'-Ptb_mem_bist.PIPE={pipe}','-o',str(image),*map(str,sources)],check=True,env=env)
    completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
    if 'pipelined' not in completed.stdout or 'PASS mem_bist' not in completed.stdout:
        raise RuntimeError(completed.stdout+completed.stderr)
    print(completed.stdout.strip())
    results.append({'name':f'mem_bist_pipelined{pipe}_paired{paired}','output':completed.stdout.strip(),
                    'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
sources=[root/'mem/rtl/mem_bist.v',root/'mem/tests/tb_mem_bist_rowpad.v']
image=build/'mem_bist_rowpad.vvp'
subprocess.run([args.iverilog,'-g2012','-s','tb_mem_bist_rowpad','-Ptb_mem_bist_rowpad.PIPE=1','-o',str(image),*map(str,sources)],check=True,env=env)
completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
if 'PASS mem_bist row-pad' not in completed.stdout:
    raise RuntimeError(completed.stdout+completed.stderr)
print(completed.stdout.strip())
results.append({'name':'mem_bist_rowpad','output':completed.stdout.strip(),
                'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
(build/'results.json').write_text(json.dumps(report,indent=2)+'\n')

