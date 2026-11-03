"""Attest vendor build without turning 'generated' into 'timing qualified'."""
import hashlib
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--scoped',action='store_true')
args=parser.parse_args()
pnr=root/('build/mem-bist-scoped/mem_bist/impl/pnr' if args.scoped else 'build/mem-bist-official/mem_bist/impl/pnr')
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
def scoped_paths(needle):
    command=next(s for s in t.items if s.startswith('Report Command:') and needle in s)
    i=t.items.index(command)+1
    while t.items[i]!='Data Delay':i+=1
    i+=1
    paths=[]
    while t.items[i].isdigit():
        paths.append({'from':t.items[i+2],'to':t.items[i+3],
                      'slack_ns':float(t.items[i+1]),'data_delay_ns':float(t.items[i+8])})
        i+=9
    return paths
def negative_paths(table):
    i=t.items.index(table);i=t.items.index('Data Delay',i)+1
    paths=[]
    while t.items[i].isdigit():
        if t.items[i+1].startswith('-'):
            paths.append({'from':t.items[i+2],'to':t.items[i+3],
                          'slack_ns':float(t.items[i+1]),'from_clock':t.items[i+4],'to_clock':t.items[i+5]})
        i+=9
    return paths
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
 'remaining_review':('finite20 vendor async inputs active in this separate build; remaining init/DLL paths unwaived' if args.scoped else 'vendor DDR calibration/gating and initialization crossings; finite vendor proposal NOT active; no blanket waiver applied'),
 'held_bundle_constraints':{
   'request_earliest_capture_ns':2e9/81000000,'request_max_delay_ns':20,
   'snapshot_earliest_capture_ns':3e9/27000000+1e9/81000000,'snapshot_max_delay_ns':60,
   'hold_exempt_only_for_held_bundles':True,
   'request_paths':scoped_paths('control/held_base*'),
   'snapshot_paths':scoped_paths('control/user_snapshot*'),
   'first_stage_d_pins':['control/'+name+'_0_s0/D' for name in ['request_sync','ack_sync','cal_sync','busy_sync','fault_sync']],
   'note':'Only first synchronizer D pins exempt; later stages and same-domain logic remain timed.'},
 'fmax_mhz':{name:fmax(name) for name in ['sys27','memory324','user81']},
 'worst_setup':worst_path('Setup Paths Table'),'worst_hold':worst_path('Hold Paths Table'),
 'worst_recovery':worst_path('Recovery Paths Table'),'worst_removal':worst_path('Removal Paths Table'),
 'remaining_negative_recovery_paths':negative_paths('Recovery Paths Table'),
 'remaining_negative_hold_paths':negative_paths('Hold Paths Table'),
 'summary_note':'Tool setup-violated endpoint summary includes recovery; normal data setup and recovery are reported separately here.',
 'fmax_note':'same-domain summary does not qualify cross-domain or external DDR IO timing',
 'logic_used':int(re.search(r'Logic\s+\|\s+(\d+)/',report).group(1)),
 'registers_used':int(re.search(r'Register\s+\|\s+(\d+)/',report).group(1)),
 'inputs':[artifact(p) for p in inputs],
 'outputs':[artifact(pnr/name) for name in ['mem_bist.fs','mem_bist.rpt.txt','mem_bist_tr_content.html','mem_bist.pin.html']],
 'simulation':json.loads((root/'build/mem-tests/results.json').read_text()),
}
if args.scoped:
    result['vendor_input_qualification']=json.loads((root/'build/mem-bist-scoped-input/qualification.json').read_text())
    result['inputs'].append(artifact(root/'build/mem-bist-scoped-input/mem_bist.sdc'))
dest=root/('validation/mem-bist-scoped-prehardware-2026-11-04.json' if args.scoped else 'validation/mem-bist-prehardware-2026-11-04.json')
dest.write_text(json.dumps(result,indent=2)+'\n')
print(dest)
