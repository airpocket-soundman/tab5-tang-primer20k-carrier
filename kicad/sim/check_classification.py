"""Classification coverage of every TMDS copper item of the routed board (KiCad python):

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/check_classification.py

Every track segment and via of the 16 TMDS nets (HDMI_D*/HDMI_CK*, Core side and `_C` side) must belong to exactly one role recorded by the
router in tmds_roles.json: main (coupled pair path), stub (pad escape stub), strap (ESD copper strap) or branch (bias-resistor branch).
Vias are classified as main when they sit on a vertex of a role polyline. Anything that is not covered is "unclassified"; the script exits
with code 1 if there is one, or if a role segment has no PCB copper (stale roles). Also lists the intentional exclusions (the part of a
stub that lies inside a socket/connector pad is reported by tmds_sparam.py as `clipped_in_pad_mm`).
Output: kicad/sim/classification_report.json
"""
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.environ.get("CHECK_PCB") or os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb")
mm = pcbnew.ToMM
TOL = 0.03
board = pcbnew.LoadBoard(PCB)
roles = json.load(open(os.path.join(HERE, "tmds_roles.json")))
LAYERS = ["F.Cu", "In2.Cu", "B.Cu"]


def role_segments(net):
    out = []
    for role, lst in roles.get(net, {}).items():
        for layer, pts, w in lst:
            ln = LAYERS[layer] if isinstance(layer, int) else layer
            for a, b in zip(pts[:-1], pts[1:]):
                out.append((role, ln, a[0], a[1], b[0], b[1]))
    return out


def dist_to_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


report = {"nets": {}, "unclassified": [], "stale_roles": []}
counts = {"main": 0, "stub": 0, "strap": 0, "branch": 0, "via_main": 0}
nets = sorted({t.GetNetname() for t in board.GetTracks() if t.GetNetname().startswith(("HDMI_D", "HDMI_CK"))})
for net in nets:
    rs = role_segments(net)
    pcb_segs, pcb_vias = [], []
    for t in board.GetTracks():
        if t.GetNetname() != net:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            pcb_vias.append((mm(t.GetPosition().x), mm(t.GetPosition().y)))
        else:
            pcb_segs.append((board.GetLayerName(t.GetLayer()), mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y)))
    cls = {"main": 0, "stub": 0, "strap": 0, "branch": 0, "via_main": 0}
    for (ln, x0, y0, x1, y1) in pcb_segs:
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(int(L / 0.05), 1)
        votes = {}
        ok = True
        for i in range(n + 1):
            px, py = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            hit = None
            for (role, rln, ax, ay, bx, by) in rs:
                if rln == ln and dist_to_seg(px, py, ax, ay, bx, by) <= TOL:
                    hit = role
                    break
            if hit is None:
                ok = False
                break
            votes[hit] = votes.get(hit, 0) + 1
        if ok:
            r = max(votes, key=votes.get)
            cls[r] += 1
            counts[r] += 1
        else:
            report["unclassified"].append(dict(net=net, kind="segment", layer=ln, a=[round(x0, 3), round(y0, 3)], b=[round(x1, 3), round(y1, 3)]))
    for (vx, vy) in pcb_vias:
        hit = any(math.hypot(vx - px, vy - py) <= TOL for (_r, _l, ax, ay, bx, by) in rs for (px, py) in ((ax, ay), (bx, by)))
        if hit:
            cls["via_main"] += 1
            counts["via_main"] += 1
        else:
            report["unclassified"].append(dict(net=net, kind="via", at=[round(vx, 3), round(vy, 3)]))
    # role segments that have no copper on the board (stale roles)
    for (role, rln, ax, ay, bx, by) in rs:
        mx, my = (ax + bx) / 2, (ay + by) / 2
        if not any(ln == rln and dist_to_seg(mx, my, x0, y0, x1, y1) <= TOL for (ln, x0, y0, x1, y1) in pcb_segs):
            report["stale_roles"].append(dict(net=net, role=role, layer=rln, a=[round(ax, 3), round(ay, 3)], b=[round(bx, 3), round(by, 3)]))
    cls["pcb_segments"] = len(pcb_segs)
    cls["pcb_vias"] = len(pcb_vias)
    report["nets"][net] = cls
report["counts"] = counts
report["ok"] = not report["unclassified"] and not report["stale_roles"]
if not os.environ.get("CHECK_PCB"):
    json.dump(report, open(os.path.join(HERE, "classification_report.json"), "w"), indent=1)
print("TMDS classification:", counts, "unclassified:", len(report["unclassified"]), "stale roles:", len(report["stale_roles"]))
for u in report["unclassified"][:10]:
    print("  unclassified", u)
for u in report["stale_roles"][:10]:
    print("  stale role", u)
sys.exit(0 if report["ok"] else 1)
