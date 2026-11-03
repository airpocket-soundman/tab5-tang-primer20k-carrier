"""Independent-shim tests only; does not invoke programmer or physical DDR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--iverilog',default='iverilog')
p.add_argument('--vvp',default='vvp')
args=p.parse_args()
root=Path(__file__).resolve().parents[2]
build=root/'build/mem-tests'
build.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
tool=Path(args.iverilog).resolve().parent
env['PATH']=str(tool)+os.pathsep+str(tool.parent/'lib')+os.pathsep+env['PATH']
results=[]
for name in ('mem_bist','mem_mailbox','mem_link'):
    sources=[root/f'mem/rtl/{name}.v',root/f'mem/tests/tb_{name}.v']
    image=build/f'{name}.vvp'
    subprocess.run([args.iverilog,'-g2012','-s',f'tb_{name}','-o',str(image),*map(str,sources)],check=True,env=env)
    completed=subprocess.run([args.vvp,str(image)],capture_output=True,text=True,check=True,env=env)
    if 'PASS ' not in completed.stdout:
        raise RuntimeError(completed.stdout+completed.stderr)
    print(completed.stdout.strip())
    results.append({'name':name,'output':completed.stdout.strip(),
                    'sources':{str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}})
report={'scope':'RTL simulations, not physical DDR proof','tests':results}
(build/'results.json').write_text(json.dumps(report,indent=2)+'\n')
