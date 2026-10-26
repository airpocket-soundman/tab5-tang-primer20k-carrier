"""Postprocess actual EasyEDA engine waveforms; no circuit solver is used here."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
from run_hdmi import metrics
v=sys.argv[1];root=H/v;W=root/'simulation/easyeda-wasm'
inputs=json.loads((W/'hdmi-input.json').read_text())['cases'];baseline={x['name']:x for x in json.loads((root/'simulation/hdmi/summary.json').read_text())['cases']}
rows=[]
for case in inputs:
    name=case['name'];d=json.loads((W/'results'/(name+'.json')).read_text());assert d['ok'] and d['source']==case['source']
    rawpath=Path(d['rawPath']);raw=json.loads(rawpath.read_text(encoding='utf8'));assert not raw['diagnostics']['errors']
    plot=next(p for p in raw['plots'] if p['name'].startswith('tran'));vv={x['name'].lower():np.asarray(x['real']) for x in plot['vectors']}
    a=case['analysis'];t=vv['time'];assert t[-1]>=129*a['bit_period_s']*.9999
    m=metrics(t,vv['rx_diff'],vv['rx_p'],vv['rx_n'],a)
    original=np.load(baseline[name]['raw_path']);grid=np.linspace(20*a['bit_period_s'],127*a['bit_period_s'],10001)
    delta=float(abs(np.interp(grid,t,vv['rx_diff'])-np.interp(grid,original['time'],original['diff'])).max())
    assert m['engineering_criteria_ok']==baseline[name]['engineering_criteria_ok'] and delta<.01,(name,delta)
    rows.append({'name':name,'conditions':a,**m,'max_waveform_delta_V':delta,'classification_matches':True,'raw_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'engine':d['engine'],'executionProjectUuid':d['executionProjectUuid']})
report={'ok':True,'completed':len(rows),'engineering_pass':sum(x['engineering_criteria_ok'] for x in rows),'max_waveform_delta_V':max(x['max_waveform_delta_V'] for x in rows),'cases':rows,'scope':'Real NGspice46 WASM calculation inside EasyEDA. Analytical driver,line and receiver assumptions.100mV decision and0.4UI window are engineering criteria,not an HDMI compliance mask.'}
(W/'hdmi-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
