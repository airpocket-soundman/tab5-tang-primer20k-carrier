from pathlib import Path
import sys,json,hashlib
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';sys.path.insert(0,str(H/'simulation/parallel'))
from run_waveforms import deck,PARAMS
data=json.loads((H/'simulation/parallel/extracted-paths.json').read_text())['spark-full-pcba']
corners={'fast_IBIS_min':dict(PARAMS['fast'],cio=3.062e-12),'fast_IBIS_typ':dict(PARAMS['fast'],cio=3.467e-12),'fast_IBIS_max':dict(PARAMS['fast'],cio=4.473e-12),'controlled_IBIS':dict(PARAMS['controlled'],cio=3.467e-12),'slow_Cio_bound':dict(PARAMS['slow'],cio=11e-12)}
cases=[]
for sig,g in data['signals'].items():
 for corner,p in corners.items():
  for direction in ('write','read'):
   lines,recv=deck(g,p,direction,680,10e-6,1);source='host' if direction=='write' else 'core'
   lines=[l for l in lines if not l.startswith('.save')];lines=[l if not l.startswith('.tran') else '.tran 20p 220n 0 20p' for l in lines]
   saved={'GPIO_receiver':recv,'GPIO_driver_pad':source,'switch_host_pin':'swa0','switch_core_pin':'swb0'}
   lines.insert(-1,'.save '+' '.join('v('+v+')' for v in saved.values()));text='\n'.join(lines)+'\n'
   cases.append({'name':'link-'+sig+'-'+corner+'-'+direction,'netlist':text,'analysis':{'signal':sig,'corner':corner,'direction':direction,'vdd':p['vdd'],'saved':saved},'source':{'netlist_sha256':hashlib.sha256(text.encode()).hexdigest(),'pcb_normalized_sha256':data['sourcePCBhash'],'scope':'Identical run_final_selected.py model construction; no physical validation'}})
(W/'parallel-input.json').write_text(json.dumps({'cases':cases},indent=2)+'\n');print('Prepared',len(cases),'parallel cases')
