"""Full-size TPS5430 averaged5V sensitivity; TLV1117 dynamics not modelled."""
from pathlib import Path
import sys,json,hashlib
H=Path(__file__).resolve().parent;P=H/'simulation/power';sys.path.insert(0,str(P))
from simulate_case import run
dc=json.loads((H/'design/kicad/sim/power_dc_check.json').read_text())
pcb=H/'design/kicad/tab5-fpga-carrier.kicad_pcb'
base=dict(variant='spark-full-pcba',model='average',include_ldo=False,vin=12,stop=.045,settled_start=.015,core_baseline=.05,core_load=.5,hdmi_load=.06,tab_load=1,path_R=max(dc['path_resistance_ohm'].values()),contact_R=.02,return_R=.03,dcr=.027,esr=.04,L=15e-6,cout=220e-6,maxstep=2e-6,sourcePCBhash=hashlib.sha256(pcb.read_bytes().replace(b'\r\n',b'\n')).hexdigest())
cases=[dict(base,name='spark-12V-nominal',kind='barrel'),dict(base,name='spark-11p4V',vin=11.4,kind='barrel'),dict(base,name='spark-12p6V',vin=12.6,kind='barrel'),dict(base,name='spark-PD-profile',kind='pd',settled_start=.020),dict(base,name='spark-load1A-sensitivity',kind='barrel',core_baseline=.5,core_load=1),dict(base,name='spark-lowESR-sensitivity',kind='barrel',esr=.002,cout=176e-6,L=12e-6,pwm_tau=1.25e-6)]
results=[]
for c in cases:
 (P/'cases'/(c['name']+'.json')).write_text(json.dumps(c,indent=2)+'\n')
 results.append(run(c))
(P/'summary.json').write_text(json.dumps({'results':results,'scope':'5V averaged converter sensitivity only; original TI compensation network, full-size single3.24k feedback and Bourns DCR; carrier copper extracted from currentPCB. TLV1117LV33 dynamics excluded,60mA equivalent5V load budget includes local3V3 and HDMI. Not full switching/thermal/CH224K negotiation validation.'},indent=2)+'\n')
