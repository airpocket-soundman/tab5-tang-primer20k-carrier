"""Extract a variant PCB independently and run the retained channel model.

System Python entry point. Model copies and outputs stay under validation/.
"""
from pathlib import Path
import hashlib
import importlib
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
variant=sys.argv[1]
src=ROOT/'variants'/variant/'kicad'
out=ROOT/'variants/validation'/(variant+'-channel')
out.mkdir(parents=True,exist_ok=True)
for name in ('tmds_channel.py','tmds_sparam.py','microstrip2d.py'):
    shutil.copyfile(ROOT/'kicad/sim'/name,out/name)
for name in ('tmds_roles.json','zdiff_cache.json'):
    shutil.copyfile(src/'sim'/name,out/name)
pcb=src/'tab5-fpga-carrier.kicad_pcb'
before=hashlib.sha256(pcb.read_bytes()).hexdigest()
code="import sys;sys.argv.append('--extract');sys.path.insert(0,%r);import tmds_channel as tc;tc.extract(%r,%r)"%(str(out),str(pcb),str(out/'tmds_geom.json'))
subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe','-X','utf8','-c',code],check=True,capture_output=True)
sys.path.insert(0,str(out))
sp=importlib.import_module('tmds_sparam')
sp.R_BIAS=510.0
sp.tc.load()
sp.main()
sp.tc.main()
after=hashlib.sha256(pcb.read_bytes()).hexdigest()
assert before==after,'PCB changed during channel extraction; repeat after finalization'
report=dict(variant=variant,source_pcb_sha256=before,bias_ohms=510,
            scope='Actual variant copper and retained Core approximation; geometry/classification must pass separately. No via/pad/full-board 3D calibration or HDMI compliance claimed.',
            results=json.loads((out/'tmds_sparam.json').read_text()))
(out/'channel-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
