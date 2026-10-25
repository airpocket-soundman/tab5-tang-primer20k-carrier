from pathlib import Path
import concurrent.futures as cf
import subprocess,sys,json,time
import hashlib
from power_models import make
H=Path(__file__).resolve().parent
names=json.loads((H/'cases/index.json').read_text())
if '--extras' in sys.argv:names=list(json.loads((H/'cases/extra-cases.json').read_text()))
if '--average-only' in sys.argv:names=[n for n in names if 'vendor' not in n]
if '--stale-only' in sys.argv:
 def stale(n):
  p=H/'results'/(n+'.json')
  if not p.exists():return True
  d=json.loads(p.read_text());c=json.loads((H/'cases'/(n+'.json')).read_text())
  return not d.get('complete') or d.get('deck_sha256')!=hashlib.sha256(('\n'.join(make(c))+'\n').encode()).hexdigest()
 names=[n for n in names if stale(n)]
def run(n):
 p=H/'cases'/(n+'.json');raw=Path('D:/tmp/carrier-power-transient');raw.mkdir(exist_ok=True)
 with (raw/(n+'.driver.log')).open('w') as f:
  try:
   r=subprocess.run([sys.executable,str(H/'simulate_case.py'),str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=100 if 'vendor' not in n else 1500)
   result={'name':n,'process_returncode':r.returncode}
   if (H/'results'/(n+'.json')).exists():result['complete']=json.loads((H/'results'/(n+'.json')).read_text()).get('complete',False)
  except subprocess.TimeoutExpired:result={'name':n,'status':'timeout','complete':False}
 print(json.dumps(result),flush=True);return result
start=time.time()
with cf.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,names))
(H/'results/suite-execution.json').write_text(json.dumps({'runtime_s':time.time()-start,'cases':results},indent=2)+'\n')
