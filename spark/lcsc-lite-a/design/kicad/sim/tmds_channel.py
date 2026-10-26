"""TMDS channel geometry analysis from the routed board.

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/tmds_channel.py --extract   (KiCad python: vias + board track lengths)
  python -X utf8 kicad/sim/tmds_channel.py                                                    (system python: numpy/scipy)

Inputs
  tmds_roles.json  written by the router (route_pcb.py): for every TMDS net the tracks of the coupled pair path ("main", incl. the
                   ESD straps) and of the bias-resistor branches ("branch").
  tmds_geom.json   written by --extract from the .kicad_pcb: vias, and all track segments (used to cross-check the router output).
For every pair the local differential impedance is looked up from the 2D field solver (microstrip2d) at 0.1 mm steps along the P trace
(width and distance to the N trace); all copper layers use the F.Cu microstrip table (assumption, see docs).
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
EXTRACT = "--extract" in sys.argv
if EXTRACT:
    import pcbnew  # noqa: E402
    mm = pcbnew.ToMM
else:
    import microstrip2d as m2  # noqa: E402
PCB = os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb")
GEOM = os.path.join(HERE, "tmds_geom.json")
ROLES = os.path.join(HERE, "tmds_roles.json")
PAIRS = [("D0", "HDMI_D0P", "HDMI_D0N"), ("D1", "HDMI_D1P", "HDMI_D1N"), ("D2", "HDMI_D2P", "HDMI_D2N"),
         ("CK", "HDMI_CKP", "HDMI_CKN")]
CACHE = os.path.join(HERE, "zdiff_cache.json")
GRID = (0.1, 0.13, 0.15, 0.2, 0.3, 0.45, 0.7, 1.0, 1.5)


def extract(path=PCB, out=GEOM):
    board = pcbnew.LoadBoard(path)
    geom = {}
    for t in board.GetTracks():
        n = t.GetNetname()
        if not (n.startswith("HDMI_D") or n.startswith("HDMI_CK")):
            continue
        g = geom.setdefault(n, {"segs": [], "vias": []})
        if isinstance(t, pcbnew.PCB_VIA):
            g["vias"].append((mm(t.GetPosition().x), mm(t.GetPosition().y)))
        else:
            a_, b_ = t.GetStart(), t.GetEnd()
            g["segs"].append((mm(a_.x), mm(a_.y), mm(b_.x), mm(b_.y), mm(t.GetWidth()), board.GetLayerName(t.GetLayer())))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            n = pad.GetNetname()
            if n in geom:
                sz, ps = pad.GetSize(), pad.GetPosition()
                geom[n].setdefault("pads", []).append(
                    dict(ref=fp.GetReference() + "." + pad.GetNumber(), x=mm(ps.x), y=mm(ps.y), w=mm(sz.x), h=mm(sz.y),
                         rot=pad.GetOrientationDegrees()))     # absolute orientation on the board
    json.dump(geom, open(out, "w"))
    print("wrote", out, len(geom), "nets")


GEOM_DATA = {}
ROLE_DATA = {}
LAYER_NAMES = ["F.Cu", "In2.Cu", "B.Cu"]


def load():
    global GEOM_DATA, ROLE_DATA
    GEOM_DATA = json.load(open(GEOM))
    ROLE_DATA = json.load(open(ROLES)) if os.path.exists(ROLES) else {}


def _polyline_segs(role_list):
    out = []
    for layer, pts, w in role_list:
        ln = LAYER_NAMES[layer] if isinstance(layer, int) else layer
        for a_, b_ in zip(pts[:-1], pts[1:]):
            out.append((a_[0], a_[1], b_[0], b_[1], w, ln))
    return out


PATH_ROLES = ("main", "stub", "strap")     # signal path = coupled pair path + pad escape stubs + ESD straps


def segs(board, net):
    """Segments of the signal path (coupled pair path, pad escape stubs, ESD straps) of a net."""
    if net in ROLE_DATA:
        return [x for r in PATH_ROLES for x in _polyline_segs(ROLE_DATA[net].get(r, []))]
    return [tuple(x) for x in GEOM_DATA.get(net, {}).get("segs", [])]


def branch_segs(net):
    return _polyline_segs(ROLE_DATA.get(net, {}).get("branch", []))


def vias(board, net):
    return [tuple(x) for x in GEOM_DATA.get(net, {}).get("vias", [])]


def length(seglist):
    return sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in seglist)


def _cache():
    try:
        return json.load(open(CACHE))
    except Exception:  # noqa: BLE001
        return {}


_c = _cache()


def zdiff_exact(w, gap):
    """[Zdiff, eps_eff(odd), Zeven (per line), eps_eff(even)] of the pair (2D solver, cached)."""
    key = "%.3f/%.2f" % (round(w, 3), gap)
    if key not in _c or len(_c[key]) < 4:
        r = m2.pair(round(w, 3), max(gap, 0.05))
        _c[key] = [r["zdiff"], r["odd"][1], r["even"][0], r["even"][1]]
        json.dump(_c, open(CACHE, "w"))
    return _c[key]


def zdiff(w, gap):
    """Differential impedance, eps_eff: log-gap interpolation between solved grid points (no rounding of the real gap)."""
    g = min(max(gap, GRID[0]), GRID[-1])
    lo = max(x for x in GRID if x <= g + 1e-9)
    hi = min(x for x in GRID if x >= g - 1e-9)
    a, b = zdiff_exact(w, lo), zdiff_exact(w, hi)
    if hi == lo:
        return a
    t = (math.log(g) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return [a[i] + (b[i] - a[i]) * t for i in range(4)]


def samples(seglist, step=0.1):
    pts = []
    for (x0, y0, x1, y1, w, ly) in seglist:
        n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
        for i in range(n):
            pts.append((x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (i + 0.5) / n, w, ly, math.hypot(x1 - x0, y1 - y0) / n))
    return pts


def profile(sp_, sn_):
    """[(dl, Zdiff, eps_eff(odd), gap, layer, x, y, Zeven, eps_eff(even))] along the P trace, in the order of sp_ (all layers use the microstrip table)."""
    P = samples(sp_)
    N = samples(sn_)
    out = []
    for (x, y, w, ly, dl) in P:
        best, wn = 1e9, w
        for (xn, yn, w2, ly2, _) in N:
            if ly2 != ly:
                continue
            d = math.hypot(xn - x, yn - y)
            if d < best:
                best, wn = d, w2
        if best > 1e8:                      # partner on another layer here (via jog): treat as uncoupled
            best, wn = 1.5 + w, w
        gap = best - (w + wn) / 2
        z, ee, ze, eee = zdiff(w, max(gap, 0.1))
        out.append((dl, z, ee, gap, ly, x, y, ze, eee))
    return out


def order_segments(seglist):
    """Chain the segments of one net from its minimum-x end to the other end; each segment is oriented along the walk.
    Returns (ordered, loose) where loose are segments that could not be reached from the chain."""
    segs_ = [list(x) for x in seglist]
    if not segs_:
        return [], []
    pts = [(x[0], x[1]) for x in segs_] + [(x[2], x[3]) for x in segs_]
    cur = min(pts, key=lambda q: (q[0], q[1]))
    out, used = [], [False] * len(segs_)
    while True:
        best = None
        for i, sg in enumerate(segs_):
            if used[i]:
                continue
            for flip in (False, True):
                a_ = (sg[2], sg[3]) if flip else (sg[0], sg[1])
                d = math.hypot(a_[0] - cur[0], a_[1] - cur[1])
                if d < 0.06 and (best is None or d < best[0]):
                    best = (d, i, flip)
        if best is None:
            break
        _, i, flip = best
        sg = segs_[i]
        used[i] = True
        if flip:
            sg = [sg[2], sg[3], sg[0], sg[1]] + sg[4:]
        out.append(tuple(sg))
        cur = (sg[2], sg[3])
    loose = [tuple(sg) for i, sg in enumerate(segs_) if not used[i]]
    return out, loose


def clip_at_pads(ordered, pads, refs=("J4.", "J5.")):
    """Remove the part of the path that lies inside the Core-socket (J4) / HDMI-connector (J5) pad copper at both path ends.
    The pad copper is a wider conductor of the pad structure itself (not a line section). Returns (segments, clipped length in mm)."""
    rects = []
    for p in pads:
        if p["ref"].startswith(refs):
            hw, hh = p["w"] / 2, p["h"] / 2
            if int(round(p["rot"])) % 180 == 90:
                hw, hh = hh, hw
            rects.append((p["x"], p["y"], hw, hh))
    segs_ = [list(x) for x in ordered]
    total = 0.0

    def inside(x, y):
        return any(abs(x - cx) <= hw + 1e-6 and abs(y - cy) <= hh + 1e-6 for cx, cy, hw, hh in rects)
    for end in (0, 1):
        while segs_:
            sg = segs_[0] if end == 0 else segs_[-1]
            a_, b_ = ((sg[0], sg[1]), (sg[2], sg[3])) if end == 0 else ((sg[2], sg[3]), (sg[0], sg[1]))
            if not inside(*a_):
                break
            L = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
            n = max(int(L / 0.005), 1)
            t_out = None
            for i in range(n + 1):
                t = i / n
                if not inside(a_[0] + (b_[0] - a_[0]) * t, a_[1] + (b_[1] - a_[1]) * t):
                    t_out = t
                    break
            if t_out is None:                       # whole segment inside the pad copper
                total += L
                segs_.pop(0 if end == 0 else -1)
                continue
            total += L * t_out
            q = (a_[0] + (b_[0] - a_[0]) * t_out, a_[1] + (b_[1] - a_[1]) * t_out)
            if end == 0:
                sg[0], sg[1] = q
            else:
                sg[2], sg[3] = q
            break
    return [tuple(x) for x in segs_], total


def main():
    load()
    print("%-3s %-5s %8s %8s %6s | %s" % ("pr", "net", "len P", "len N", "skew", "branch P/N (mm) | chain complete"))
    summary = {}
    for tag, p, n in PAIRS:
        row = {}
        tot_p = tot_n = 0.0
        zs, ls, coupled, tot_l = [], [], 0.0, 0.0
        for sfx in ("", "_C"):
            sp_, loose_p = order_segments(segs(None, p + sfx))
            sn_, loose_n = order_segments(segs(None, n + sfx))
            lp_, ln_ = length(sp_), length(sn_)
            bp, bn = length(branch_segs(p + sfx)), length(branch_segs(n + sfx))
            ok = not loose_p and not loose_n
            print("%-3s %-5s %8.2f %8.2f %6.2f | %5.1f / %5.1f | %s" % (tag, sfx or "core", lp_, ln_, lp_ - ln_, bp, bn,
                                                                          "yes" if ok else "NO (loose segments: %d/%d)" % (len(loose_p), len(loose_n))))
            tot_p += lp_
            tot_n += ln_
            row["len_" + (sfx or "core")] = (lp_, ln_)
            row["branch" + (sfx or "")] = (bp, bn)
            for (dl, z, ee, gap, ly, x, y, _ze, _ee) in profile(sp_, sn_):
                zs.append(z)
                ls.append(dl)
                tot_l += dl
                if gap < 0.4:
                    coupled += dl
        zs, ls = np.array(zs), np.array(ls)
        print("%-3s TOTAL len P %.2f N %.2f skew %.2f mm; Zdiff min %.0f mean %.0f max %.0f ohm; coupled share %.0f %%" % (
            tag, tot_p, tot_n, tot_p - tot_n, zs.min(), (zs * ls).sum() / ls.sum(), zs.max(), 100 * coupled / tot_l))
        row.update(len_p=tot_p, len_n=tot_n, skew=tot_p - tot_n, zmin=float(zs.min()), zmean=float((zs * ls).sum() / ls.sum()),
                   coupled=100 * coupled / tot_l)
        summary[tag] = row
    json.dump(summary, open(os.path.join(HERE, "tmds_summary.json"), "w"), indent=1)


if __name__ == "__main__":
    if EXTRACT:
        extract()
    else:
        main()
