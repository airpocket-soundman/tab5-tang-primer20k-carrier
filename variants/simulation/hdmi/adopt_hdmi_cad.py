from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[3]
VARIANTS=('lite-a-dual','lite-b-barrel','lite-c-dnp')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for v in __import__('sys').argv[1:] or VARIANTS:
 src=Path('D:/tmp/hdmi-cad-revision')/v/'kicad';dst=ROOT/'variants'/v/'kicad'
 stat=json.loads((src/'prototype_status.json').read_text());assert not stat['failed_routes']
 assert sha(dst/'tab5-fpga-carrier.kicad_pcb')==stat['source_raw_sha256'],'User/source PCB changed after prototype: stop'
 report=Path('D:/tmp/hdmi-cad-revision')/(v+'-adopt-drc.json')
 subprocess.run(['C:/Program Files/KiCad/10.0/bin/kicad-cli.exe','pcb','drc','--severity-all','--format','json','-o',str(report),str(src/'tab5-fpga-carrier.kicad_pcb')],check=True,capture_output=True)
 r=json.loads(report.read_text(encoding='utf8'));assert not r['violations'] and not r['unconnected_items'],(v,r)
 for name in ['tab5-fpga-carrier.kicad_pcb','tab5-fpga-carrier.kicad_sch','bom.csv','core_pin_assignment.csv','gen/design.py','gen/order_parts.json','lib/carrier.kicad_sym','sim/tmds_roles.json']:shutil.copyfile(src/name,dst/name)
 (dst/'gen/rebuild_qualified_hdmi.py').write_text('''"""Deterministic reviewed local HDMI stage. Outputs temp only; requires DRC and guarded adoption.
Run AFTER any full make_pcb stage to prevent restoring the old sideband topology.
The preserved pre-HDMI snapshot is authoritative for this qualified local stage;
new unrelated board changes require a fresh audited snapshot, never silent merge.
"""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4]
variant=Path(__file__).resolve().parents[2].name
subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe','-X','utf8',str(root/'variants/simulation/hdmi/prepare_hdmi_cad.py'),variant],check=True)
print('Temporary result only. Run DRC and adopt_hdmi_cad.py '+variant+' to apply with raw-SHA guard.')
''')
 (dst/'sim/hdmi-revision-adoption.json').write_text(json.dumps({'baseline_raw_sha256':stat['source_raw_sha256'],'adopted_raw_sha256':sha(dst/'tab5-fpga-carrier.kicad_pcb'),'DRC_violations':0,'DRC_unconnected':0,'HPD_active_low':True,'Core_off_injection':'10k limited; vendor tolerance not established','C24_position':(65,53) if v=='lite-c-dnp' else (65,55)},indent=2)+'\n')
 print(v,sha(dst/'tab5-fpga-carrier.kicad_pcb'))
