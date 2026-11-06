"""Print the drill/place (aux) origin and board outline of the r5l PCB (KiCad python)."""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
b = pcbnew.LoadBoard(str(K / 'tab5-fpga-carrier-r5l.kicad_pcb'))
o = b.GetDesignSettings().GetAuxOrigin()
print('aux origin mm', pcbnew.ToMM(o.x), pcbnew.ToMM(o.y))
bb = b.GetBoardEdgesBoundingBox()
print('outline mm', pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
print('copper layers', b.GetCopperLayerCount())
