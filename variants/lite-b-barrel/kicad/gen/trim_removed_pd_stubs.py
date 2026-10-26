"""Prune only DRC-reported dangling VIN copper after deleting PD OR branch."""
from pathlib import Path
import json
import subprocess
import sys
import pcbnew

HERE=Path(__file__).resolve().parent
PCB=HERE.parent/'tab5-fpga-carrier.kicad_pcb'
REPORT=HERE.parent/'sim/drc_r3.json'
CLI=Path(sys.executable).parent/'kicad-cli.exe'
removed=[]
for iteration in range(30):
    subprocess.run([str(CLI),'pcb','drc','--format','json','--severity-all','-o',str(REPORT),str(PCB)],check=True,stdout=subprocess.DEVNULL)
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    assert not report['unconnected_items'],'PD deletion disconnected retained circuitry'
    targets={i['uuid'] for v in report['violations'] if v['type'] in ('track_dangling','via_dangling') for i in v['items']}
    if not targets:break
    b=pcbnew.LoadBoard(str(PCB));keep=[]
    for item in list(b.GetTracks()):
        if item.m_Uuid.AsString() not in targets:continue
        assert item.GetNetname()=='VIN','Only PD-deletion VIN branch pruning is allowed'
        keep.append(item);removed.append({'uuid':item.m_Uuid.AsString(),'net':item.GetNetname()});b.RemoveNative(item)
    assert keep
    pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(PCB),b)
else:raise RuntimeError('PD stub pruning did not converge')
assert not report['violations'],report['violations']
(HERE.parent/'sim/pd-stub-pruning.json').write_text(json.dumps({'removed':removed,'final_DRC_violations':0,'final_unconnected':0},indent=2)+'\n')
print('B DRC 0 / unconnected 0; removed VIN dangling objects',len(removed))
