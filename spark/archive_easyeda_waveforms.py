"""Keep large genuine raw outputs outside Git and retain hashes/compact CSV."""
from pathlib import Path
import json,hashlib
import numpy as np
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';rawdir=Path('D:/tmp/easyeda-ngspice-wasm/raw');rawdir.mkdir(exist_ok=True)
for p in (W/'results').glob('spark-*.json'):
 d=json.loads(p.read_text())
 if 'raw' in d:
  text=d.pop('raw');raw=rawdir/p.name;raw.write_text(text,encoding='utf8');d['rawPath']=str(raw)
 else:raw=Path(d['rawPath']);text=raw.read_text(encoding='utf8')
 d['raw_sha256']=hashlib.sha256(text.encode()).hexdigest();parsed=json.loads(text);d['diagnostics']=parsed['diagnostics'];p.write_text(json.dumps(d,indent=2)+'\n')
 plot=next(x for x in parsed['plots'] if x['name'].startswith('tran'));v={x['name']:np.asarray(x['real']) for x in plot['vectors']};names=['time']+[n for n in v if n!='time'];ix=np.unique(np.linspace(0,len(v['time'])-1,4000).astype(int))
 np.savetxt(W/'results'/(p.stem+'.csv'),np.column_stack([v[n][ix] for n in names]),delimiter=',',header=','.join(names),comments='')
manifest={}
for p in (W/'results').glob('*.json'):
 d=json.loads(p.read_text())
 if 'rawPath' in d:
  raw=Path(d['rawPath']);manifest[p.stem]={'path':str(raw),'bytes':raw.stat().st_size,'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'export_sampling':d.get('exportSampling','adaptive solver output')}
(W/'raw-waveform-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Archived genuine raw outputs:',len(manifest))
