"""Generate the KiCad PCB (placement, nets, outline, planes, power tracks, signal routing).

Run with KiCad's bundled python:
  "C:/Program Files/KiCad/10.0/bin/python.exe" kicad/gen/make_pcb.py
"""
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design  # noqa: E402

PRJ = os.path.abspath(os.path.join(HERE, ".."))
FPDIR = "C:/Program Files/KiCad/10.0/share/kicad/footprints/"
mm = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def fp_path(libname):
    if libname == "carrier":
        return os.path.join(PRJ, "lib", "carrier.pretty")
    return FPDIR + libname + ".pretty"


class Builder:
    def __init__(self):
        self.board = pcbnew.BOARD()
        self.board.SetCopperLayerCount(4)
        self.board.GetDesignSettings().SetAuxOrigin(V(28.0,79.0))
        self.nets = {}
        self.fps = {}

    # ---------------------------------------------------------------- nets
    def net(self, name):
        if name not in self.nets:
            ni = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(ni)
            self.nets[name] = ni
        return self.nets[name]

    # ---------------------------------------------------------------- outline
    def outline(self):
        x0, y0, x1, y1 = design.BOARD
        r = 3.0
        L = pcbnew.Edge_Cuts

        def line(a, b):
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(L)
            s.SetStart(V(*a))
            s.SetEnd(V(*b))
            s.SetWidth(mm(0.1))
            self.board.Add(s)

        def arc(c, start, mid_ang):
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_ARC)
            s.SetLayer(L)
            a0 = math.radians(mid_ang)
            sx, sy = c[0] + r * math.cos(a0 - math.pi / 4), c[1] + r * math.sin(a0 - math.pi / 4)
            mx, my = c[0] + r * math.cos(a0), c[1] + r * math.sin(a0)
            ex, ey = c[0] + r * math.cos(a0 + math.pi / 4), c[1] + r * math.sin(a0 + math.pi / 4)
            s.SetArcGeometry(V(sx, sy), V(mx, my), V(ex, ey))
            s.SetWidth(mm(0.1))
            self.board.Add(s)

        line((x0 + r, y0), (x1 - r, y0))
        line((x1, y0 + r), (x1, y1 - r))
        line((x1 - r, y1), (x0 + r, y1))
        line((x0, y1 - r), (x0, y0 + r))
        arc((x1 - r, y0 + r), None, -45)
        arc((x1 - r, y1 - r), None, 45)
        arc((x0 + r, y1 - r), None, 135)
        arc((x0 + r, y0 + r), None, 225)

    # ---------------------------------------------------------------- footprints
    def pose(self, fp, c, x, y, rot):
        pos = V(x, y)
        fp.SetPosition(pos)
        if c.side == "B" and not fp.IsFlipped():
            fp.Flip(pos, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pos)

    def create(self, c):
        lib, name = c.fp.split(":")
        fp = pcbnew.FootprintLoad(fp_path(lib), name)
        if fp is None:
            raise RuntimeError("footprint not found " + c.fp)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        self.board.Add(fp)
        self.pose(fp, c, c.pos[0], c.pos[1], c.rot)
        if c.dnp:
            fp.SetDNP(True)
        pins = c.pads if c.pads is not None else c.pins
        for pad in fp.Pads():
            num = pad.GetNumber()
            net = None
            if num in pins:
                net = pins[num]
            elif num == "MP" or (num == "SH"):
                net = "GND"
            elif num == "" and not pad.IsOnCopperLayer():
                continue
            if net:
                pad.SetNet(self.net(net))
        self.fps[c.ref] = fp
        return fp

    # ---------------------------------------------------------------- tracks / vias
    def track(self, net, layer, pts, width=0.25):
        lid = self.board.GetLayerID(layer)
        for a, b in zip(pts[:-1], pts[1:]):
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(V(*a))
            t.SetEnd(V(*b))
            t.SetWidth(mm(width))
            t.SetLayer(lid)
            t.SetNet(self.net(net))
            self.board.Add(t)

    def via(self, net, x, y, dia=0.6, drill=0.3):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(V(x, y))
        v.SetWidth(mm(dia))
        v.SetDrill(mm(drill))
        v.SetNet(self.net(net))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        self.board.Add(v)

    # ---------------------------------------------------------------- zones
    def zone(self, net, layer, rect=None):
        x0, y0, x1, y1 = rect or (design.BOARD[0] + 0.3, design.BOARD[1] + 0.3, design.BOARD[2] - 0.3,
                                  design.BOARD[3] - 0.3)
        z = pcbnew.ZONE(self.board)
        z.SetLayer(self.board.GetLayerID(layer))
        z.SetNet(self.net(net))
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(mm(x), mm(y))
        z.SetMinThickness(mm(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefSpokeWidth(mm(0.3))
        z.SetThermalReliefGap(mm(0.2))
        z.SetLocalClearance(mm(0.25))
        self.board.Add(z)
        return z

    def fill(self):
        filler = pcbnew.ZONE_FILLER(self.board)
        filler.Fill(self.board.Zones())

    def save(self, path):
        pcbnew.SaveBoard(path, self.board)


def write_pro():
    path = os.path.join(PRJ, design.PROJECT + ".kicad_pro")
    pro = {"meta": {"filename": design.PROJECT + ".kicad_pro", "version": 3},
           "board": {"design_settings": {"rules": {"min_clearance": 0.127, "min_track_width": 0.127,
                                                   "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
                                                   "min_via_annular_width": 0.1, "min_copper_edge_clearance": 0.3,
                                                   "min_hole_to_hole": 0.25, "min_hole_clearance": 0.25}}},
           "net_settings": {"classes": [{"name": "Default", "clearance": 0.127, "track_width": 0.127,
                                         "via_diameter": 0.6, "via_drill": 0.3, "diff_pair_width": 0.2,
                                         "diff_pair_gap": 0.2, "diff_pair_via_gap": 0.25, "wire_width": 6,
                                         "bus_width": 12, "line_style": 0, "microvia_diameter": 0.3,
                                         "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
                                         "schematic_color": "rgba(0, 0, 0, 0.000)"}],
                            "meta": {"version": 3}, "net_colors": None, "netclass_assignments": None,
                            "netclass_patterns": []}}
    json.dump(pro, open(path, "w", encoding="utf-8"), indent=2)


def main(route=True):
    b = Builder()
    comps = design.build()
    # Stage D1 bias parts outside the narrow post-ESD gaps while the coarse
    # router runs; move only their branches to the final DRC-checked layout.
    import shorten_d1_bias
    route_comps = shorten_d1_bias.routing_components(comps) if route else comps
    b.outline()
    for c in route_comps:
        b.create(c)
    import place_pcb
    place_pcb.run(b, route_comps)
    out = os.path.join(PRJ, design.PROJECT + ".kicad_pcb")
    if route:
        import route_pcb
        route_pcb.run(b, route_comps)
        shorten_d1_bias.apply(b.board)
    for layer in ("In1.Cu", "In2.Cu", "F.Cu", "B.Cu"):
        z = b.zone("GND", layer)
        if layer != "In1.Cu":
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        if layer in ("F.Cu", "B.Cu"):
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    b.fill()
    b.save(out)
    write_pro()
    print("saved", out, "footprints", len(comps), "nets", len(b.nets))


if __name__ == "__main__":
    if '--experimental-full-route' in sys.argv:
        main(route=True)
    elif '--noroute' in sys.argv:
        main(route=False)
    else:
        # Preserve the qualified essential routing. A full route is experimental;
        # the final reviewed HDMI stage is the default reproducible release path.
        import subprocess
        from pathlib import Path
        root=Path(__file__).resolve().parents[4]
        variant=Path(__file__).resolve().parents[2].name
        py='C:/Program Files/KiCad/10.0/bin/python.exe'
        subprocess.run([py,'-X','utf8',str(root/'variants/simulation/hdmi/prepare_hdmi_cad.py'),variant],check=True)
        subprocess.run(['python','-X','utf8',str(root/'variants/simulation/hdmi/adopt_hdmi_cad.py'),variant],check=True)
