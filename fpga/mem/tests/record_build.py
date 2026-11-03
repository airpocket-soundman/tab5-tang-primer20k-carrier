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
parser.add_argument('--guarded',action='store_true')
args=parser.parse_args()
assert not(args.scoped and args.guarded)
stem='mem-deep-diag' if args.guarded else 'mem-bist-scoped' if args.scoped else 'mem-bist-official'
pnr=root/f'build/{stem}/mem_bist/impl/pnr'
console=root/f'build/{stem}-console.log'
log=console.read_text()
assert 'MEM_BUILD_FLOW_RETURNED' in log and not re.search(r'ERROR\s*\(',log), 'build failed; stale outputs must not be attested'
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
    if 'Data Delay' not in items[:16]:return None
    i=items.index('Data Delay')+1
    if items[i]!='1':return None
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
    start=t.items.index(table)
    if 'Data Delay' not in t.items[start:start+16]:return []
    i=t.items.index('Data Delay',start)+1
    paths=[]
    while t.items[i].isdigit():
        if t.items[i+1].startswith('-'):
            paths.append({'from':t.items[i+2],'to':t.items[i+3],
                          'slack_ns':float(t.items[i+1]),'from_clock':t.items[i+4],'to_clock':t.items[i+5]})
        i+=9
    return paths
inputs=sorted((root/'mem/rtl').glob('*.v'))+sorted((root/'mem/config').glob('*.tcl'))+list((root/'mem/config').glob('*.cst'))+list((root/'mem/config').glob('*.sdc'))
inputs += [root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo',root/'build/mem-deep-input/MemDDR3_tapped.vo']
active_sdc=root/('build/mem-deep-diag-input/mem_bist.sdc' if args.guarded else 'build/mem-bist-scoped-input/mem_bist.sdc' if args.scoped else 'mem/config/mem_bist.sdc')
assert (pnr/'mem_bist.rpt.txt').stat().st_mtime>=max(p.stat().st_mtime for p in inputs+[active_sdc]), 'sources changed after build; do not attest stale report'
def pin_audit():
    cst=(root/'mem/config/mem_bist.cst').read_text(encoding='utf-8-sig')
    expected=dict(re.findall(r'^IO_LOC\s+"([^"]+)"\s+([A-Z]\d+(?:,[A-Z]\d+)?)',cst,re.M))
    types=dict(re.findall(r'^IO_PORT\s+"([^"]+)"\s+IO_TYPE=(\w+)',cst,re.M))
    actual={}
    for line in report.splitlines():
        fields=[v.strip() for v in line.split('|')]
        if len(fields)>10 and re.fullmatch(r'[a-zA-Z_]\w*(?:\[\d+\])?',fields[0]):actual[fields[0]]=fields
    entries=[]
    for name,balls in expected.items():
        assert name in actual,('constrained port missing',name)
        row=actual[name];assert row[2].split('/')[0]==balls,(name,balls,row[2])
        assert row[7]==types[name],(name,types[name],row[7])
        voltage='1.5' if '15' in types[name] else '3.3'
        assert row[-1]==voltage,(name,voltage,row[-1])
        entries.append({'port':name,'balls':balls,'bank':row[2].split('/')[-1],'type':row[7],'vccio':row[-1]})
    assert 'ddr_addr[13]' not in actual
    return {'scope':'document/CST to routed pin report check; not physical board observation',
            'passed':True,'constrained_ports_checked':len(entries),'ports':entries}
result={
 'scope':'standalone MEM diagnostic; NOT hardware-approved; physical DDR unverified',
 'tool':'Gowin V1.9.11.03 Education; official CLI, no hardware programming',
 'part':'GW2A-LV18PG256C8/I7','device_version':'C',
 'configured_bytes':134217728,'physical_capacity_known':False,
 'memory_hz':324000000,'user_hz':81000000,
 'synthesis_completed':True,'placement_routing_completed':True,'bitstream_generated':True,
 'timing_qualified':False,'hardware_approved':False,
 'guarded_candidate':args.guarded,
 'sta_constraints_pass':int(following('Numbers of Setup Violated Endpoints'))==0 and int(following('Numbers of Hold Violated Endpoints'))==0,
 'setup_violated_endpoints':int(following('Numbers of Setup Violated Endpoints')),
 'hold_violated_endpoints':int(following('Numbers of Hold Violated Endpoints')),
 'remaining_review':('finite guarded90 vendor inputs; retained USER epoch/quarantine, no owned reset waiver; hardware/pin/config review mandatory' if args.guarded else 'finite20 vendor async inputs active in this separate build; remaining init/DLL paths unwaived' if args.scoped else 'vendor DDR calibration/gating and initialization crossings; finite vendor proposal NOT active; no blanket waiver applied'),
 'held_bundle_constraints':{
   'request_earliest_capture_ns':2e9/81000000,'request_max_delay_ns':20,
   'snapshot_earliest_capture_ns':3e9/27000000+1e9/81000000,'snapshot_max_delay_ns':60,
   'hold_exempt_only_for_held_bundles':True,
   'request_paths':scoped_paths('control/held_base*'),
   'snapshot_paths':scoped_paths('control/user_snapshot*'),
   'diagnostic_snapshot_paths':scoped_paths('control/user_debug_snapshot*'),
   'deep_snapshot_paths':scoped_paths('control/user_deep_snapshot*'),
   'first_stage_d_pins':['control/'+name+'_0_s0/D' for name in ['request_sync','ack_sync','cal_sync','busy_sync','fault_sync','user_ready_sync','heartbeat_sync']],
   'note':'Only first synchronizer D pins exempt; later stages and same-domain logic remain timed.'},
 'fmax_mhz':{name:fmax(name) for name in ['sys27','memory324','user81']},
 'worst_setup':worst_path('Setup Paths Table'),'worst_hold':worst_path('Hold Paths Table'),
 'worst_recovery':worst_path('Recovery Paths Table'),'worst_removal':worst_path('Removal Paths Table'),
 'remaining_negative_recovery_paths':negative_paths('Recovery Paths Table'),
 'remaining_negative_hold_paths':negative_paths('Hold Paths Table'),
 'remaining_negative_setup_paths':negative_paths('Setup Paths Table'),
 'remaining_negative_removal_paths':negative_paths('Removal Paths Table'),
 'summary_note':'Tool setup-violated endpoint summary includes recovery; normal data setup and recovery are reported separately here.',
 'fmax_note':'same-domain summary does not qualify cross-domain or external DDR IO timing',
 'logic_used':int(re.search(r'Logic\s+\|\s+(\d+)/',report).group(1)),
 'registers_used':int(re.search(r'Register\s+\|\s+(\d+)/',report).group(1)),
 'inputs':[artifact(p) for p in inputs],
 'pin_audit':pin_audit(),'console':artifact(console),
 'host_codec':artifact(root/'host/mem_protocol.h'),
 'outputs':[artifact(pnr/name) for name in ['mem_bist.fs','mem_bist.rpt.txt','mem_bist_tr_content.html','mem_bist.pin.html']],
 'simulation':json.loads((root/'build/mem-tests/results.json').read_text()),
}
if args.scoped:
    result['vendor_input_qualification']=json.loads((root/'build/mem-bist-scoped-input/qualification.json').read_text())
    result['inputs'].append(artifact(root/'build/mem-bist-scoped-input/mem_bist.sdc'))
if args.guarded:
    result['guarded_input_qualification']=json.loads((root/'build/mem-deep-diag-input/qualification.json').read_text())
    result['inputs'].append(artifact(active_sdc))
    paths=result['held_bundle_constraints']['diagnostic_snapshot_paths']
    actual_bits={int(re.search(r'sys_debug_snapshot_(\d+)_s\d+/D$',p['to']).group(1)) for p in paths}
    constant_bits=set(range(74,80))|set(range(106,112))|set(range(138,144))|set(range(170,176))
    expected_bits=set(range(176))-constant_bits
    assert actual_bits==expected_bits,('diagnostic CDC coverage gap',sorted(expected_bits-actual_bits),sorted(actual_bits-expected_bits))
    assert all(p['slack_ns']>=0 for p in paths)
    deep_paths=result['held_bundle_constraints']['deep_snapshot_paths']
    deep_actual={int(re.search(r'sys_deep_snapshot_(\d+)_s\d+/D$',p['to']).group(1)) for p in deep_paths}
    deep_expected=set(range(26))|set(range(64,161))
    assert deep_actual==deep_expected,('deep CDC coverage gap',sorted(deep_expected-deep_actual),sorted(deep_actual-deep_expected))
    assert all(p['slack_ns']>=0 for p in deep_paths)
    result['deep_CDC_coverage']={'matched_destinations':len(deep_actual),'variable_bits':sorted(deep_actual),'constant_bits':sorted(set(range(256))-deep_expected),'max_delay_ns':60,'passed':True}
    result['output_only_tap_audit']=json.loads((root/'build/mem-deep-input/tap_audit.json').read_text())
    result['native_diagnostic']=True
    result['diagnostic_CDC_coverage']={'total_bundle_bits':176,'variable_bits':sorted(actual_bits),
        'constant_zero_bits':sorted(constant_bits),'matched_destinations':len(actual_bits),
        'max_delay_ns':60,'minimum_capture_settle_ns':3e9/27000000+1e9/81000000,
        'passed':True,'normal_native_handshake_policy_changed':False}
dest=root/('validation/mem-deep-diag-prehardware-2026-11-04.json' if args.guarded else 'validation/mem-bist-scoped-prehardware-2026-11-04.json' if args.scoped else 'validation/mem-bist-prehardware-2026-11-04.json')
dest.write_text(json.dumps(result,indent=2)+'\n')
print(dest)
