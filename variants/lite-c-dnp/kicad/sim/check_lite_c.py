"""Cross-check actual lite C PCB, generated design, XML netlist, and PCBA scope."""
from collections import Counter
import csv
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import pcbnew

HERE=Path(__file__).resolve().parent
KICAD=HERE.parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('lite_design',KICAD/'gen/design.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
components={c.ref:c for c in model.build()}
board=pcbnew.LoadBoard(str(KICAD/'tab5-fpga-carrier.kicad_pcb'))
base=pcbnew.LoadBoard(str(ROOT/'kicad/tab5-fpga-carrier.kicad_pcb'))
fps={f.GetReference():f for f in board.GetFootprints()}
bfps={f.GetReference():f for f in base.GetFootprints()}
subprocess.run([str(Path(sys.executable).parent/'kicad-cli.exe'),'sch','export','netlist','--format','kicadxml','-o',str(HERE/'schematic.net.xml'),str(KICAD/'tab5-fpga-carrier.kicad_sch')],check=True)
xml=ET.parse(HERE/'schematic.net.xml').getroot()
nets={}
for net in xml.findall('./nets/net'):
    for node in net.findall('node'):
        nets[(node.get('ref'),node.get('pin'))]=net.get('name').lstrip('/')
checks=[]
def record(name,ok,**detail):checks.append(dict(name=name,ok=bool(ok),**detail))
errors=[]
for ref,c in components.items():
    f=fps[ref]
    if f.GetValue()!=c.value or f.IsDNP()!=c.dnp:errors.append((ref,'value/DNP'))
    for pin,net in c.pins.items():
        if net is not None and nets.get((ref,pin))!=net:errors.append((ref,pin,'schematic',net,nets.get((ref,pin))))
    for p in f.Pads():
        if not p.GetNumber():continue
        expected=(c.pads or c.pins).get(p.GetNumber())
        if p.GetNumber() in ('MP','SH'):expected='GND'
        if p.GetNetname()!=(expected or ''):errors.append((ref,p.GetNumber(),'PCB',expected,p.GetNetname()))
record('schematic_design_and_PCB_pin_nets',not errors,errors=errors)
def geometry(b):
    result=Counter()
    for t in b.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA):
            result[('via',t.GetNetname(),t.GetPosition().x,t.GetPosition().y,t.GetWidth(pcbnew.F_Cu),t.GetDrillValue())]+=1
        else:
            a=(t.GetStart().x,t.GetStart().y);z=(t.GetEnd().x,t.GetEnd().y)
            result[('track',t.GetNetname(),t.GetLayer(),tuple(sorted((a,z))),t.GetWidth())]+=1
    return result
old=geometry(base);new=geometry(board)
signal_old=Counter({k:v for k,v in old.items() if k[1] not in ('GND','+5V','+3V3','VIN','DC_RAW','DC_IN','VBUS_PD','BUCK_PH','BUCK_BOOT','BUCK_FB','BUCK_EN','HDMI_SDA','HDMI_SCL','HDMI_HPD','HDMI_5V','F_HPD')})
record('all_original_parallel_and_TMDS_tracks_and_vias_preserved_HDMI_sideband_intentionally_rerouted',not(signal_old-new),original_signal_items=sum(signal_old.values()),added_items=sum((new-old).values()),removed_power_items=sum((old-new).values()))
oldpads={p.GetNumber():p for p in bfps['J4'].Pads() if p.GetNumber().isdigit()}
newpads={p.GetNumber():p for p in fps['J4'].Pads() if p.GetNumber().isdigit()}
delta={n:pcbnew.ToMM((oldpads[n].GetPosition()-newpads[n].GetPosition()).EuclideanNorm()) for n in oldpads}
record('socket_all_204_pin_numbers_and_positions',len(newpads)==204 and max(delta.values())<.003,max_pad_shift_mm=max(delta.values()))
record('socket_hold_downs_grounded',len([p for p in fps['J4'].Pads() if p.GetNumber()=='MP' and p.GetNetname()=='GND'])==2)
record('changed_footprints_match_design',all(str(fps[r].GetFPID().GetLibNickname())+':'+str(fps[r].GetFPID().GetLibItemName())==components[r].fp for r in ('J4','L1','U3','R49','R50')))
def pad(ref,num):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(num))
local_caps={name:pcbnew.ToMM((pad(cap,1).GetPosition()-pad('U3',upin).GetPosition()).EuclideanNorm()) for name,cap,upin in [('input','C10',3),('output','C11',2)]}
record('LDO_capacitors_near_pins',all(v<3 for v in local_caps.values()),straight_pad_distance_mm=local_caps)
hole_xy=[(pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)) for r,f in fps.items() if r.startswith('H')]
hole_clear={}
for ref in ('C10','C11','U3','R49','R50','L1'):
    bb=fps[ref].GetBoundingBox(False)
    x0,y0,x1,y1=map(pcbnew.ToMM,(bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()))
    hole_clear[ref]=min(math.hypot(max(x0-x,0,x-x1),max(y0-y,0,y-y1))-1.6 for x,y in hole_xy)
record('new_placements_keep_5mm_from_hole_edge',all(v>=5 for v in hole_clear.values()),clearance_mm=hole_clear)
rows=list(csv.DictReader((KICAD/'bom.csv').open(encoding='utf-8',newline='')))
poprefs={r for row in rows if not row['DNP'] for r in row['Refs'].split(',')}
record('socket_populated_and_core_module_not_procured','J4' in poprefs and next(r for r in rows if 'J4' in r['Refs'].split(','))['LCSC']=='C22471982' and all(r['Value']!='Tang Primer 20K Core' for r in rows))
record('required_barrel_power_and_bus_fitted',all(ref in poprefs for ref in ('J1','F1','D1','D3','C1','U2','L1','U3','J4','U7','U8','U9','U10','Q3','Q4','R49','R50')))
drc=json.loads((HERE/'drc_r3.json').read_text(encoding='utf-8'))
record('DRC_all_severities_and_unconnected_zero',not drc['violations'] and not drc['unconnected_items'])
package=KICAD.parent/'manufacturing/poc-lite-c-2026-10-25'
if package.exists():
    bom=list(csv.DictReader((package/'jlc-bom.csv').open(encoding='utf-8',newline='')))
    cpl=list(csv.DictReader((package/'jlc-cpl.csv').open(encoding='utf-8',newline='')))
    refs={r for row in bom for r in row['Designator'].split(',')}
    record('PCBA_BOM_CPL_exact_ref_match',refs=={r['Designator'] for r in cpl} and len(refs)==len(cpl),pcba_components=len(refs))
    record('PCBA_socket_included_HDMI_PD_excluded','J4' in refs and not (refs&{'J2','U1','C2','R1','R2','R3','R4','R5','D2','J5','U4','U5','U6','Q1','Q2','Q5','R51','R52','C24','F2'}))
result=dict(ok=all(r['ok'] for r in checks),variant='lite-c-dnp',checks=checks,scope='CAD connectivity and population validation; not measured hardware or firmware operation')
(HERE/'lite_c_check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'ok':result['ok'],'checks':len(checks),'failed':[r for r in checks if not r['ok']]},indent=1))
raise SystemExit(0 if result['ok'] else 1)
