"""Explicit scratch benchmark: same ELF, workload and sample count, cumulative options."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser()
p.add_argument('--host',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--elf',required=True)
p.add_argument('--port',default='COM4')
p.add_argument('--iterations',type=int,default=1000)
p.add_argument('--execute',action='store_true')
a=p.parse_args()
if not a.execute or not 1<=a.iterations<=10000:p.error('Explicit --execute and iterations1..10000 required')
sys.path.insert(0,str(a.host/'tools'))
from gpu_lab import Client
import serial.tools.list_ports
assert any(x.device==a.port and x.serial_number=='30:ED:A0:E2:FE:C0' for x in serial.tools.list_ports.comports())
a.out.mkdir(parents=True,exist_ok=True)
summary=a.out/'cumulative-summary.json'
if summary.exists():raise RuntimeError('Existing summary: refuse overwrite')
cases=[]
case=dict(slots=0,tx_hz=5000000,rx_hz=5000000,guard_us=200)
for label,change in [('BASE',{}),('GUARD2',dict(guard_us=2)),('RXREUSE',dict(retain=True)),('2SLOTS',dict(slots=2)),('TXREUSE',dict(full_apb_restore_tx=True)),('8MHz',dict(tx_hz=8000000,rx_hz=8000000)),('+GUARDS',dict(compact_restore_guard=True)),('+PACK',dict(fast_tx_pack=True)),('+RXOWN',dict(dma_owned_rx=True)),('+RAMCRC',dict(ram_crc=True))]:
    case={**case,**change};cases.append(dict(label=label,options=case))
report=dict(scope='Same ELF/workload/count; each row retains every preceding option. 4KiB per WR/RD request. Job includes ARM/prep/validation/drain/cleanup; USB/LCD excluded. Historical early firmware is not reconstructed.',elf=a.elf,iterations=a.iterations,rows=[])
def display(label,step,options,result='RUNNING',us=0):
    c=Client(a.port)
    try:
        i=c.call('info');assert i['app_elf_sha256']==a.elf and not i['link_armed']
        c.call('mem',action='xferx_mode',mode='dma',tx_hz=options['tx_hz'],rx_hz=options['rx_hz'],tx_phase='negative',tx_preamble=1,sample_edge='positive',guard_us=options['guard_us'])
        return c.call('mem',action='display',test_name='DMA CUMULATIVE PER REQUEST',stage=label,step=step,total=len(cases),result=result,transfer_us=us)
    finally:c.close()
try:
    boot=None
    for index,c in enumerate(cases):
        o=c['options'];file=a.out/f'{index:02d}-{c["label"].replace("+","").lower()}.json'
        display(c['label'],index,o)
        cmd=[sys.executable,str(a.host/'tools/mem_dma_pipeline_bench.py'),'--port',a.port,'--expected-elf-sha',a.elf,'--iterations',str(a.iterations),'--workload','write_read','--execute','--record',str(file)]
        for key,value in o.items():
            cmd.append('--'+key.replace('_','-'))
            if not isinstance(value,bool):cmd.append(str(value))
        subprocess.run(cmd,check=True,cwd=a.host)
        data=json.loads(file.read_text(encoding='utf-8'));assert data['result']=='PASS';s=data['runs'][0]['final']
        assert s['completed']==a.iterations*2 and s['prepared']==s['completed'] and not s['cleanup_quarantined']
        assert s['tx_callback_count']==s['rx_callback_count']==s['completed']
        if boot is None:boot=s['boot_id']
        assert s['boot_id']==boot
        n=s['completed'];cpu=s['producer_runtime_counter']+s['consumer_runtime_counter']
        row=dict(label=c['label'],options=o,record=file.name,job_id=s['job_id'],completed=n,ms_per_request=s['job_wall_us']/n/1000,MBps=s['job_MBps'],worker_cpu_ms_per_request=cpu/n/1000,tx_api_ms=s['write_transfer_total_us']/s['write_transfer_count']/1000,rx_api_ms=s['read_transfer_total_us']/s['read_transfer_count']/1000)
        if report['rows']:
            prev=report['rows'][-1];base=report['rows'][0]
            row.update(speed_gain_pct=(row['MBps']/prev['MBps']-1)*100,saved_ms_per_request=prev['ms_per_request']-row['ms_per_request'],worker_cpu_change_pct=(row['worker_cpu_ms_per_request']/prev['worker_cpu_ms_per_request']-1)*100,cumulative_speed_gain_pct=(row['MBps']/base['MBps']-1)*100,cumulative_saved_ms_per_request=base['ms_per_request']-row['ms_per_request'])
        report['rows'].append(row)
        display(f'{c["label"]} {row["ms_per_request"]:.3f}ms/req',index+1,o,'PASS',round(s['job_wall_us']/n))
        print(json.dumps(row),flush=True)
    report['result']='PASS'
except BaseException as e:report.update(result='FAIL',error=repr(e));raise
finally:summary.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
