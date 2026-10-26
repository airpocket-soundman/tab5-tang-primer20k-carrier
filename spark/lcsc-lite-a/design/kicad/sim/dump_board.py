"""KiCad python: dump tracks/vias/pads of the board to JSON for plotting (kicad/sim/board_dump.json)."""
import json, os, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
b = pcbnew.LoadBoard(os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb"))
mm = pcbnew.ToMM
out = {"tracks": [], "vias": [], "pads": []}
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        out["vias"].append([t.GetNetname(), mm(t.GetPosition().x), mm(t.GetPosition().y), mm(t.GetWidth(pcbnew.F_Cu))])
    else:
        out["tracks"].append([t.GetNetname(), b.GetLayerName(t.GetLayer()), mm(t.GetStart().x), mm(t.GetStart().y),
                              mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth())])
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        out["pads"].append([fp.GetReference(), p.GetNumber(), p.GetNetname(), mm(bb.GetLeft()), mm(bb.GetTop()),
                            mm(bb.GetRight()), mm(bb.GetBottom())])
json.dump(out, open(os.path.join(HERE, "board_dump.json"), "w"))
print("dumped", len(out["tracks"]), len(out["vias"]), len(out["pads"]))
