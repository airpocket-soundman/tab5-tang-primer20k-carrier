"""Postprocess genuine EasyEDA outputs; no circuit solving in this script."""
from pathlib import Path
import json,numpy as np
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm'
baseline=json.loads((H/'simulation/power/summary.json').read_text())['results'];rows=[]
for b in baseline:
 name=b['name'];d=json.loads((W/'results'/(name+'.json')).read_text());assert d['ok']
 raw=json.loads(d['raw']) if 'raw' in d else json.loads(Path(d['rawPath']).read_text())
 plot=next(p for p in raw['plots'] if p['name'].startswith('tran'));v={n['name']:np.array(n['real']) for n in plot['vectors']};t=v['time'];c=b['parameters']
 deck=(H/'simulation/power/models'/(name+'.cir')).read_text();source=next(l for l in deck.splitlines() if l.startswith('Vsource '))
 def value(s):return float(s[:-1])*{'m':1e-3,'u':1e-6,'n':1e-9}[s[-1]] if s[-1] in 'mun' else float(s)
 pts=list(map(value,source.split('PWL(')[1].split(')')[0].split()));supply=np.interp(t,pts[::2],pts[1::2]);valid=(t>=c.get('settled_start',.015))&(supply>=11.4-1e-4)&(supply<=12.6+1e-4)
 if c.get('switch_off'):valid&=((t<.030)|(t>.047))
 assert valid.any() and t[-1]>=c.get('stop',.045)*.999
 metrics={'vcore_min_valid_input_V':float(v['vcore'][valid].min()),'vcore_max_valid_input_V':float(v['vcore'][valid].max()),'v33_min_valid_input_V':float(v['v33raw'][valid].min()),'v33_max_valid_input_V':float(v['v33raw'][valid].max()),'vout_max_V':float(v['vout'].max())}
 delta={k:metrics[k]-b[k] for k in metrics};passed=metrics['vcore_min_valid_input_V']>=4.5 and metrics['vcore_max_valid_input_V']<=5.5 and metrics['v33_min_valid_input_V']>=3.135 and metrics['v33_max_valid_input_V']<=3.465
 rows.append({'name':name,**metrics,'within_numeric_voltage_limits':passed,'classification_matches':passed==b['within_numeric_voltage_limits'],'delta_vs_baseline_V':delta,'agreement_within_25mV':max(abs(x) for x in delta.values())<.025,'diagnostics':raw['diagnostics']})
report={'ok':all(r['classification_matches'] and r['agreement_within_25mV'] for r in rows),'cases':rows,'completed':len(rows),'voltage_pass':sum(r['within_numeric_voltage_limits'] for r in rows),'scope':'A-type averaged5V controller and fitted XC6206 transient model recalculated inside EasyEDA with official NGspice46 WASM. Includes deliberately severe load-step sensitivities; not physical qualification.'}
(W/'power-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'ok':report['ok'],'completed':len(rows),'voltage_pass':report['voltage_pass'],'max_delta_V':max(abs(x) for r in rows for x in r['delta_vs_baseline_V'].values()),'failed_cases':[r['name'] for r in rows if not r['within_numeric_voltage_limits']]},indent=2));assert report['ok']
