"""Minimum250ns DATA hold with independent0/100ns data/clock skew."""
from pathlib import Path
import json
import subprocess
H=Path(__file__).resolve().parent;ROOT=H.parents[2];GPU=ROOT.parent/'tab5-fpga-gpu/bringup'
EXE=Path('D:/tmp/carrier-iverilog/extracted/app/bin');RAW=Path('D:/tmp/carrier-parallel-models');rows=[]
for data_delay,clock_delay in ((0,100),(100,0)):
    out=RAW/f'skew-{data_delay}-{clock_delay}.vvp'
    subprocess.run([str(EXE/'iverilog.exe'),'-g2012','-s','tb_link_speed',f'-Ptb_link_speed.DATA_DELAY={data_delay}',f'-Ptb_link_speed.CLOCK_DELAY={clock_delay}','-o',str(out),str(GPU/'rtl/link_bringup.v'),str(GPU/'rtl/link_bus_wrapper.v'),str(H/'tb_link_speed.v')],check=True)
    for phase in range(0,37000,1000):
        r=subprocess.run([str(EXE/'vvp.exe'),str(out),'+HZ=1000000',f'+PHASE_PS={phase}'],capture_output=True,text=True,timeout=30)
        rows.append({'data_delay_ns':data_delay,'clock_delay_ns':clock_delay,'DIR_delay_ns':100,'DATA_hold_ns':250,'turnaround_guard_ns':500,'phase_ps':phase,'ok':r.returncode==0 and 'PASS speed' in r.stdout,'output':r.stdout.strip()[:400]})
    print(data_delay,clock_delay,'pass',sum(r['ok'] for r in rows if r['data_delay_ns']==data_delay),'/37',flush=True)
(H/'rtl-skew-results.json').write_text(json.dumps({'system_clock_Hz':27000000,'bus_clock_Hz':1000000,'results':rows,'scope':'Actual portableRTL; independent worst data/clock path skew and exact minimum250ns DATA hold. No analogue metastability model.'},indent=2)+'\n')
assert all(r['ok'] for r in rows)
