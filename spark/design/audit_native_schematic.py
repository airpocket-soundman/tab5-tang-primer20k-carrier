"""Compare every model pin/net and component value to the native netlist."""
from pathlib import Path
from collections import Counter
import json,sys,csv,hashlib
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'kicad/gen'));import design
P=H/'easyeda/schematic-netlist.txt';data=json.loads(P.read_text(encoding='utf8'))
native={c['props']['Designator']:c for c in data['components'].values()}
models={c.ref:c for c in design.build()};errors=[];pins=0
if native.keys()!=models.keys():errors.append({'references':list(native.keys()^models.keys())})
for ref,c in models.items():
 if ref not in native:continue
 n=native[ref];p=n['props'];actual={str(v['number']):v['net'] for v in n['pinInfoMap'].values()}
 if p['Value']!=c.value:errors.append({'ref':ref,'value':p['Value'],'expected':c.value})
 for pn,net in c.pins.items():
  if net is None:continue
  pins+=1
  if actual.get(pn)!=net:errors.append({'ref':ref,'pin':pn,'expected':net,'actual':actual.get(pn)})
 for pn,net in actual.items():
  if c.pins.get(pn) is None and net and not net.startswith('$'):
   errors.append({'ref':ref,'unexpected_connected_pin':pn,'net':net})
report={'ok':not errors,'components':len(native),'connected_pins_checked':pins,'source_pcb_sha256':hashlib.sha256((H/'kicad/tab5-fpga-carrier.kicad_pcb').read_bytes()).hexdigest(),'native_netlist_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'errors':errors,'scope':'All118 references and values, every model-connected pin net, extra/NC pin nets. J1 physical ground pad3 is a PCB-only duplicate shell contact; native symbol represents2 terminals.'}
(H/'easyeda/schematic-migration-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if report['ok'] else 1)
