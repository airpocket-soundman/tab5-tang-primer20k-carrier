"""Which TMDS channel should use which Core TX pair?  Tries all 24 assignments (HDMI-only routing, bare board)."""
import sys, os, time, math, itertools
sys.path.insert(0, os.path.dirname(__file__))
import design, make_pcb, route_pcb
PAIRS = {"TX1": (140, 142), "TX2": (130, 132), "TX3": (68, 70), "TX4": (64, 62)}   # (P, N)
CH = ["D0", "D1", "D2", "CK"]
NETS = ["HDMI_%s%s" % (c, pn) for c in CH for pn in "NP"]
res = []
for perm in itertools.permutations(PAIRS):
    for ch, tx in zip(CH, perm):
        p, n = PAIRS[tx]
        design.CORE_PINS["HDMI_%sP" % ch] = p
        design.CORE_PINS["HDMI_%sN" % ch] = n
    b = make_pcb.Builder(); comps = design.build(); b.outline()
    keep = [c for c in comps if c.ref[0] in ("J", "H") and c.block in ("core", "mbus", "hdmi", "mech")] + \
           [c for c in comps if c.block == "series"]
    for c in keep: b.create(c)
    r = route_pcb.Router(b.board, *design.BOARD); r.load(design.BOARD)
    core_x = next(c.pos[0] for c in keep if c.ref == "J4")
    r.add_escape_stubs({"J5.": (2.6, design.hdmi_stub_dir), "J4.": (2.4, lambda x, y, cx=core_x: -1 if x < cx else 1)})
    r.max_exp = 2000000
    t = time.time(); ok = sum(bool(r.route_net(n, route_pcb.TW, 40.0)) for n in NETS)
    ln = sum(math.hypot(b_[0]-a_[0], b_[1]-a_[1]) for (nm, l, pts, w) in r.tracks if nm in NETS for a_, b_ in zip(pts[:-1], pts[1:]))
    vi = sum(1 for v in r.vias if v[0] in NETS)
    print("D0,D1,D2,CK <- %s: routed %d/8 length %.0f vias %d (%.0fs)" % (",".join(perm), ok, ln, vi, time.time()-t), flush=True)
