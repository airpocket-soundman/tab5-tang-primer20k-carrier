"""Attest vendor build without turning 'generated' into 'timing qualified'."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parents[2]
pnr=root/'build/mem-bist-official/mem_bist/impl/pnr'
class Text(HTMLParser):
    def __init__(self):super().__init__();self.items=[]
    def handle_data(self,data):
        if data.strip():self.items.append(data.strip())
t=Text();t.feed((pnr/'mem_bist_tr_content.html').read_text())
def following(label):return t.items[t.items.index(label)+1]
report=(pnr/'mem_bist.rpt.txt').read_text()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def artifact(path):return {'path':str(path.relative_to(root)),'sha256':digest(path),'bytes':path.stat().st_size}
frequency_items=t.items[t.items.index('Max Frequency Summary:'):]
def fmax(name):
    i=frequency_items.index(name)
    return float(frequency_items[i+2].replace('(MHz)',''))
def worst_path(table):
    items=t.items[t.items.index(table):]
    i=items.index('1')
    return {'slack_ns':float(items[i+1]),'from':items[i+2],'to':items[i+3],
            'from_clock':items[i+4],'to_clock':items[i+5]}
inputs=sorted((root/'mem/rtl').glob('*.v'))+sorted((root/'mem/config').glob('*.tcl'))+list((root/'mem/config').glob('*.cst'))+list((root/'mem/config').glob('*.sdc'))
inputs += [root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo']
result={
 'scope':'standalone MEM diagnostic; NOT hardware-approved; physical DDR unverified',
 'tool':'Gowin V1.9.11.03 Education; official CLI, no hardware programming',
 'part':'GW2A-LV18PG256C8/I7','device_version':'C',
 'configured_bytes':134217728,'physical_capacity_known':False,
 'memory_hz':324000000,'user_hz':81000000,
 'synthesis_completed':True,'placement_routing_completed':True,'bitstream_generated':True,
 'timing_qualified':False,'hardware_approved':False,
 'setup_violated_endpoints':int(following('Numbers of Setup Violated Endpoints')),
 'hold_violated_endpoints':int(following('Numbers of Hold Violated Endpoints')),
 'remaining_review':'vendor DDR calibration/gating cross-domain setup and held-bundle CDC hold; no blanket waiver applied',
 'fmax_mhz':{name:fmax(name) for name in ['sys27','memory324','user81']},
 'worst_setup':worst_path('Setup Paths Table'),'worst_hold':worst_path('Hold Paths Table'),
 'fmax_note':'same-domain summary does not qualify cross-domain or external DDR IO timing',
 'logic_used':int(re.search(r'Logic\s+\|\s+(\d+)/',report).group(1)),
 'registers_used':int(re.search(r'Register\s+\|\s+(\d+)/',report).group(1)),
 'inputs':[artifact(p) for p in inputs],
 'outputs':[artifact(pnr/name) for name in ['mem_bist.fs','mem_bist.rpt.txt','mem_bist_tr_content.html','mem_bist.pin.html']],
 'simulation':json.loads((root/'build/mem-tests/results.json').read_text()),
}
dest=root/'validation/mem-bist-prehardware-2026-11-04.json'
dest.write_text(json.dumps(result,indent=2)+'\n')
print(dest)
