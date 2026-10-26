"""Postprocess genuine EasyEDA-worker output; performs no SPICE calculation."""
from pathlib import Path
import json,re
import numpy as np
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm'
baseline={r['name']:r for r in json.loads((H/'simulation/power/summary.json').read_text())['results']}
rows=[]
for name,b in baseline.items():
 d=json.loads((W/'results'/(name+'.json')).read_text());assert d['ok'],name
 raw=json.loads(d['raw']) if 'raw' in d else json.loads(Path(d['rawPath']).read_text());plot=next(p for p in raw['plots'] if p['name'].startswith('tran'))
 v={n['name']:np.array(n['real']) for n in plot['vectors']};t=v['time'];c=b['parameters']
 deck=(H/'simulation/power/models'/(name+'.cir')).read_text()
 source=next(l for l in deck.splitlines() if l.startswith('Vsource '))
 def value(s):
  return float(s[:-1])*{'m':1e-3,'u':1e-6,'n':1e-9}[s[-1]] if s[-1] in 'mun' else float(s)
 pts=list(map(value,source.split('PWL(')[1].split(')')[0].split()))
 supply=np.interp(t,pts[::2],pts[1::2]);valid=(t>=c['settled_start'])&(supply>=11.4-1e-4)&(supply<=12.6+1e-4)
 assert valid.any() and t[-1]>=c['stop']*.999
 metrics={'vcore_min_valid_input_V':float(v['vcore'][valid].min()),'vcore_max_valid_input_V':float(v['vcore'][valid].max()),'vout_max_V':float(v['vout'].max())}
 deltas={k:metrics[k]-b[k] for k in metrics}
 original=np.load(b['raw_path']);grid=np.linspace(c['settled_start'],c['stop'],5001)
 difference=np.interp(grid,t,v['vcore'])-np.interp(grid,original['time'],original['v(vcore)'])
 rows.append({'name':name,'samples':len(t),**metrics,'within_4p5_to_5p5V':metrics['vcore_min_valid_input_V']>=4.5 and metrics['vcore_max_valid_input_V']<=5.5,'delta_vs_previous_V':deltas,'max_sampled_core_waveform_delta_V':float(abs(difference).max()),'engine_agreement_within_25mV':bool(max(abs(x) for x in deltas.values())<=.025 and abs(difference).max()<=.025),'diagnostics':raw['diagnostics']})
out={'ok':all(r['within_4p5_to_5p5V'] and r['engine_agreement_within_25mV'] for r in rows),'cases':rows,'agreement_tolerance_V':.025,'scope':'Same averaged5V cases rerun with official NGspice46 WASM in EasyEDA API Gateway. Postprocessing only in Python; excludes TLV1117/PD negotiation/thermal/hardware.'}
(W/'power-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));raise SystemExit(0 if out['ok'] else 1)
