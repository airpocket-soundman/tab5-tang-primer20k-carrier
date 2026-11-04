"""Finite protocol-guarded vendor exceptions; no broad clock groups/reset waivers.

Preserves original unwaived/scoped20 source and output evidence.
"""
from pathlib import Path
import re,json,hashlib
root=Path(__file__).resolve().parents[2]
mailbox=(root/'mem/rtl/mem_mailbox.v').read_text()
assert 'always @(posedge user_clk or negedge sys_reset_n)' in mailbox
assert 'always @(posedge user_clk or negedge epoch_reset_sync[2])' in mailbox
assert 'if(!epoch_reset_sync[2])user_epoch_used<=0;' in mailbox
assert 'bootstrap_count<31' in mailbox and 'epoch_reset_sync[2]&&!user_epoch_used' in mailbox
assert 'user_epoch_pulse' not in mailbox
assert 'user_epoch' not in '\n'.join(line for line in (root/'mem/config/mem_bist.sdc').read_text().splitlines() if line.startswith('set_false_path'))
import os
TAG=os.environ.get('MEM_IP_TAG','');SFX=('-'+TAG) if TAG else ''
BASE_SDC=root/('mem/config/mem_bist.sdc' if not TAG else f'mem/config/mem_bist_{TAG}.sdc')
vo=root/f'build/mem-bist-ip{SFX}/generated/MemDDR3/MemDDR3.vo'
text=vo.read_text();cells={}
for m in re.finditer(r'^(\w+) \\([^\n]+?)\s+\(\n(.*?)^\);',text,re.M|re.S):
 cells['controller/'+m[2].strip().replace('/','_')]=(m[1],m[3])
proof=json.loads((root/f'build/mem-tests{SFX}/results.json').read_text())
cone=next(t for t in proof['tests'] if t['name']=='vendor_clock_init_cone')
assert 'PASS vendor initialization model' in cone['output']
assert cone['projection']['generated_source_sha256']==hashlib.sha256(vo.read_bytes()).hexdigest()
entries=[]
for e in json.loads((root/'mem/config/vendor_async_review.json').read_text())['exceptions']:
 cell,port=e['pin'].rsplit('/',1);kind,body=cells[cell]
 assert re.search(r'\.'+port+r'\(',body)
 assert (kind,port) in [('DHCEN','CE'),('DQS','HOLD'),('IDES8_MEM','CALIB'),('DFFC','D')]
 entries.append(dict(e,primitive=kind,analysis='both',group='async20'))
assert len(entries)==20
prefix='controller/gw3_top_u_ddr_phy_top_'
for bit in range(8):
 pin=prefix+f'dll_step_base_{bit}_s0/D';kind,body=cells[pin.rsplit('/',1)[0]]
 assert kind=='DFFCE' and re.search(r'\.D\(\\gw3_top/u_ddr_phy_top/dll_step \['+str(bit)+r'\]\)',body)
 assert '.CE(\\gw3_top/u_ddr_phy_top/n1426_3 )' in body
 entries.append({'pin':pin,'primitive':kind,'analysis':'hold','group':'step8',
 'reason':'one-shot initialization CE, LOCK and held STEP; non-vacuous116-cell cone contract'})
pin=prefix+'wloadn_1_s0/D';kind,body=cells[pin.rsplit('/',1)[0]]
assert kind=='DFFC' and '.D(\\gw3_top/u_ddr_phy_top/ddr_init_internal_r )' in body
entries.append({'pin':pin,'from':prefix+'ddr_init_internal_r_s0/Q','primitive':kind,'analysis':'hold','group':'wload1',
 'reason':'sticky init-complete level to asynchronous DQS WLOADN;256SYS calibrated/no-native-traffic guard'})
baseline=json.loads((root/'validation/mem-bist-scoped-prehardware-2026-11-04.json').read_text())
reset_pins=sorted(set(e['to'] for e in baseline['remaining_negative_recovery_paths']))
assert len(reset_pins)==61
counts={}
for pin in reset_pins:
 assert pin.startswith('controller/') and pin.endswith('/RESET')
 kind,body=cells[pin.rsplit('/',1)[0]]
 assert kind in ['OSER8','OSER8_MEM','IDES8_MEM','DQS'] and '.RESET(' in body
 counts[kind]=counts.get(kind,0)+1
 entries.append({'pin':pin,'primitive':kind,'analysis':'setup','group':'reset61',
 'reason':'initialization-only asynchronous RESET recovery; calibration reestablishes alignment before256SYS-guarded native traffic; removal remains timed'})
assert counts=={'OSER8':23,'OSER8_MEM':20,'IDES8_MEM':16,'DQS':2},counts
assert len(entries)==90 and len(set(e['pin'] for e in entries))==90
out=root/f'build/mem-scheduler-diag-input{SFX}';out.mkdir(parents=True,exist_ok=True)
extra='\n//90 finite guarded primitive input endpoints; no clock groups.\n'
for e in entries:
 line='set_false_path '
 if e['analysis']!='both':line+='-'+e['analysis']+' '
 if 'from' in e:line+='-from [get_pins {'+e['from']+'}] '
 extra+=line+'-to [get_pins {'+e['pin']+'}]\n'
(out/'mem_bist.sdc').write_text(BASE_SDC.read_text()+extra)
record={'scope':'finite guarded internal timing exceptions; NOT physical DDR proof',
 'resolved_unique_endpoints':90,'groups':{'async20':20,'step8':8,'wload1':1,'reset61':61},
 'reset_primitive_counts':counts,'reset_removal_checks_waived':False,
 'endpoints':entries,'generated_vo_sha256':hashlib.sha256(vo.read_bytes()).hexdigest(),
 'combined_sdc_sha256':hashlib.sha256((out/'mem_bist.sdc').read_bytes()).hexdigest(),
 'clock_cone_proof':cone,
 'owned_USER_epoch_retention':'USER used-marker reset only by SYS epoch through USER-synchronized reset release;32USER-cycle bootstrap; no owned reset timing waiver',
 'owned_reset_timing_exceptions':[],
 'mailbox_source_sha256':hashlib.sha256((root/'mem/rtl/mem_mailbox.v').read_bytes()).hexdigest(),
 'guard_defaults':{'calibration_stable_SYS_cycles':256,'USER_heartbeat_cycles':256,'SYS_no_heartbeat_cycles':27000,'USER_bootstrap_cycles':32}}
(out/'qualification.json').write_text(json.dumps(record,indent=2)+'\n')
print('PASS90 unique qualified endpoints:20async +8STEP hold +1WLOADN hold +61RESET recovery; no reset removal exception')
