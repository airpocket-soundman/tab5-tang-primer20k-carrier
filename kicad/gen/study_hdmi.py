"""Placement study: where should the HDMI connector sit?  Routes only the 8 TMDS nets on a board that holds the
fixed parts (Core, M5-Bus header, series resistors, holes) for several candidate poses and prints length / vias / success."""
import sys, os, time, math
sys.path.insert(0, os.path.dirname(__file__))
import design, make_pcb, route_pcb, pcbnew

CANDS = [(119.0, 30.0, 0), (70.0, 9.5, 90), (62.0, 9.5, 90), (84.0, 9.5, 90), (70.0, 70.5, 270), (84.0, 70.5, 270)]
if len(sys.argv) > 1:
    CANDS = [tuple(float(v) for v in a.split(',')) for a in sys.argv[1:]]
NETS = ["HDMI_CKN", "HDMI_CKP", "HDMI_D0N", "HDMI_D0P", "HDMI_D1N", "HDMI_D1P", "HDMI_D2N", "HDMI_D2P"]
for pose in CANDS:
    design.HDMI_POSE = (pose[0], pose[1], int(pose[2]))
    b = make_pcb.Builder(); comps = design.build(); b.outline()
    keep = [c for c in comps if c.ref[0] in ("J", "H") and c.block in ("core", "mbus", "hdmi", "mech")]
    keep += [c for c in comps if c.block == "series"]
    for c in keep:
        b.create(c)
    r = route_pcb.Router(b.board, *design.BOARD); r.load(design.BOARD)
    core_x = next(c.pos[0] for c in keep if c.ref == "J4")
    r.add_escape_stubs({"J5.": (2.6, design.hdmi_stub_dir), "J4.": (2.4, lambda x, y, cx=core_x: -1 if x < cx else 1)})
    r.max_exp = 2000000
    t = time.time(); ok = 0
    for n in NETS:
        ok += bool(r.route_net(n, route_pcb.TW, 40.0))
    length = sum(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) for (nm, l, pts, w) in r.tracks if nm in NETS
                 for a_, b_ in zip(pts[:-1], pts[1:]))
    vias = sum(1 for v in r.vias if v[0] in NETS)
    print("pose %s: routed %d/8, TMDS track %.0f mm, vias %d (%.0fs)" % (pose, ok, length, vias, time.time() - t), flush=True)
