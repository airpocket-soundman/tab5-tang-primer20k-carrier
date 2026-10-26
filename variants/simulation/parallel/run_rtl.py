from pathlib import Path
import hashlib
import json
import subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
GPU=ROOT.parent/'tab5-fpga-gpu/bringup'
EXE=Path('D:/tmp/carrier-iverilog/extracted/app/bin')
RAW=Path('D:/tmp/carrier-parallel-models');RAW.mkdir(exist_ok=True)
rtl=[GPU/'rtl/link_bringup.v',GPU/'rtl/link_bus_wrapper.v']
out=RAW/'speed.vvp'
subprocess.run([str(EXE/'iverilog.exe'),'-g2012','-s','tb_link_speed','-o',str(out),*map(str,rtl),str(HERE/'tb_link_speed.v')],check=True)
results=[]
for hz in (1000000,2000000,3000000,4000000,5000000,10000000,20000000,40000000):
    for phase in range(0,37000,1000):
        run=subprocess.run([str(EXE/'vvp.exe'),str(out),'+HZ='+str(hz),'+PHASE_PS='+str(phase)],capture_output=True,text=True,timeout=30)
        results.append({'bus_Hz':hz,'phase_ps':phase,'ok':run.returncode==0 and 'PASS speed' in run.stdout,'output':run.stdout.strip()[:500]})
    print(hz,'passed',sum(r['ok'] for r in results if r['bus_Hz']==hz),'/37',flush=True)
base=RAW/'base-link.vvp'
subprocess.run([str(EXE/'iverilog.exe'),'-g2012','-s','tb_link_bringup','-o',str(base),str(rtl[0]),str(GPU/'tests/tb_link_bringup.v')],check=True)
r=subprocess.run([str(EXE/'vvp.exe'),str(base)],capture_output=True,text=True,check=True)
report={'system_clock_Hz':27000000,'turnaround_guard_ns':500,'data_flight_delay_ns':100,'clock_flight_delay_ns':100,'DIR_flight_delay_ns':100,'delay_basis':'Conservative complete 5%-settling envelope from 680ohm corrected-capacitance distributed-RLC model, rounded upward; deliberately more than pure wave-flight time','phase_cases':37,'results':results,'existing_regression_100MHz':r.stdout.strip(),'source_sha256':{str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl},'scope':'Actual portable bringup RTL, not board top, PARLIO DMA or DDR3 controller. No setup/hold aperture/metastability analogue model is included. Speed failures are retained.'}
(HERE/'rtl-results.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(r['ok'] for r in results if r['bus_Hz']==1000000)
