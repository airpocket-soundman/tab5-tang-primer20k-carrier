from pathlib import Path
import json
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';key=lambda r:(r['freq_Hz'],r['corner'],r['direction'])
baseline={key(r):r for r in json.loads((H/'simulation/parallel/periodic-results.json').read_text())['results']};rows=[]
for p in sorted((W/'results').glob('periodic-*.json')):
 d=json.loads(p.read_text());r=d['summary'];b=baseline[key(r)];delta=max(abs(r[k]-b[k]) for k in ('sample_high_min_V','sample_low_max_V'))
 rows.append({**r,'engine_ok':d['ok'],'sample_max_delta_V':delta,'classification_matches':r['threshold_ok']==b['threshold_ok'],'comparison_ok':d['ok'] and delta<=.025 and r['threshold_ok']==b['threshold_ok']})
out={'ok':len(rows)==16 and all(r['comparison_ok'] for r in rows),'completed':len(rows),'expected':16,'max_sample_delta_V':max((r['sample_max_delta_V'] for r in rows),default=0),'classification_matches':sum(r['classification_matches'] for r in rows),'at_1MHz_pass':sum(r['threshold_ok'] for r in rows if r['freq_Hz']==1000000),'results':rows,'scope':'Same periodic physical-line model; official NGspice46 WASM rerun in EasyEDA. No RTL/DMA or achieved application throughput claim.'}
(W/'periodic-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='results'},indent=2));raise SystemExit(0 if out['ok'] else 1)
