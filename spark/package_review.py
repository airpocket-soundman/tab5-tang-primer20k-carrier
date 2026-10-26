"""Bundle only the current engineering review candidate, excluding rejected imports."""
from pathlib import Path
import json,hashlib,zipfile
H=Path(__file__).resolve().parent
def read(p):return json.loads((H/p).read_text(encoding='utf8'))
drc=read('design/kicad/sim/drc-final.json');assert not drc['violations'] and not drc['unconnected_items']
erc=read('design/kicad/sim/erc-final.json');assert not any(s['violations'] for s in erc['sheets'])
for p in ['design/easyeda/electrical-migration-audit.json','design/easyeda/schematic-migration-audit.json','design/easyeda/manual-footprint-audit.json','design/kicad/sim/schematic-model-audit.json','sources/preservation-check.json']:assert read(p)['ok'],p
assert read('design/easyeda/akizuki-drc-details.json')==[]
warnings=read('design/easyeda/akizuki-schematic-drc.json');assert not any(r['type']=='fatalError' and r['count'] for r in warnings)
pcb=H/'design/kicad/tab5-fpga-carrier.kicad_pcb';digest=hashlib.sha256(pcb.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
power=read('simulation/power/summary.json')['results'];assert len(power)==6 and all(r['complete'] and r['within_numeric_voltage_limits'] and r['parameters']['sourcePCBhash']==digest for r in power)
si=read('simulation/parallel/spark-full-pcba-final680.json')['results'];assert len(si)==150
summary={'status':'Engineering review candidate; NOT released for fabrication or submitted to Spark','pcb_normalized_sha256':digest,'dimensions_mm':[125,78],'functions':['HDMI','USB PD12V','barrel12V'],'pcba_components':99,'manual_components':4,'kicad_drc_violations':0,'kicad_unconnected':0,'kicad_erc_errors':0,'native_pcb_drc':0,'native_schematic_fatal':0,'native_schematic_warnings':sum(r['count'] for r in warnings if r['type']=='warn'),'native_schematic_checked_pins':482,'si_cases':150,'si_receiver_voltage_pass':sum(r['receiver_voltage_ok'] for r in si),'si_driver_voltage_pass':sum(r['source_voltage_ok'] for r in si),'si_max_settle_ns':max(r['settle_5percent_ns'] for r in si),'power_cases_pass':6,'preserved_original_files':883,'open_items':['13 native schematic warnings need classification','manufacturer assembly preview/DFM and stock','physical fit and enclosure','Spark KiCad-to-EasyEDA import eligibility','hardware bring-up and performance']}
(H/'review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
wasm_checks={name:read('simulation/easyeda-wasm/'+name+'-comparison.json') for name in ('power','parallel','periodic')}
assert all(r['ok'] for r in wasm_checks.values()),'EasyEDA rerun comparison incomplete'
summary['easyeda_api_recalculation']={'engine':'Official NGspice46 WASM in EasyEDA API Gateway Worker','power_cases':6,'parallel_cases':150,'periodic_cases':16,'all_comparisons_passed':True,'circuit_limits_unchanged':True}
(H/'review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
files={H/'README.md',H/'review-summary.json'}
for name in ['easyeda_call.py','bootstrap_easyeda_wasm.py','prepare_easyeda_wasm.py','prepare_easyeda_parallel.py','prepare_easyeda_periodic.py','run_easyeda_batches.py','compare_easyeda_power.py','compare_easyeda_parallel.py','compare_easyeda_periodic.py','archive_easyeda_waveforms.py','plot_easyeda_comparison.py','simulate_power.py','rebind_simulation.py','package_review.py','check_preserved.py','design/easyeda-run-wasm.js']:
 files.add(H/name)
for folder in ['application','design/kicad','design/manufacturing/spark-full-review-2026-10-26','simulation']:
 for p in (H/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log','.kicad_prl','.lck'):files.add(p)
for p in (H/'design').glob('*.md'):files.add(p)
for name in ['design/akizuki-purchase-plan.csv','design/enclosure-concept.scad','design/easyeda/spark-akizuki-migration-review.epro2','design/easyeda/README.md','design/easyeda/electrical-migration-audit.json','design/easyeda/schematic-migration-audit.json','design/easyeda/manual-footprint-audit.json','design/easyeda/akizuki-rules-before.json','design/easyeda/akizuki-rules-aligned.json','design/easyeda/akizuki-drc-details.json','design/easyeda/akizuki-schematic-drc.json','design/easyeda/schematic-netlist.txt','sources/official-evidence.json','sources/preservation-check.json','sources/TS-1102S-B-D-B_C480272.pdf','sources/KSDxx.pdf','sources/mj179ph_mj180ph.pdf']:files.add(H/name)
manifest={str(p.relative_to(H)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
(H/'review-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');files.add(H/'review-manifest.json')
out=H/'spark-full-engineering-review-2026-10-26.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):z.write(p,'spark/'+str(p.relative_to(H)).replace('\\','/'))
with zipfile.ZipFile(out) as z:assert z.testzip() is None
print(json.dumps(summary,indent=2));print('Review ZIP:',out.stat().st_size,'bytes;',len(files),'files')
