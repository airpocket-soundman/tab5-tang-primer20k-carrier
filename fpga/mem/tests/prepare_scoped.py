"""Qualify exactly20 public generated-netlist pins, then form separate SDC.

No protected source is decoded. Baseline SDC/build output are not replaced.
"""
import hashlib
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parents[2]
proposal=json.loads((root/'mem/config/vendor_async_review.json').read_text())
vo=root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo'
text=vo.read_text()
cells={}
for match in re.finditer(r'^(\w+) \\([^\n]+?)\s+\(\n(.*?)^\);',text,re.M|re.S):
    kind,name,body=match.groups()
    cells['controller/'+name.strip().replace('/','_')]=(kind,body)
pins=[entry['pin'] for entry in proposal['exceptions']]
assert len(pins)==20 and len(set(pins))==20
resolved=[]
for pin in pins:
    cell,port=pin.rsplit('/',1)
    assert cell in cells,('missing generated cell',pin)
    kind,body=cells[cell]
    assert re.search(r'\.'+port+r'\(',body),('missing cell port',pin)
    assert (kind,port) in [('DHCEN','CE'),('DQS','HOLD'),('IDES8_MEM','CALIB'),('DFFC','D')],(pin,kind)
    resolved.append({'pin':pin,'primitive':kind})
# Recalibration stage0 feeds a same-clock second stage in vendor public VO.
assert re.search(r'DFFC \\gw3_top/u_ddr_phy_top/ddr_sync/recalib_s_1_s0.*?\.D\(\\gw3_top/u_ddr_phy_top/ddr_sync/recalib_s \[0\]\)',text,re.S)
out=root/'build/mem-bist-scoped-input';out.mkdir(parents=True,exist_ok=True)
base=(root/'mem/config/mem_bist.sdc').read_text()
extra='\n// Finite20 reviewed vendor asynchronous sampling inputs, no clock groups.\n'
extra+='\n'.join('set_false_path -to [get_pins {'+pin+'}]' for pin in pins)+'\n'
(out/'mem_bist.sdc').write_text(base+extra)
record={'scope':'public generated-netlist endpoint qualification; routed-name interpretation remains checked by tool diagnostics',
        'resolved_unique_endpoints':len(resolved),'endpoints':resolved,
        'generated_vo_sha256':hashlib.sha256(vo.read_bytes()).hexdigest(),
        'combined_sdc_sha256':hashlib.sha256((out/'mem_bist.sdc').read_bytes()).hexdigest(),
        'proposal_sha256':hashlib.sha256((root/'mem/config/vendor_async_review.json').read_bytes()).hexdigest()}
(out/'qualification.json').write_text(json.dumps(record,indent=2)+'\n')
print('PASS20 unique generated cell input pins; separate scoped SDC prepared')
