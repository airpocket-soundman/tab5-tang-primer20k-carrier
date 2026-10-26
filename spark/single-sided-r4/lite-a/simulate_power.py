from pathlib import Path
import json,sys,hashlib
H=Path(__file__).resolve().parent;P=H/'simulation/power';sys.path.insert(0,str(P))
from simulate_case import run
source=H.parents[1]/'tab5-tang-primer20k-carrier-audit-pages/variants/simulation/power/cases'
source=Path('D:/github/airpocket-soundman/tab5-tang-primer20k-carrier-audit-pages/variants/simulation/power/cases')
sha=hashlib.sha256((H/'design/kicad/tab5-fpga-carrier.kicad_pcb').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
dc=json.loads((H/'design/kicad/sim/power_dc_check.json').read_text());results=[]
for p in sorted(source.glob('lite-a-dual-*.json')):
 c=json.loads(p.read_text())
 if c.get('switch_off'):continue
 if c.get('model')=='vendor' or c.get('stop',.045)>.06 or c.get('kind') in ['drop','reverse']:continue
 c['name']=c['name'].replace('lite-a-dual','spark-lite-a');c['variant']='spark-lite-a';c['source_pcb_sha256']=sha
 c['path_R']=max(dc['path_resistance_ohm'].values())*((1+.00393*65) if c.get('temp')==50 or 'one-amp' in c['name'] else 1)
 (P/'cases'/(c['name']+'.json')).write_text(json.dumps(c,indent=2)+'\n');results.append(run(c))
(P/'summary.json').write_text(json.dumps({'results':results,'scope':'A-type averaged5V controller and fitted XC6206 dynamic model; includes normal cases and explicit out-of-envelope stress sensitivities. Excludes long brownout/reverse-input and vendor switching models. Not physical validation.'},indent=2)+'\n')
print('Power cases',len(results),'voltage pass',sum(r['within_numeric_voltage_limits'] for r in results))
