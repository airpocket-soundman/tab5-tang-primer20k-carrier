"""Independent source-model vs physical KiCad pad audit (run with KiCad Python)."""
from pathlib import Path
import hashlib,json
import pcbnew
K=Path(__file__).resolve().parents[1];H=K.parents[2]
def main():
    b=pcbnew.LoadBoard(str(K/'tab5-fpga-carrier-r5s.kicad_pcb'))
    contract=json.loads((K/'circuit-contract.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()}
    assert set(fps)==set(contract),set(fps)^set(contract)
    count=0
    for ref,c in contract.items():
        pads={}
        for p in fps[ref].Pads():pads.setdefault(p.GetNumber(),set()).add(p.GetNetname())
        assert fps[ref].GetValue()==c['value'],(ref,'value')
        assert fps[ref].IsDNP()==c['dnp'],(ref,'DNP')
        for num,net in c['pins'].items():
            if net is None:assert all(not v or v.startswith('unconnected-') for v in pads.get(num,set())),(ref,num,pads.get(num))
            else:
                assert pads.get(num)=={net},(ref,num,net,pads.get(num));count+=1
    r4=pcbnew.LoadBoard(str(H.parent/'single-sided-r4/full/design/kicad/tab5-fpga-carrier.kicad_pcb'))
    orig={f.GetReference():f for f in r4.GetFootprints()}
    for ref in ('J1','J3','J4','J5','J6','J7','J8'):
        assert fps[ref].GetPosition()==orig[ref].GetPosition(),(ref,'pose')
        assert fps[ref].GetOrientationDegrees()==orig[ref].GetOrientationDegrees(),(ref,'angle')
    changes={'143':'JTAG_TMS','147':'JTAG_TDO','149':'JTAG_TCK','153':'JTAG_TDI'}
    for ref in ('J3','J4'):
        before={p.GetNumber():p.GetNetname() for p in orig[ref].Pads()}
        after={p.GetNumber():p.GetNetname() for p in fps[ref].Pads()}
        for pin,net in before.items():
            if ref=='J3' and pin in ('25','27','29'):assert after[pin]=='TAB_HVIN'
            elif ref=='J4' and pin in changes:
                assert not net and after[pin]==changes[pin],(pin,'JTAG must replace r4NC only')
            else:assert after[pin]==net,(ref,pin,net,after[pin])
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    report={'date':'2026-11-03','variant':'manual-jumpers-direct-SODIMM-JTAG','components':len(fps),'connected_source_pins_checked':count,
      'schematic_to_PCB':'PASS','host_signal_pins':'r4 unchanged','Core_reserved_JTAG_pins':changes,'cable_required':False,
      'preserved_mating_poses':['J1','J3','J4','J5','J6','J7','J8'],'board_copper_layers':b.GetCopperLayerCount(),
      'files':{p.name:sha(p) for p in [K/'tab5-fpga-carrier-r5s.kicad_sch',K/'tab5-fpga-carrier-r5s.kicad_pcb',K/'bom-r5s.csv']}}
    (K/'sim/pin-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
