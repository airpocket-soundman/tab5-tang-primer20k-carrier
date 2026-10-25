"""Derive independent B from the verified common 99mm layout; source read-only.

Keeps routing already verified for the common circuitry. Removes the complete
PD-only branch, then requires fresh DRC and B-specific electrical verification.
"""
from pathlib import Path
import hashlib
import json
import shutil
import pcbnew

B=Path(__file__).resolve().parent
A=B.parent/'lite-a-dual'
REMOVED={'J2','U1','C2','R1','R2','R3','R4','R5','D2'}
for name in ('gen','lib'):
    shutil.copytree(A/'kicad'/name,B/'kicad'/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','export_poc_package.py'))
for name in ('fp-lib-table','sym-lib-table','tab5-fpga-carrier.kicad_pro'):
    shutil.copy2(A/'kicad'/name,B/'kicad'/name)
gen=B/'kicad/gen'
shutil.copy2(gen/'design_variant.py',gen/'design_dual.py')
(gen/'design_variant.py').write_text('''"""B: common verified 99x78 layout, HDMI fitted, barrel 12V only."""
import design_dual as dual
from design_dual import *
VARIANT='lite-b-barrel'
REMOVED={'J2','U1','C2','R1','R2','R3','R4','R5','D2'}
EDGE_CONNECTORS=('J1','J4','J5')
def build():
    cs=dual.build()
    cs[:]=[c for c in cs if c.ref not in REMOVED]
    return cs
''',encoding='utf-8')
for name in ('make_sch.py','make_pcb.py'):
    p=gen/name;s=p.read_text(encoding='utf-8')
    s=s.replace('lite A dual input','lite B barrel input').replace('lite-a-dual','lite-b-barrel').replace('Independent lite A: 99x78mm, HDMI and dual 12V inputs; PCBA socket','Independent lite B: 99x78mm, HDMI and barrel 12V only; PCBA socket')
    p.write_text(s,encoding='utf-8')
source=A/'kicad/tab5-fpga-carrier.kicad_pcb'
board=pcbnew.LoadBoard(str(source))
footprints=list(board.GetFootprints())
remaining={p.GetNetname() for f in footprints if f.GetReference() not in REMOVED for p in f.Pads() if p.GetNetname()}
branch={p.GetNetname() for f in footprints if f.GetReference() in REMOVED for p in f.Pads() if p.GetNetname()}
dedicated=branch-remaining
keepalive=[]
for t in list(board.GetTracks()):
    if t.GetNetname() in dedicated:
        keepalive.append(t);board.RemoveNative(t)
for f in footprints:
    if f.GetReference() in REMOVED:
        keepalive.append(f);board.RemoveNative(f)
tb=board.GetTitleBlock();tb.SetTitle('Tab5 Tang Primer20K carrier - lite B barrel 12V');tb.SetRevision('lite-b-barrel');tb.SetDate('2026-10-25')
tb.SetComment(0,'99x78mm; HDMI fitted; USB PD removed; socket PCBA required')
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(B/'kicad/tab5-fpga-carrier.kicad_pcb'),board)
report={'source_variant':'lite-a-dual','source_pcb_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'removed_refs':sorted(REMOVED),'PD_exclusive_nets_copper_removed':sorted(dedicated),'strategy':'preserve verified common placement and routing, then remove full PD-only branch; B requires independent revalidation'}
(B/'kicad/sim/common-layout-derivation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
