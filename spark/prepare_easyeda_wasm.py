from pathlib import Path
import json,hashlib,re
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';W.mkdir(exist_ok=True);(W/'results').mkdir(exist_ok=True)
runtime=Path('D:/tmp/easyeda-ngspice-wasm');sha=(runtime/'source-commit.txt').read_text(encoding='utf-8-sig').strip()
manifest={'repository':'https://github.com/easyeda/eext-simulation-with-ngspice','commit':sha,'runtime_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.iterdir() if p.name in ['ngspice.js','ngspice.wasm','ngspice-xspice-codemodels.js','NGSPICE-COPYING.txt','NGSPICE-AUTHORS.txt']},'execution':'Unmodified official NGspice46 WASM executed inside EasyEDA through API Gateway. No GUI automation, no external Python/ngspice calculation as substitute.'}
(W/'runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
cases=[]
for p in sorted((H/'simulation/power/models').glob('spark-*.cir')):
 source=p.read_text(encoding='utf8');text=source
 for name in re.findall(r'^\.include\s+"([^"]+)"',text,re.M|re.I):
  included=Path(name);text=text.replace('.include "'+name+'"','* BEGIN inlined '+included.name+'\n'+included.read_text(encoding='cp1252')+'\n* END inlined '+included.name)
 cases.append({'name':p.stem,'netlist':text,'compatMode':'psa','source':{'original_deck_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'inlined_deck_sha256':hashlib.sha256(text.encode()).hexdigest(),'path':str(p.relative_to(H)),'only_transformation':'Inline existing .include with cp1252 comments decoded; circuit equations and analysis unchanged. psa applies PSpice parsing to the inlined library, equivalent in scope to the original ps+include path.'}})
(W/'power-input.json').write_text(json.dumps({'cases':cases},indent=2)+'\n')
(W/'active-input.json').write_text(json.dumps({'cases':cases[:1]},indent=2)+'\n')
print('Prepared',len(cases),'power cases; first case:',cases[0]['name'])
