"""Parent-side audit of actual KiCad PCB against XML netlist and original pins.

Run using KiCad Python after exporting XML with kicad-cli sch export netlist.
This does not import the variant generator or trust its self-check results.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import pcbnew

ROOT=Path(__file__).resolve().parents[2]
name=sys.argv[1]
folder=ROOT/'variants'/name/'kicad'
pcb=folder/'tab5-fpga-carrier.kicad_pcb'
xml=Path(sys.argv[2])
out=ROOT/'variants/validation'/f'{name}-independent-audit.json'
b=pcbnew.LoadBoard(str(pcb))
original=pcbnew.LoadBoard(str(ROOT/'kicad/tab5-fpga-carrier.kicad_pcb'))
fps={f.GetReference():f for f in b.GetFootprints()}
base={f.GetReference():f for f in original.GetFootprints()}
doc=ET.parse(xml).getroot()
checks=[]
def check(label,ok,details=None):
    checks.append(dict(name=label,ok=bool(ok),details=details))
def pads(fp):
    return {p.GetNumber():p for p in fp.Pads() if p.GetNumber()}
def pos(p):
    v=p.GetPosition();return (pcbnew.ToMM(v.x),pcbnew.ToMM(v.y))
schema={c.attrib['ref']:c for c in doc.findall('./components/comp')}
mismatches=[]; nc=[]
for net in doc.findall('./nets/net'):
    expected=net.attrib['name'].lstrip('/')
    for node in net.findall('node'):
        ref,pin=node.attrib['ref'],node.attrib['pin']
        if ref not in fps:
            mismatches.append([ref,pin,expected,'missing footprint']);continue
        pp=[p for p in fps[ref].Pads() if p.GetNumber()==pin]
        if expected.startswith('unconnected-('):
            if any(p.GetNetname() for p in pp):nc.append([ref,pin,expected,[p.GetNetname() for p in pp]])
            continue
        if not pp or any(p.GetNetname()!=expected for p in pp):
            mismatches.append([ref,pin,expected,[p.GetNetname() for p in pp]])
check('schematic_connected_nodes_equal_PCB',not mismatches,mismatches)
check('schematic_NC_not_wired_on_PCB',not nc,nc)
values=[];dnp=[];footprints=[]
for ref,c in schema.items():
    if ref not in fps:continue
    fp=fps[ref]
    if c.findtext('value')!=fp.GetValue():values.append([ref,c.findtext('value'),fp.GetValue()])
    fpid=fp.GetFPID()
    footprint_name=str(fpid.GetLibNickname())+':'+str(fpid.GetLibItemName())
    expected_fp=c.findtext('footprint')
    # FootprintLoad in the original generator does not populate the library
    # nickname. Compare the physical footprint name, and namespace when stored.
    if expected_fp.split(':')[-1]!=str(fpid.GetLibItemName()) or (str(fpid.GetLibNickname()) and expected_fp!=footprint_name):footprints.append([ref,expected_fp,footprint_name])
    expected=any(p.attrib.get('name')=='dnp' for p in c.findall('property'))
    if expected != fp.IsDNP():dnp.append([ref,expected,fp.IsDNP()])
check('schematic_values_equal_PCB',not values,values)
check('schematic_footprints_equal_PCB',not footprints,footprints)
check('schematic_population_equal_PCB',not dnp,dnp)
if name in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
    button_errors=[]
    cy=7.5 if name=='lite-c-dnp' else 6.5
    coords=[('SW1',29.),('SW2',42.2)] if name=='lite-c-dnp' else [('SW1',59.9),('SW2',70.5)]
    for ref,x in coords:
        f=fps[ref]
        expected=sorted((n,round(x+dx,5),round(cy+dy,5)) for n,dx in [('1',-4.1),('2',4.1)] for dy in [-2.25,2.25])
        actual=sorted((p.GetNumber(),round(pos(p)[0],5),round(pos(p)[1],5)) for p in f.Pads())
        if f.GetValue()!='TS-06104' or str(f.GetFPID().GetLibItemName())!='SW_TS_06104_HandSolder' or actual!=expected:button_errors.append(ref)
    check('Akizuki_TS06104_button_pads_match_manufacturer',not button_errors,button_errors)
for ref in ('J3','J4'):
    old=pads(base[ref]);new=pads(fps[ref]);pins=[str(n) for n in range(1,31 if ref=='J3' else 205)]
    wrong=[p for p in pins if p not in new or old[p].GetNetname()!=new[p].GetNetname()]
    check(ref+'_preserved_all_connector_pin_nets',not wrong,wrong)
check('socket_PCBA_required',not fps['J4'].IsDNP())
check('PMOD_GPIO_pin_sockets_DNP',all(r in fps and fps[r].IsDNP() for r in ('J6','J7','J8')))
mb=pads(fps['J3'])
check('M5Bus_real_left_right_preserved',fps['J3'].IsFlipped() and all(sum((a-z)**2 for a,z in zip(pos(mb[n]),xy))<1e-6 for n,xy in [('1',(53.73,22.15)),('2',(56.27,22.15)),('29',(53.73,57.71)),('30',(56.27,57.71))]))
check('Tab5_5V_VBAT_not_tied',all(not mb[p].GetNetname() for p in ('28','30')))
sc=pads(fps['J4']);sock=fps['J4'];cx,cy=pos(sock)
geometry=[]
for n in range(1,205):
    local_x=-31.65+(n-1)*.3+(2.4 if n>72 else 0)
    local_y=4.1 if n%2 else -4.1
    expected=(cx-local_y,cy+local_x)
    if sum((a-z)**2 for a,z in zip(pos(sc[str(n)]),expected))>.003**2:
        geometry.append([n,pos(sc[str(n)]),expected])
check('socket_204_centers_match_STD_drawing',not geometry,geometry)
required=('U7','U8','U9','U10','Q3','Q4','JP1','R46','R47','R48','U2','U3','L1','D1','D3','D4','F1','C1','C7','R6','R7','R49','R50')
check('minimum_power_bus_safety_parts_fitted',all(r in fps and not fps[r].IsDNP() for r in required),[r for r in required if r not in fps or fps[r].IsDNP()])
series=[]
for ref,fp in fps.items():
    if not ref.startswith('R'):continue
    ns={str(p.GetNetname()) for p in fp.Pads()}
    iso=next((n for n in ns if n.startswith('ISO_')),None)
    if iso and ns=={iso,'F_'+iso[4:]}:series.append(ref)
check('all_15_parallel_series_680R_fitted',len(series)==15 and all(fps[r].GetValue()=='680R' and not fps[r].IsDNP() for r in series),series)
if name!='lite-c-dnp':
    caps=[f'C{i}' for i in range(12,20)]
    check('HDMI_caps_low_profile_0402',all('C_0402' in str(fps[r].GetFPID().GetLibItemName()) for r in caps))
    check('sideband_ESD_independent_ground_low_profile',str(fps['U6'].GetFPID().GetLibItemName())=='DFN2510-10L_RCLAMP0524P' and fps['U6'].GetValue()=='RCLAMP0524P')
    expected_hpd={'Q5':{'1':'HPD_B','2':'GND','3':'HPD_BUF'},'R40':{'1':'HDMI_HPD','2':'HPD_B'},'R41':{'1':'HPD_B','2':'GND'},'R51':{'1':'+3V3','2':'HPD_BUF'},'R52':{'1':'HPD_BUF','2':'F_HPD'},'C24':{'1':'HPD_BUF','2':'GND'}}
    check('HPD_inverting_filtered_current_limited_topology',all(r in fps and not fps[r].IsDNP() and {n:str(p.GetNetname()) for n,p in pads(fps[r]).items()}==ns for r,ns in expected_hpd.items()))
shape=b.GetBoardEdgesBoundingBox();dims=[pcbnew.ToMM(shape.GetWidth()),pcbnew.ToMM(shape.GetHeight())]
target=[125,78] if name=='lite-c-dnp' else [99,78]
check('outline_target',all(abs(a-z)<.15 for a,z in zip(dims,target)),dict(actual_edge_bbox_mm=dims,target_mm=target))
if name=='lite-c-dnp':
    expected={'J2','U1','C2','R1','R2','R3','R4','R5','D2','J5','U4','U5','U6','Q1','Q2','F2','Q5','R51','R52','C24'}|{f'C{i}' for i in range(12,20)}|{f'R{i}' for i in range(28,42)}
    check('all_HDMI_PD_lands_retained_but_DNP',all(r in fps and fps[r].IsDNP() for r in expected))
elif name=='lite-b-barrel':
    removed={'J2','U1','C2','R1','R2','R3','R4','R5','D2'}
    check('PD_removed',not removed.intersection(fps))
else:
    check('PD_12V_fitted',all(r in fps and not fps[r].IsDNP() for r in ('J2','U1','R3','R5','D2')) and fps['R4'].IsDNP())
if name!='lite-c-dnp':check('single_Basic_510R_all_TMDS_bias',all(fps[f'R{i}'].GetValue()=='510R' and not fps[f'R{i}'].IsDNP() for i in range(28,36)))
packages=list((ROOT/'variants'/name/'manufacturing').glob('*/package-check.json'))
check('one_manufacturing_candidate',len(packages)==1,[str(p.relative_to(ROOT)) for p in packages])
if len(packages)==1:
    package=packages[0].parent
    manifest=json.loads(packages[0].read_text(encoding='utf-8'))
    expected_hash=hashlib.sha256(pcb.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    check('manufacturing_matches_current_PCB',manifest['source_pcb_sha256']==expected_hash)
    with (package/'jlc-bom.csv').open(encoding='utf-8',newline='') as f:bom=list(csv.DictReader(f))
    with (package/'jlc-cpl.csv').open(encoding='utf-8',newline='') as f:cpl=list(csv.DictReader(f))
    brefs={r.strip():row['LCSC Part #'] for row in bom for r in row['Designator'].split(',')}
    crefs=[row['Designator'] for row in cpl]
    check('BOM_CPL_equal_and_no_DNP',set(brefs)==set(crefs) and len(crefs)==len(set(crefs)) and all(not fps[r].IsDNP() for r in crefs))
    check('socket_LDO_L1_correct_procurement',all(brefs.get(r)==p for r,p in [('J4','C22471982'),('U3','C5446'),('L1','C380054'),('R7','C22978'),('R49','C25803'),('R50','C25803')]))
    check('parallel_series_approved_Basic_680R',len(series)==15 and all(brefs.get(r)=='C23228' for r in series))
    check('manual_barrel_not_accidentally_PCBA',all(r not in crefs for r in ('J1','J3','JP1')))
    if name in ('lite-a-dual','lite-b-barrel'):check('HDMI_connector_PCBA_required',brefs.get('J5')=='C916313' and 'J5' in crefs)
    check('PMOD_GPIO_pin_sockets_not_in_BOM_CPL',not {'J6','J7','J8'}.intersection(set(brefs)|set(crefs)))
    if name!='lite-c-dnp':check('Basic_bias_correct_procurement',all(brefs.get(f'R{i}')==('C25123' if i in (30,31) else 'C23193') for i in range(28,36)))
    check('CPL_in_board_origin_frame',all(0<=float(row['Mid X'])<=target[0] and 0<=float(row['Mid Y'])<=target[1] for row in cpl))
    hashes=[]
    for fname,digest in manifest.get('files',{}).items():
        path=package/fname
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:hashes.append(fname)
    check('manufacturing_files_equal_manifest',not hashes,hashes)
report_path=ROOT/'variants/validation'/f'{name}-drc.json'
if report_path.exists():
    drc=json.loads(report_path.read_text(encoding='utf-8'))
    check('parent_DRC_no_violations_no_unconnected',not drc['violations'] and not drc['unconnected_items'])
    default=json.loads((ROOT/'kicad/sim/drc_r3.json').read_text(encoding='utf-8'))
    check('DRC_no_added_ignored_rule_types',drc.get('ignored_checks')==default.get('ignored_checks'))
result=dict(ok=all(c['ok'] for c in checks),scope='Independent actual XML/PCB and preserved pin/physical pattern check; physical operation and full-board EM not established',variant=name,pcb_sha256=hashlib.sha256(pcb.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),pcb_hash_normalization='CRLF to LF',checks=checks)
out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(dict(variant=name,ok=result['ok'],checks=len(checks),failed=[c['name'] for c in checks if not c['ok']]),ensure_ascii=False))
