"""Export fitted carrier component body envelopes from actual KiCad files."""
from pathlib import Path
import json
import pcbnew

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
boards=[];results={}
def mm(v):return pcbnew.ToMM(v)
for variant in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
    path=ROOT/'variants'/variant/'kicad/tab5-fpga-carrier.kicad_pcb'
    board=pcbnew.LoadBoard(str(path));boards.append(board)
    parts=[]
    for f in board.GetFootprints():
        name=str(f.GetFPID().GetLibItemName())
        shapes=[s for s in f.GraphicalItems() if s.GetClass()=='PCB_SHAPE' and s.GetLayer()==pcbnew.F_Fab]
        if shapes:
            boxes=[s.GetBoundingBox() for s in shapes]
            bbox=[min(mm(b.GetLeft()) for b in boxes),min(mm(b.GetTop()) for b in boxes),max(mm(b.GetRight()) for b in boxes),max(mm(b.GetBottom()) for b in boxes)]
        else:
            b=f.GetBoundingBox(False);bbox=[mm(b.GetLeft()),mm(b.GetTop()),mm(b.GetRight()),mm(b.GetBottom())]
        parts.append(dict(ref=f.GetReference(),value=f.GetValue(),footprint=name,dnp=f.IsDNP(),back=f.IsFlipped(),body_xy_mm=bbox,origin_mm=[mm(f.GetPosition().x),mm(f.GetPosition().y)]))
    results[variant]=parts
(OUT/'carrier_geometry.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print({k:len(v) for k,v in results.items()})
