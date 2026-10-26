"""Fetch only hash-pinned official engine assets; no client installation/update."""
from pathlib import Path
import json,hashlib,urllib.request,concurrent.futures
H=Path(__file__).resolve().parent;manifest=json.loads((H/'simulation/easyeda-wasm/runtime-manifest.json').read_text());out=Path('D:/tmp/easyeda-ngspice-wasm');out.mkdir(exist_ok=True);(out/'raw').mkdir(exist_ok=True)
def fetch(item):
 name,digest=item;p=out/name
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
  url='https://raw.githubusercontent.com/easyeda/eext-simulation-with-ngspice/'+manifest['commit']+'/iframe/wasm/'+name
  with urllib.request.urlopen(url,timeout=60) as r:data=r.read()
  assert hashlib.sha256(data).hexdigest()==digest,(name,'hash mismatch');p.write_bytes(data)
 return name
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:print('Verified:',list(pool.map(fetch,manifest['runtime_files'].items())))
(out/'source-commit.txt').write_text(manifest['commit']+'\n')
