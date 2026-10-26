"""Run HDL-independent SI equivalents first; later compare actual EasyEDA output."""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
from hdmi_models import deck,CORNERS

def metrics(t,diff,p,n,a):
    ui=a['bit_period_s'];index=np.arange(20,125);bits=np.asarray(a['bits'])[index];sign=2*bits-1
    delay=a['flight_delay_s'];center=(index+1.5)*ui+delay
    values=np.interp(center,t,diff);signed=values*sign
    phases=np.linspace(.05,.95,91);margins=[float(np.min(np.interp((index+1+phase)*ui+delay,t,diff)*sign)) for phase in phases]
    intervals=[];start=None
    for phase,margin in zip(phases,margins):
        if margin>=.1:
            if start is None:start=phase
        elif start is not None:intervals.append(phase-start);start=None
    if start is not None:intervals.append(phases[-1]-start)
    return {'minimum_signed_center_margin_V':float(signed.min()),'center_eye_height_V':float(values[bits==1].min()-values[bits==0].max()),'center_bit_errors':int(np.sum(signed<=0)),'center_below_100mV_count':int(np.sum(signed<.1)), 'sample_window_over_100mV_UI':max(intervals,default=0.),'rx_single_ended_min_V':float(min(p.min(),n.min())),'rx_single_ended_max_V':float(max(p.max(),n.max())),'engineering_criteria_ok':bool(signed.min()>=.1 and max(intervals,default=0.)>=.4),'samples':len(t)}

def main(v):
    root=H/v;folder=root/'simulation/hdmi';(folder/'decks').mkdir(exist_ok=True);(folder/'results').mkdir(exist_ok=True)
    sys.path.insert(0,str(root/'simulation/power'));from ngspice_shared import Spice
    sections=json.loads((folder/'sections.json').read_text());cases=[];outputs=[]
    jobs=[(lane,rate,corner,'prbs7',2.) for lane in ['D0','D1','D2','CK'] for rate in [742.5e6,1485e6] for corner in CORNERS]
    jobs += [(lane,251.75e6,'nominal','prbs7',2.) for lane in ['D0','D1','D2','CK']]
    jobs += [(lane,742.5e6,'nominal','control00',2.) for lane in ['D0','D1','D2']]
    jobs += [(lane,742.5e6,'nominal','prbs7',1.) for lane in ['D0','D1','D2','CK']]
    rawdir=Path('D:/tmp/carrier-hdmi-r4-'+v);rawdir.mkdir(exist_ok=True)
    pcbhash=hashlib.sha256((root/'design/kicad/tab5-fpga-carrier.kicad_pcb').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    for lane,rate,corner,pattern,step in jobs:
        text,a=deck(sections,lane,rate,corner,499 if v=='full' else 510,pattern,step)
        name=f'hdmi-{lane}-{rate/1e6:g}M-{corner}-{pattern}-cell{step:g}'
        (folder/'decks'/(name+'.cir')).write_text(text,encoding='utf8')
        s=Spice();start=time.time();assert s.load(text.splitlines())==0;s.run()
        t=s.vector('time');assert t[-1]>=129*a['bit_period_s']*.9999,(name,t[-1],s.messages[-4:])
        data={'time':t,'diff':s.vector('v(rx_diff)'),'p':s.vector('v(rx_p)'),'n':s.vector('v(rx_n)'),'source':s.vector('v(src_diff)')}
        raw=rawdir/(name+'.npz');np.savez_compressed(raw,**data)
        result={'name':name,'conditions':a,**metrics(t,data['diff'],data['p'],data['n'],a),'runtime_s':time.time()-start,'raw_path':str(raw)}
        (folder/'results'/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');outputs.append(result)
        cases.append({'name':name,'netlist':text,'analysis':a,'source':{'netlist_sha256':hashlib.sha256(text.encode()).hexdigest(),'pcb_normalized_sha256':pcbhash,'scope':a['scope']}})
        print(v,name,result['minimum_signed_center_margin_V'],result['engineering_criteria_ok'],flush=True)
    refinements=[]
    for x in outputs:
        if x['conditions']['step_mm']!=1:continue
        coarse=next(y for y in outputs if y['name']==x['name'].replace('cell1','cell2'))
        refinements.append({'lane':x['conditions']['lane'],'center_margin_delta_V':x['minimum_signed_center_margin_V']-coarse['minimum_signed_center_margin_V'],'within_10mV':abs(x['minimum_signed_center_margin_V']-coarse['minimum_signed_center_margin_V'])<.01})
    report={'cases':outputs,'completed':len(outputs),'engineering_pass':sum(x['engineering_criteria_ok'] for x in outputs),'mesh_refinement':refinements,'scope':'Analytical assumptions and engineering thresholds only. Not HDMI compliance or vendor-IBIS validation.'}
    (folder/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (root/'simulation/easyeda-wasm/hdmi-input.json').write_text(json.dumps({'cases':cases},indent=2)+'\n')
    print(v,'HDMI complete',report['completed'],'engineering criteria',report['engineering_pass'],flush=True)

if __name__=='__main__':main(sys.argv[1])
