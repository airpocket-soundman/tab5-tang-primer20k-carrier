from pathlib import Path
import json,sys,hashlib
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';sys.path.insert(0,str(H/'simulation/parallel'))
from run_waveforms import deck,PARAMS
data=json.loads((H/'simulation/parallel/extracted-paths.json').read_text())['spark-lite-a'];cases=[]
for freq in (1000000,10000000,20000000,40000000):
 period=1/freq
 for corner in ('fast','slow'):
  for direction in ('write','read'):
   p=dict(PARAMS[corner],cio=(3.467e-12 if corner=='fast' else 11e-12));lines,recv=deck(data['signals']['CLK'],p,direction,680,period,3)
   lines=[l if not l.startswith('.tran') else f'.tran 100p {3*period+10e-9} 0 100p' for l in lines];text='\n'.join(lines)+'\n';thresholds=(2.,.8) if direction=='write' else (.75*3.465,.25*3.135)
   cases.append({'name':f'periodic-{freq}-{corner}-{direction}','netlist':text,'analysis':{'kind':'periodic','freq_Hz':freq,'corner':corner,'direction':direction,'receiver':recv,'period':period,'thresholds':thresholds},'source':{'netlist_sha256':hashlib.sha256(text.encode()).hexdigest(),'pcb_normalized_sha256':data['sourcePCBhash'],'scope':'Identical periodic_link.py model/thresholds; not RTL/DMA proof'}})
(W/'periodic-input.json').write_text(json.dumps({'cases':cases},indent=2)+'\n');print('Prepared',len(cases),'periodic cases')
