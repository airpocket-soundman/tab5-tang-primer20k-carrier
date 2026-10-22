"""Post-route touch-ups on the saved board (run with KiCad's python):
 * remove a VIN via that violates clearance to BUCK_PH when the net stays connected,
 * add a GND stitching via + stub for pads the router could not stitch,
 * refill zones and save.
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.abspath(os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb"))
mm = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def items_hit(board, x, y, acc, ignore_net=None):
    p = V(x, y)
    a = mm(acc)
    for t in board.GetTracks():
        if ignore_net and t.GetNetname() == ignore_net:
            continue
        if t.HitTest(p, a):
            return True
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if ignore_net and pad.GetNetname() == ignore_net:
                continue
            if pad.HitTest(p, a):
                return True
    return False


def segment_clear(board, a, b, acc, net):
    n = max(int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.1), 1)
    for i in range(1, n + 1):
        t = i / n
        if items_hit(board, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, acc, ignore_net=net):
            return False
    return True


def add_via(board, x, y, net):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y))
    v.SetWidth(mm(0.6))
    v.SetDrill(mm(0.3))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(net)
    board.Add(v)


def add_track(board, a, b, net, layer, w=0.2):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(*a))
    t.SetEnd(V(*b))
    t.SetWidth(mm(w))
    t.SetLayer(board.GetLayerID(layer))
    t.SetNet(net)
    board.Add(t)


def hit_f(board, x, y, acc, net="GND"):
    """Anything on F.Cu (tracks, via copper, pads) of another net within acc mm of the point?"""
    p = V(x, y)
    a = mm(acc)
    for t in board.GetTracks():
        if t.GetNetname() == net:
            continue
        if isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() == pcbnew.F_Cu:
            if t.HitTest(p, a):
                return True
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                continue
            if pad.IsOnLayer(pcbnew.F_Cu) and pad.HitTest(p, a):
                return True
    return False


def f_segment_clear(board, a, b, acc):
    n = max(int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05), 1)
    return all(not hit_f(board, a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, acc)
               for i in range(1, n))


def connect_to_gnd_pad(board, cx, cy, gnd):
    """Link an isolated GND pad to the nearest reachable GND SMD pad on F.Cu with a one- or two-segment track."""
    cands = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == "GND" and pad.IsOnLayer(pcbnew.F_Cu) and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                q = pad.GetPosition()
                px, py = pcbnew.ToMM(q.x), pcbnew.ToMM(q.y)
                d = math.hypot(px - cx, py - cy)
                if 0.5 < d < 14:
                    cands.append((d, px, py))
    for d, px, py in sorted(cands):
        for mid in ((px, cy), (cx, py), None):
            pts = [(cx, cy), mid, (px, py)] if mid else [(cx, cy), (px, py)]
            if all(f_segment_clear(board, a, b, 0.33) for a, b in zip(pts[:-1], pts[1:])):
                for a, b in zip(pts[:-1], pts[1:]):
                    add_track(board, a, b, gnd, "F.Cu", 0.2)
                return True
    return False


def main():
    board = pcbnew.LoadBoard(PCB)
    gnd = board.FindNet("GND")

    # 1) GND stub + via for R33 pad 2 (and any other isolated GND SMD pad passed on the command line)
    targets = sys.argv[1:] or ["R33.2"]
    for tgt in targets:
        ref, num = tgt.split(".")
        pad = None
        for fp in board.GetFootprints():
            if fp.GetReference() == ref:
                for p in fp.Pads():
                    if p.GetNumber() == num:
                        pad = p
        if pad is None:
            continue
        c = pad.GetPosition()
        cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
        placed = False
        for dist in (1.2, 1.5, 1.8, 2.2, 2.6, 3.0):
            for ang in range(0, 360, 15):
                x = cx + dist * math.cos(math.radians(ang))
                y = cy + dist * math.sin(math.radians(ang))
                if items_hit(board, x, y, 0.55, ignore_net="GND"):
                    continue
                if not segment_clear(board, (cx, cy), (x, y), 0.3, "GND"):
                    continue
                add_via(board, x, y, gnd)
                add_track(board, (cx, cy), (x, y), gnd, "F.Cu")
                print("GND via for", tgt, "at (%.2f, %.2f)" % (x, y))
                placed = True
                break
            if placed:
                break
        if not placed:
            placed = connect_to_gnd_pad(board, cx, cy, gnd)
            print("F.Cu link to a GND pad for", tgt, ":", placed)

    # 1b) neck a 0.23 mm wide stub of BUCK_PH that sat 0.007 mm inside the clearance of a VIN via
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() != "BUCK_PH":
            continue
        a, e = t.GetStart(), t.GetEnd()
        if (abs(pcbnew.ToMM(a.x) - 109.34) < 0.02 and abs(pcbnew.ToMM(a.y) - 70.24) < 0.02
                and abs(pcbnew.ToMM(e.x) - 109.5) < 0.02):
            t.SetWidth(mm(0.5))
            print("narrowed BUCK_PH stub")

    # 1c) thermal pad of the buck IC: solid connection to the planes (avoids starved-thermal on In2.Cu)
    for fp in board.GetFootprints():
        if fp.GetReference() == "U2":
            for pad in fp.Pads():
                if pad.GetNumber() == "9":
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    # 2) refill zones and save
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print("saved")


if __name__ == "__main__":
    main()
