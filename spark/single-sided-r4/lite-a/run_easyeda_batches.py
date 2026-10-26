"""Sequential API orchestration only; the solver executes inside EasyEDA."""
from pathlib import Path
import json,subprocess,sys,argparse
parser=argparse.ArgumentParser();parser.add_argument('kind',nargs='?',choices=['power','parallel','periodic','hdmi'],default='parallel');parser.add_argument('--force',action='store_true');args=parser.parse_args()
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';kind=args.kind;cases=json.loads((W/(kind+'-input.json')).read_text())['cases']
pending=[]
for c in cases:
 p=W/'results'/(c['name']+'.json')
 if p.exists() and not args.force:
  old=json.loads(p.read_text())
  if old.get('ok') and old.get('source')==c['source']:continue
 pending.append(c)
batch_size=1 if kind in ('periodic','hdmi') else 3 if kind=='power' else 10
for start in range(0,len(pending),batch_size):
 batch=pending[start:start+batch_size];(W/'active-input.json').write_text(json.dumps({'cases':batch})+'\n')
 record=W/(kind+'-api-batch-'+str(start//batch_size+1).zfill(2)+'.json')
 run=subprocess.run([sys.executable,'-X','utf8',str(H/'easyeda_call.py'),str(H/'design/easyeda-run-wasm.js'),str(record)],capture_output=True,text=True,encoding='utf8')
 if run.returncode:raise RuntimeError(run.stdout[-1000:]+run.stderr[-1000:])
 response=json.loads(record.read_text())
 if not response['result']['allPassed']:raise RuntimeError(response)
 print('EasyEDA solved',len(cases)-len(pending)+min(start+len(batch),len(pending)),'/',len(cases),'last',batch[-1]['name'],flush=True)
print('All cases completed in EasyEDA API Gateway workers',flush=True)
