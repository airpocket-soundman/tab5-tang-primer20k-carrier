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
build=root/'build/mem-tests'
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
    cone=root/'build/mem-clock-cone'
    sources=[cone/'tb_vendor_init.v',cone/'MemClockCone.v',Path(args.primitive_lib)]
    image=cone/'test.vvp'
    subprocess.run([args.iverilog,'-g2012','-s','tb_vendor_init','-o',str(image),*map(str,sources)],check=True,env=env,timeout=30)
    completed=subprocess.run([args.vvp,'-i',str(image)],capture_output=True,text=True,check=True,env=env,timeout=60)
    if 'PASS vendor initialization model' not in completed.stdout:raise RuntimeError(completed.stdout)
    print(completed.stdout.strip())
    results.append({'name':'vendor_clock_init_cone','scope':'pre-calibration clock cone only; no DRAM/full calibration proof',
                    'output':completed.stdout.strip(),'projection':json.loads((cone/'projection.json').read_text()),
                    'sources':{str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
report={'scope':'RTL simulations, not physical DDR proof','tests':results}
(build/'results.json').write_text(json.dumps(report,indent=2)+'\n')

