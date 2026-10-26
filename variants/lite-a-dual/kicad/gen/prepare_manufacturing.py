"""Finish manufacturing graphics without disabling DRC checks (KiCad Python)."""
import json,subprocess,tempfile,sys
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[2]
PCB=ROOT/'kicad/tab5-fpga-carrier.kicad_pcb'
CLI=Path(sys.executable).parent/'kicad-cli.exe'

def main():
    b=pcbnew.LoadBoard(str(PCB))
    for t in list(b.GetTracks()):
        if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()=='GND' and (t.GetPosition()-pcbnew.VECTOR2I(pcbnew.FromMM(10.1),pcbnew.FromMM(22.4))).EuclideanNorm()<1000:
            b.RemoveNative(t) # redundant stitch: 0.20mm drill spacing to neighbour
    pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(PCB),b)
    with tempfile.TemporaryDirectory(prefix='carrier-silk-') as td:
        report=Path(td)/'drc.json'
        subprocess.run([str(CLI),'pcb','drc','--severity-all','--format','json','-o',str(report),str(PCB)],check=True)
        d=json.loads(report.read_text(encoding='utf8'))
        ids={i['uuid'] for v in d['violations'] if v['type'] in ('silk_overlap','silk_over_copper') for i in v['items']}
        objects=list(b.GetDrawings())
        for f in b.GetFootprints():objects.extend([f.Reference(),f.Value()]+list(f.GraphicalItems()))
        for item in objects:
            if item.m_Uuid.AsString() in ids and item.GetLayer() in (pcbnew.F_SilkS,pcbnew.B_SilkS):
                item.SetLayer(pcbnew.F_Fab if item.GetLayer()==pcbnew.F_SilkS else pcbnew.B_Fab)
        pcbnew.SaveBoard(str(PCB),b)
if __name__=='__main__':main()
