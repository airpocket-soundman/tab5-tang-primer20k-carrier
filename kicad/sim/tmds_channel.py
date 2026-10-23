"""TMDS channel analysis from the routed KiCad board (run with KiCad's python):

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/tmds_channel.py --extract   (KiCad python: board -> tmds_geom.json)
  python -X utf8 kicad/sim/tmds_channel.py                                                    (system python with numpy/scipy/scikit-rf)

For every TMDS pair (Core side net and connector side net, joined at the AC coupling capacitor) it extracts the routed
copper of P and N, walks along P and measures at every 0.1 mm the width and the distance to the partner trace, maps that to a
local differential impedance with the 2D field solver (microstrip2d), then reports length, skew, via count, Zdiff profile
statistics and a differential-mode S-parameter estimate (scikit-rf cascade of the sections).

Model limits (see docs/HDMI_信号品質_調査と方針.md): quasi-static microstrip sections (top layer) / stripline estimate for
In2, vias as lumped L-C, no mask, differential mode only (no mode conversion), Core board as an ideal 100 ohm line.
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
PAIRS = [("D0", "HDMI_D0P", "HDMI_D0N"), ("D1", "HDMI_D1P", "HDMI_D1N"), ("D2", "HDMI_D2P", "HDMI_D2N"),
         ("CK", "HDMI_CKP", "HDMI_CKN")]
CACHE = os.path.join(HERE, "zdiff_cache.json")
EPS_EFF_UNCOUPLED = 3.1


def load_cache():
    try:
        return json.load(open(CACHE))
    except Exception:  # noqa: BLE001
        return {}


_cache = load_cache()


def zdiff(w, gap):
    """Differential impedance and eps_eff of a microstrip pair on the L1/L2 stackup (cached 2D solutions)."""
    w = round(w, 3)
    grid = (0.1, 0.15, 0.2, 0.3, 0.45, 0.7, 1.0, 1.5)
    gap = min(grid, key=lambda g: abs(g - min(gap, 1.5)))
    key = "%.3f/%.2f" % (w, gap)
    if key not in _cache:
        r = m2.pair(w, max(gap, 0.05))
        _cache[key] = [r["zdiff"], r["odd"][1]]
        json.dump(_cache, open(CACHE, "w"))
    return _cache[key]


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
    json.dump(geom, open(out, "w"))
    print("wrote", out, len(geom), "nets")


GEOM_DATA = {}
PAIR_LEN = {}


def _stub_keys():
    try:
        st = json.load(open(os.path.join(HERE, "stub_tracks.json")))
    except Exception:  # noqa: BLE001
        return set()
    keys = set()
    for net, ly, pts in st:
        for a_, b_ in zip(pts[:-1], pts[1:]):
            keys.add((net, round(a_[0], 2), round(a_[1], 2), round(b_[0], 2), round(b_[1], 2)))
            keys.add((net, round(b_[0], 2), round(b_[1], 2), round(a_[0], 2), round(a_[1], 2)))
    return keys


def segs(board, net):
    stubs = segs.cache if hasattr(segs, "cache") else None
    if stubs is None:
        stubs = segs.cache = _stub_keys()
    out = []
    for x in GEOM_DATA.get(net, {}).get("segs", []):
        if (net, round(x[0], 2), round(x[1], 2), round(x[2], 2), round(x[3], 2)) in stubs:
            continue                                      # bias-resistor branch: not on the signal path
        out.append(tuple(x))
    return out


def vias(board, net):
    return [tuple(x) for x in GEOM_DATA.get(net, {}).get("vias", [])]


def samples(seglist, step=0.1):
    pts = []
    for (x0, y0, x1, y1, w, ly) in seglist:
        n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
        for i in range(n):
            pts.append((x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (i + 0.5) / n, w, ly, math.hypot(x1 - x0, y1 - y0) / n))
    return pts


def length(seglist):
    return sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in seglist)


def analyse(board, tag, p, n):
    res = {}
    for side, suffix in (("core", ""), ("conn", "_C")):
        sp_, sn_ = segs(board, p + suffix), segs(board, n + suffix)
        res[side] = dict(len_p=length(sp_), len_n=length(sn_), vias_p=len(vias(board, p + suffix)),
                         vias_n=len(vias(board, n + suffix)), segs_p=sp_, segs_n=sn_)
    return res


def profile(sp_, sn_):
    """Zdiff along the P trace: list of (dl, Zdiff, eps_eff, coupled_gap)."""
    P = samples(sp_)
    Nn = samples(sn_)
    out = []
    for (x, y, w, ly, dl) in P:
        if ly != "F.Cu":
            out.append((dl, None, None, None, ly))
            continue
        best = 1e9
        wn = w
        for (xn, yn, w2, ly2, _) in Nn:
            if ly2 != ly:
                continue
            d = math.hypot(xn - x, yn - y)
            if d < best:
                best, wn = d, w2
        gap = best - (w + wn) / 2
        z, ee = zdiff(w, max(gap, 0.1))
        out.append((dl, z, ee, gap, ly))
    return out


def main():
    global GEOM_DATA
    GEOM_DATA = json.load(open(GEOM))
    global PAIR_LEN
    try:
        PAIR_LEN = json.load(open(os.path.join(HERE, 'pair_lengths.json')))
    except Exception:  # noqa: BLE001
        PAIR_LEN = {}
    board = None
    print("%-3s %-5s %8s %8s %6s %5s | %s" % ("pr", "part", "len P", "len N", "skew", "vias", "Zdiff F.Cu: min / mean(len-weighted) / max; share coupled(gap<0.4mm)"))
    summary = {}
    for tag, p, n in PAIRS:
        r = analyse(board, tag, p, n)
        tot_p = r["core"]["len_p"] + r["conn"]["len_p"]
        tot_n = r["core"]["len_n"] + r["conn"]["len_n"]
        pl = PAIR_LEN
        tp = sum(pl.get(p + sfx, {}).get(p + sfx, 0.0) for sfx in ("", "_K", "_C"))
        tn = sum(pl.get(p + sfx, {}).get(n + sfx, 0.0) for sfx in ("", "_K", "_C"))
        if tp and tn:
            tot_p, tot_n = tp, tn                      # lengths of the coupled main paths (bias-resistor stubs excluded)
        zs, ls, coupled, tot_l = [], [], 0.0, 0.0
        for side, suffix in (("core", ""), ("conn", "_C")):
            prof = profile(r[side]["segs_p"], r[side]["segs_n"])
            for dl, z, ee, gap, ly in prof:
                tot_l += dl
                if z is None:
                    continue
                zs.append(z); ls.append(dl)
                if gap < 0.4:
                    coupled += dl
            print("%-3s %-5s %8.1f %8.1f %6.2f %5d |" % (tag, side, r[side]["len_p"], r[side]["len_n"],
                                                      r[side]["len_p"] - r[side]["len_n"],
                                                      r[side]["vias_p"] + r[side]["vias_n"]))
        zs, ls = np.array(zs), np.array(ls)
        mean = float((zs * ls).sum() / ls.sum()) if len(ls) else float("nan")
        print("%-3s TOTAL len P %.1f N %.1f skew %.2f mm; Zdiff F.Cu min %.0f mean %.0f max %.0f ohm; coupled share %.0f %%" % (
            tag, tot_p, tot_n, tot_p - tot_n, zs.min() if len(zs) else 0, mean, zs.max() if len(zs) else 0,
            100 * coupled / max(tot_l, 1e-9)))
        summary[tag] = dict(len_p=tot_p, len_n=tot_n, zmean=mean)
    json.dump(summary, open(os.path.join(HERE, "tmds_summary.json"), "w"), indent=1)


if __name__ == "__main__":
    if EXTRACT:
        extract()
    else:
        main()
