"""Freeze read-only actual A/B copper and official Core net lengths for simulation."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import openpyxl

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records={}
xls=ROOT/'docs/reference/tang-primer-20k/Core_3690_Net_Length.xlsx'
for row in openpyxl.load_workbook(xls,data_only=True).active.values:
    if isinstance(row[1],str) and row[1].startswith('/LVDS_TX'):
        records[row[1].lstrip('/')]=dict(pads=row[2],vias=row[3],via_mm=float(row[4].split()[0])*.0254,track_mm=float(row[5].split()[0])*.0254,all_mm=float(row[7].split()[0])*.0254)
mapping={'D0':('LVDS_TX2_P','LVDS_TX2_N'),'D1':('LVDS_TX3_P','LVDS_TX3_N'),'D2':('LVDS_TX5_N','LVDS_TX5_P'),'CK':('LVDS_TX1_P','LVDS_TX1_N')}
lengths={tag:{'P':dict(net=pair[0],**records[pair[0]]),'N':dict(net=pair[1],**records[pair[1]])} for tag,pair in mapping.items()}
for pair in lengths.values():pair['skew_mm']=pair['P']['all_mm']-pair['N']['all_mm']
(HERE/'core_lengths.json').write_text(json.dumps(dict(source=str(xls.relative_to(ROOT)),sha256=sha(xls),units='mm; spreadsheet All includes via length; Die field is zero, not a certified package delay',pairs=lengths),indent=2)+'\n')
with (HERE/'core_lengths.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['pair','P_net','N_net','P_total_mm','N_total_mm','P_minus_N_mm'])
    for tag,r in lengths.items():w.writerow([tag,r['P']['net'],r['N']['net'],r['P']['all_mm'],r['N']['all_mm'],r['skew_mm']])
manifest={'Core_XLS_sha256':sha(xls),'variants':{}}
for variant in ('lite-a-dual','lite-b-barrel'):
    dst=HERE/'models'/variant;dst.mkdir(parents=True,exist_ok=True)
    src=ROOT/'variants'/variant/'kicad'
    for name in ('tmds_channel.py','tmds_sparam.py','microstrip2d.py'):
        shutil.copyfile(ROOT/'kicad/sim'/name,dst/name)
    for name in ('tmds_roles.json','zdiff_cache.json'):
        shutil.copyfile(src/'sim'/name,dst/name)
    pcb=src/'tab5-fpga-carrier.kicad_pcb'
    code="import sys;sys.argv.append('--extract');sys.path.insert(0,%r);import tmds_channel as tc;tc.extract(%r,%r)"%(str(dst),str(pcb),str(dst/'tmds_geom.json'))
    subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe','-X','utf8','-c',code],check=True,capture_output=True)
    manifest['variants'][variant]=dict(source_pcb=str(pcb.relative_to(ROOT)),source_pcb_sha256=sha(pcb),geometry_sha256=sha(dst/'tmds_geom.json'),roles_sha256=sha(dst/'tmds_roles.json'))
cpcb=ROOT/'variants/lite-c-dnp/kicad/tab5-fpga-carrier.kicad_pcb'
manifest['variants']['lite-c-dnp']=dict(source_pcb=str(cpcb.relative_to(ROOT)),source_pcb_sha256=sha(cpcb),scope='HDMI DNP; no active HDMI eye simulation required')
(HERE/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'prepared':list(manifest['variants']),'core_pairs':lengths},indent=1))
