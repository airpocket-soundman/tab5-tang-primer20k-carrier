"""r5l: assembly drawing (reference designators on the F.Fab layer) as SVG (KiCad python).

Same idea as the r4 export: a temporary copy of the board shows one reference per part and no values;
DNP parts are crossed out. Writes order/assembly-top.svg only. Run:
  "C:/Program Files/KiCad/10.0/bin/python.exe" export_assembly.py
"""
import subprocess, sys, tempfile
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
ORDER = K.parents[2] / 'order'
PCB = K / 'tab5-fpga-carrier-r5l.kicad_pcb'
CLI = Path(sys.executable).parent / 'kicad-cli.exe'
mm = pcbnew.FromMM
with tempfile.TemporaryDirectory(prefix='r5l-assembly-') as td:
    b = pcbnew.LoadBoard(str(PCB))
    for f in b.GetFootprints():
        f.Value().SetLayer(pcbnew.Dwgs_User)
        r = f.Reference()
        r.SetVisible(True)
        r.SetLayer(pcbnew.B_Fab if f.IsFlipped() else pcbnew.F_Fab)
        r.SetPosition(f.GetPosition())
        r.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
        r.SetTextSize(pcbnew.VECTOR2I(mm(0.65), mm(0.65)))
        r.SetTextThickness(mm(0.10))
        for item in f.GraphicalItems():
            if item.GetClass() in ('PCB_TEXT', 'PCB_FIELD'):
                item.SetLayer(pcbnew.Dwgs_User)
    tmp = Path(td) / 'assembly.kicad_pcb'
    pcbnew.SaveBoard(str(tmp), b)
    subprocess.run([str(CLI), 'pcb', 'export', 'svg', '-l', 'F.Fab,Edge.Cuts', '--mode-single', '--black-and-white',
                    '--fit-page-to-board', '--exclude-drawing-sheet', '--crossout-DNP-footprints-on-fab-layers',
                    '-o', str(ORDER / 'assembly-top.svg'), str(tmp)], check=True)
print('wrote', ORDER / 'assembly-top.svg')
