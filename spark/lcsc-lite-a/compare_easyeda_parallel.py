"""Compare captured EasyEDA calculations to the previous 150-case run."""
from pathlib import Path
import json
from collections import Counter
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm'
old=json.loads((H/'simulation/parallel/spark-lite-a-final680.json').read_text())['results'];key=lambda r:(r['signal'],r['corner'],r['direction']);baseline={key(r):r for r in old}
rows=[]
for p in sorted((W/'results').glob('link-*.json')):
 d=json.loads(p.read_text());r=d['summary'];b=baseline[key(r)]
 delta=max(abs(r['pin_extrema_V'][port][field]-b['pin_extrema_V'][port][field]) for port in b['pin_extrema_V'] for field in b['pin_extrema_V'][port])
 flags=('receiver_voltage_ok','source_voltage_ok','switch_design_envelope_ok');same=all(r[f]==b[f] for f in flags)
 rows.append({**r,'engine_ok':d['ok'],'max_extrema_delta_V':delta,'settle_delta_ns':r['settle_5percent_ns']-b['settle_5percent_ns'],'classification_matches':same,'comparison_ok':bool(d['ok'] and delta<=.025 and abs(r['settle_5percent_ns']-b['settle_5percent_ns'])<=1 and same)})
out={'ok':len(rows)==150 and all(r['comparison_ok'] for r in rows),'completed':len(rows),'expected':150,'receiver_voltage_pass':sum(r['receiver_voltage_ok'] for r in rows),'source_voltage_pass':sum(r['source_voltage_ok'] for r in rows),'classification_matches':sum(r['classification_matches'] for r in rows),'max_extrema_delta_V':max((r['max_extrema_delta_V'] for r in rows),default=0),'max_abs_settle_delta_ns':max((abs(r['settle_delta_ns']) for r in rows),default=0),'max_settle_ns':max((r['settle_5percent_ns'] for r in rows),default=0),'tolerance':{'voltage_V':.025,'settling_ns':1,'all_classifications_must_match':True},'results':rows,'scope':'Genuine recalculations in official NGspice46 WASM inside EasyEDA. Same linear RLC/fixedRon/IBIS-derived capacitance model; no new hardware validation.'}
(W/'parallel-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='results'},indent=2));raise SystemExit(0 if out['ok'] else 1)
