"""Prepare an isolated full-size engineering candidate; never edits source designs."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'tab5-tang-primer20k-carrier-audit-pages'
OUT=ROOT/'spark/design'
K=OUT/'kicad'
if (K/'gen/design.py').exists():
    raise SystemExit('Already prepared; refusing to overwrite candidate edits')
protected={}
for folder in ('kicad','variants','manufacturing'):
    for p in (SOURCE/folder).rglob('*'):
        if p.is_file() and p.suffix in ('.kicad_pcb','.kicad_sch','.csv','.kicad_mod','.kicad_sym','.json','.py') and '__pycache__' not in p.parts:
            protected[str(p.relative_to(SOURCE))]=hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'spark/sources/preserved-design-hashes.json').write_text(json.dumps({'root':str(SOURCE),'files':protected},indent=2)+'\n',encoding='utf8')
for folder in ('gen','lib'):
    shutil.copytree(SOURCE/'kicad'/folder,K/folder,ignore=shutil.ignore_patterns('__pycache__'))
for p in (SOURCE/'variants/lite-a-dual/kicad/lib/carrier.pretty').glob('*'):
    shutil.copyfile(p,K/'lib/carrier.pretty'/p.name)
for name in ('tab5-fpga-carrier.kicad_pro','fp-lib-table','sym-lib-table'):
    shutil.copyfile(SOURCE/'kicad'/name,K/name)
(K/'sim').mkdir()
for name in ('check_parallel_power.py','check_power_dc.py','check_mbus_revision.py','check_d1_bias.py','check_esd_footprint.py','check_continuity.py','check_classification.py','check_ground_reference.py','tmds_channel.py','tmds_sparam.py','microstrip2d.py'):
    p=SOURCE/'kicad/sim'/name
    if p.exists():shutil.copyfile(p,K/'sim'/name)
shutil.copyfile(K/'gen/design.py',K/'gen/design_base.py')
lite=(SOURCE/'variants/lite-a-dual/kicad/gen/design.py').read_text(encoding='utf8')
hdmi=lite[lite.index('# BEGIN qualified low-profile'):lite.index('# Akizuki TS-06104')]
model='''"""Spark full-size125x78 candidate. KiCad engineering reference, not an eligible EasyEDA entry yet."""
from design_base import *
import design_base as base
import json
from pathlib import Path
BOARD=(2.,1.,127.,79.)
VARIANT='spark-full-pcba'
POSE=json.loads((Path(__file__).parent/'full-placement.json').read_text())
def build():
    cs=base.build()
    for c in cs:
        if c.ref in POSE:c.pos,c.rot=tuple(POSE[c.ref][0]),POSE[c.ref][1]
        if c.ref.startswith('R') and set(c.pins.values())=={'ISO_'+s for s in []}:pass
        nets=set(c.pins.values())
        iso=next((n for n in nets if n and n.startswith('ISO_')),None)
        if iso and nets=={iso,'F_'+iso[4:]}:
            c.value='680R';c.lcsc='C23228'
            c.comment='Initial PoC1MHz; DATA setup/hold>=250ns; DIR deadtime>=500ns; weak drive/SLOW. New full-size routing must be re-evaluated.'
        if c.ref=='J4':
            c.fp='carrier:DDR3_XDAP_4042044_20401';c.value='SOCKET XDAP-4042044-20401';c.lcsc='C22471982'
            c.comment='PCBA mandatory; socket only, Core module supplied by user; confirm stock/fixture'
    return cs
'''
model=model.replace("        if c.ref.startswith('R') and set(c.pins.values())=={'ISO_'+s for s in []}:pass\n",'')
(K/'gen/design.py').write_text(model+'\n'+hdmi,encoding='utf8')
print('Prepared',K,'; protected',len(protected),'source files')
