from pathlib import Path
import json
import subprocess
import sys
H=Path(__file__).resolve().parent;ROOT=H.parents[2]
KI=Path('C:/Program Files/KiCad/10.0/bin')
variants=sys.argv[1:] or ['lite-a-dual','lite-b-barrel','lite-c-dnp']
rows=[]
for v in variants:
    k=ROOT/'variants'/v/'kicad'
    commands=[
      [sys.executable,str(k/'gen/make_sch.py')],
      [sys.executable,str(k/'gen/make_bom.py'),'--offline'],
      [str(KI/'python.exe'),str(k/'sim/check_parallel_power.py')],
      [str(KI/'kicad-cli.exe'),'pcb','drc','--format','json','--severity-all','-o',str(k/'sim/drc_r3.json'),str(k/'tab5-fpga-carrier.kicad_pcb')],
      [str(KI/'kicad-cli.exe'),'sch','erc','--format','json','--severity-error','-o',str(k/'sim/erc_errors.json'),str(k/'tab5-fpga-carrier.kicad_sch')]]
    for args in commands:
        result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if result.returncode:
            print(result.stdout,result.stderr);raise RuntimeError(args)
    drc=json.loads((k/'sim/drc_r3.json').read_text(encoding='utf-8'))
    erc=json.loads((k/'sim/erc_errors.json').read_text(encoding='utf-8'))
    check=json.loads((k/'sim/parallel_power_check.json').read_text(encoding='utf-8'))
    assert not drc['violations'] and not drc['unconnected_items'],drc['violations']
    assert not any(s['violations'] for s in erc['sheets'])
    assert check['ok']
    rows.append({'variant':v,'DRC_violations':0,'unconnected':0,'ERC_errors':0,'parallel_power_checks_passed':len(check['checks']),'series_ohm':680})
(H/('sync-'+variants[0]+'.json')).write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
