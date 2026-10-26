"""Publish-selection builder: native EasyEDA files and EasyEDA-run results only.

Does not create a repository or publish remotely. Internal design/solver comparison
records remain in this workspace, outside the destination repository.
"""
from pathlib import Path
import csv,json,hashlib,shutil,re,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
assert (H/'single-sided-r4/README.md').exists()
OUT=Path('D:/github/airpocket-soundman/tab5-fpga-carrier-spark')
REPO='https://github.com/airpocket-soundman/tab5-fpga-carrier-spark'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def raw(result):return load(Path(result['rawPath']))
def vectors(result):
 plot=next(x for x in raw(result)['plots'] if x['name'].startswith('tran'))
 return {x['name']:np.asarray(x['real']) for x in plot['vectors']}
def plot_power(result,path,title,ldo=False):
 v=vectors(result);t=v['time']*1000
 fig,axes=plt.subplots(2 if ldo else 1,1,figsize=(11.2,5.8),sharex=True,squeeze=False)
 fig.patch.set_facecolor('#ffffff');ax=axes[0,0]
 ax.plot(t,v['vout'],color='#82965e',lw=1.5,label='5V regulator output');ax.plot(t,v['vcore'],color='#176b67',lw=1.65,label='Core supply')
 ax.axhspan(4.5,5.5,color='#dcecc7',alpha=.45,label='4.5–5.5V range');ax.set_ylabel('Voltage / V');ax.set_ylim(-.1,5.7);ax.legend(loc='lower right',fontsize=8,frameon=False)
 if ldo:
  a=axes[1,0];a.plot(t,v['v33raw'],color='#b77432',lw=1.5,label='Local 3.3V model');a.axhspan(3.135,3.465,color='#dcecc7',alpha=.45,label='3.3V ±5%');a.set_ylabel('Voltage / V');a.set_ylim(2.65,3.6);a.legend(loc='lower right',fontsize=8,frameon=False)
 for a in axes.flat:a.grid(alpha=.15);a.spines[['top','right']].set_visible(False);a.tick_params(labelsize=8)
 axes[-1,0].set_xlabel('Time / ms');fig.suptitle(title,fontsize=13,x=.08,ha='left');fig.text(.08,.012,'Official NGspice 46 WASM · executed inside EasyEDA Pro · analytical equivalent circuit',fontsize=8,color='#5e706d');fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(path,dpi=160);plt.close(fig)
def plot_hdmi(wasm,path,label):
 names=['hdmi-D0-742.5M-nominal-prbs7-cell2','hdmi-D0-1485M-weak_highC-prbs7-cell2']
 inputs={r['name']:r['analysis'] for r in load(wasm/'hdmi-input.json')['cases']}
 fig,axes=plt.subplots(1,2,figsize=(11.2,4.6),sharey=True)
 for ax,name in zip(axes,names):
  result=load(wasm/'results'/(name+'.json'));v=vectors(result);a=inputs[name];ui=a['bit_period_s'];phase=np.linspace(0,2,401)
  for i in range(20,124):ax.plot(phase,np.interp((i+1+phase)*ui+a['flight_delay_s'],v['time'],v['rx_diff']),color='#176b67',alpha=.18,lw=.65)
  ax.axhline(.1,color='#b77432',ls='--',lw=.8);ax.axhline(-.1,color='#b77432',ls='--',lw=.8)
  ax.set_title('D0 742.5Mb/s / nominal' if 'nominal' in name else 'D0 1485Mb/s / weak driver, high C',fontsize=10)
  ax.set_xlim(0,2);ax.set_xlabel('Time / UI');ax.grid(alpha=.15)
 axes[0].set_ylabel('Receiver differential voltage / V')
 fig.suptitle(label+' / analytical HDMI eye traces',fontsize=13)
 fig.text(.08,.015,'Actual EasyEDA NGspice46 WASM outputs. Dashed +/-100mV lines are engineering thresholds, not a compliance mask.',fontsize=8)
 fig.tight_layout(rect=[0,.05,1,.94]);fig.savefig(path,dpi=160);plt.close(fig)

project={'updated':'2026-10-26','status':'r4 single-sided SMT, SW3 omitted, J3 manually soldered. Quotation candidate; supplier acceptance and hardware validation pending.','variants':{}}
for id,folder,name,dim,count in [('full','single-sided-r4/full','spark-lcsc-priority-review.epro2',[125,78],101),('lite-a','single-sided-r4/lite-a','spark-lite-a-lcsc-review.epro2',[99,78],103)]:
 source=H/folder;design=source/'design';wasm=source/'simulation/easyeda-wasm';hardware=OUT/'hardware'/id;sim=OUT/'simulation'/id
 hardware.mkdir(parents=True,exist_ok=True);sim.mkdir(parents=True,exist_ok=True)
 obsolete=sim/'spark-lite-a-switch-cycle.csv'
 if obsolete.exists():obsolete.unlink()
 for k in ['power','parallel','periodic','hdmi']:assert load(wasm/(k+'-comparison.json'))['ok'],(id,k)
 drc=load(design/'easyeda/akizuki-drc-details.json');assert drc==[]
 sch=load(design/'easyeda/akizuki-schematic-drc.json');assert not any(r['type']=='fatalError' and r['count'] for r in sch)
 assert load(design/'easyeda/schematic-migration-audit.json')['ok']
 native=design/'easyeda'/name;shutil.copy2(native,hardware/name)
 with zipfile.ZipFile(native) as z:assert z.testzip() is None
 m=next((design/'manufacturing').glob('*single-sided-r4*'))
 for filename in ['gerbers.zip','jlc-bom.csv','jlc-cpl.csv','assembly-top.svg','assembly-bottom.svg','dnp.csv']:
  shutil.copy2(m/filename,hardware/filename)
 assert load(m/'package-check.json')['pcba_components']==count
 shutil.copy2(m/'assembly-top.svg',OUT/'docs/assets'/(id+'-assembly.svg'))
 rows=list(csv.DictReader((m/'jlc-bom.csv').open(encoding='utf8')));bom=[{'refs':r['Designator'],'value':r['Comment'],'quantity':len(r['Designator'].split(',')),'lcsc':r['LCSC Part #']} for r in rows]
 assert sum(r['quantity'] for r in bom)==count and all(r['lcsc'].startswith('C') for r in bom)
 for r in bom:r['assemblyType']='mandatory' if r['refs'] in ('J2','J4','J5') else 'tht' if r['refs'] in ('J1','JP1') else 'smt'
 assert all('J3' not in r['refs'].split(',') and 'SW3' not in r['refs'].split(',') for r in bom)
 bom.append({'refs':'J3','value':'2.54-2*15P','quantity':1,'lcsc':'C56496','assemblyType':'manual'})
 with (hardware/'bom.csv').open('w',encoding='utf8',newline='') as f:
  w=csv.writer(f);w.writerow(['References','Value','Quantity per board','LCSC','URL','Assembly'])
  for r in bom:w.writerow([r['refs'],r['value'],r['quantity'],r['lcsc'],'https://www.lcsc.com/product-detail/'+r['lcsc']+'.html',r['assemblyType']])
 # Export numerical results from the actual EasyEDA worker records, not the
 # independent solver results or comparison reports.
 executions=[];powers=[];links=[];periodic=[];hdmi=[];raw_manifest={}
 power_metrics=load(wasm/'power-comparison.json')['cases'];pm={r['name']:r for r in power_metrics}
 for file in sorted((wasm/'results').glob('*.json')):
  r=load(file);assert r['ok'] and r['engine'].startswith('Official EasyEDA NGspice46')
  namecase=r['caseName'];entry={k:r[k] for k in ['ok','status','runtimeMs','userAgent','engine','caseName','exportSampling'] if k in r}
  entry['executionProjectUuid']=r['executionProjectUuid']
  entry['source']={'easyeda_project_sha256':sha(native),**{k:v for k,v in r['source'].items() if 'sha256' in k and 'pcb' not in k}}
  if namecase.startswith('hdmi-'):
   metric=next(x for x in load(wasm/'hdmi-comparison.json')['cases'] if x['name']==namecase)
   metric={k:v for k,v in metric.items() if k not in ['max_waveform_delta_V','classification_matches']}
   hdmi.append(metric);entry['summary']={k:v for k,v in metric.items() if k not in ['conditions']}
  elif 'summary' in r:
   entry['summary']=r['summary'];(periodic if namecase.startswith('periodic-') else links).append({'name':namecase,**r['summary']})
  else:
   assert namecase in pm
   metric={k:v for k,v in pm[namecase].items() if k not in ['delta_vs_previous_V','delta_vs_baseline_V','max_sampled_core_waveform_delta_V','engine_agreement_within_25mV','agreement_within_25mV','classification_matches']}
   if 'within_4p5_to_5p5V' in metric:metric['within_numeric_voltage_limits']=metric.pop('within_4p5_to_5p5V')
   metric.pop('diagnostics',None)
   conditions=load(source/'simulation/power/cases'/(namecase+'.json'));metric['conditions']={k:v for k,v in conditions.items() if k not in ['sourcePCBhash','source_pcb_sha256','variant','name']};powers.append(metric)
   shutil.copy2(file.with_suffix('.csv'),sim/(namecase+'.csv'))
  raw_manifest[namecase]={'sha256':sha(Path(r['rawPath'])),'bytes':Path(r['rawPath']).stat().st_size,'exportSampling':r.get('exportSampling','adaptive solver output')}
  executions.append(entry)
 write(sim/'execution-records.json',executions);write(sim/'raw-output-hashes.json',raw_manifest)
 write(sim/'power-results.json',{'execution':'Official NGspice46 WASM inside EasyEDA API Gateway','cases':powers,'passed':sum(r['within_numeric_voltage_limits'] for r in powers),'voltage_limits':{'core_V':[4.5,5.5],'local_3V3_V':[3.135,3.465] if id=='lite-a' else 'dynamic model excluded'},'scope':'Analytical equivalent circuits, not automatic simulation of the complete manufacturing schematic. Fitted XC6206 dynamics in Lite A; full switching, thermal and PD-negotiation validation excluded.'})
 write(sim/'link-results.json',{'cases':links,'scope':'Linear distributed RLC, fixed switch Ron and IBIS-derived capacitance. Falling extrema inferred by linearity. Weak drive/SLOW and 1MHz initial operation; physical link unverified.'})
 write(sim/'periodic-results.json',{'cases':periodic,'scope':'Solver equations and .tran settings retained. After solving, output is linearized at100ps to stay within the WASM vector export limit. No hardware throughput claim.'})
 write(sim/'hdmi-results.json',{'cases':hdmi,'completed':len(hdmi),'engineering_pass':sum(r['engineering_criteria_ok'] for r in hdmi),'scope':'Coupled RLGC analytical model, assumed Thevenin driver and ideal receiver. No cable. 100mV center decision and 0.4UI window are engineering criteria, not HDMI compliance masks. Vendor IBIS, certification and actual video operation not established.'})
 write(sim/'engine.json',load(wasm/'runtime-manifest.json'))
 portable={}
 for kind in ['power','parallel','periodic','hdmi']:
  data=load(wasm/(kind+'-input.json'));cases=[]
  for c in data['cases']:
   c={k:v for k,v in c.items() if k!='source'}
   if kind=='power':
    p=source/'simulation/power/models'/(c['name']+'.cir');c['netlist']=re.sub(r'^\.include\s+"[^"]+"','.include "TPS5430_TRANS.LIB"',p.read_text(encoding='utf8'),flags=re.M);c['vendor_library_required']='TPS5430_TRANS.LIB, obtained separately from Texas Instruments; inline with original copyright notices before running'
   cases.append(c)
  write(sim/(kind+'-inputs.json'),{'cases':cases})
 # DRC evidence is native-client output, retained verbatim.
 write(hardware/'easyeda-pcb-drc.json',drc);write(hardware/'easyeda-schematic-drc.json',sch)
 fullnative={'native_project_sha256':sha(native),'components':load(design/'easyeda/electrical-migration-audit.json')['components'],'pcba_components':count,'manual_components':1,'smt_side':'top only','manual_refs':['J3'],'power_switch':'omitted','bom_rows':len(bom),'board_dimensions_mm':dim,'pcba_status':'quotation candidate; supplier acceptance pending','pcb_drc_violations':0,'schematic_fatal_errors':0,'schematic_warnings':sum(r['count'] for r in sch if r['type']=='warn'),'connected_schematic_pins_verified':load(design/'easyeda/schematic-migration-audit.json')['connected_pins_checked'],'checks_scope':'Native project connectivity, component values, copper pad positions, track/via net and geometry cross-checks. Physical fit, full DFM and warning classification pending.'}
 write(hardware/'design-record.json',fullnative)
 plot_hdmi(wasm,OUT/'docs/assets'/(id+'-hdmi.png'),('FULL' if id=='full' else 'LITE A'))
 nominal='spark-12V-nominal' if id=='full' else 'spark-lite-a-nominal';plot_power(load(wasm/'results'/(nominal+'.json')),OUT/'docs/assets'/(id+'-power.png'),('FULL' if id=='full' else 'LITE A')+' · power transient / nominal',id=='lite-a')
 if id=='lite-a':plot_power(load(wasm/'results/spark-lite-a-ldo-loop-slow.json'),OUT/'docs/assets/lite-a-stress.png','LITE A · 50mA load step / slow-loop sensitivity',True)
 project['variants'][id]={'dimensions':dim,'components':count,'cases':len(executions),'bom':bom,'power':{'cases':len(powers),'pass':sum(r['within_numeric_voltage_limits'] for r in powers)},'link':{'cases':len(links),'receiverPass':sum(r['receiver_voltage_ok'] for r in links),'driverPass':sum(r['source_voltage_ok'] for r in links),'maxSettleNs':max(r['settle_5percent_ns'] for r in links)},'hdmi':{'cases':len(hdmi),'pass':sum(r['engineering_criteria_ok'] for r in hdmi)},'periodic':{'cases':len(periodic),'oneMHzPass':sum(r['threshold_ok'] for r in periodic if r['freq_Hz']==1000000)},'files':{'native':f'hardware/{id}/{name}','gerbers':f'hardware/{id}/gerbers.zip','bom':f'hardware/{id}/bom.csv','assembly':f'hardware/{id}/assembly-top.svg'},'native':fullnative}
shutil.copy2(H/'single-sided-r4/full/simulation/easyeda-wasm/worker.js',OUT/'simulation/runtime/worker.js')
shutil.copytree(H/'lcsc-priority/simulation/easyeda-wasm/licenses',OUT/'simulation/runtime/licenses',dirs_exist_ok=True)
write(OUT/'docs/data/project.json',project)
manifest={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for folder in ['hardware','simulation','docs/assets','docs/data'] for p in (OUT/folder).rglob('*') if p.is_file()}
write(OUT/'manifest.json',manifest)
assert not list(OUT.rglob('*.kicad*'))
print(json.dumps({k:{'components':v['components'],'cases':v['cases'],'power':v['power'],'link':v['link'],'periodic':v['periodic']} for k,v in project['variants'].items()},indent=2))
