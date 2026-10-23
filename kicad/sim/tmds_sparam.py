"""Differential-mode channel estimate of every TMDS pair from the routed board (system python: numpy, scipy, matplotlib).

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/tmds_channel.py --extract
  python -X utf8 kicad/sim/tmds_sparam.py

Chain (signal flow):  Core board (ideal 100 ohm line, 38.4 mm, from the official net-length table)
                      -> carrier Core-side pair -> AC coupling cap (ESL) -> carrier C section -> ESD (shunt C) -> carrier K section
                      -> HDMI connector (100 ohm, 11 mm) -> sink 100 ohm.
Each carrier section is a cascade of 0.1 mm line pieces, each with the local Zdiff from the 2D field solver (see tmds_channel.py).
Layers other than F.Cu are modelled as 100 ohm (not solved). Differential mode only. Results: tmds_sparam.png / tmds_sparam.json.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tmds_channel as tc  # noqa: E402

C0 = 299792458.0
F = np.linspace(10e6, 3.3e9, 330)
TAND = 0.02                 # FR4 (JLC7628) loss tangent at 1 GHz
EPS_R = 4.4
ESD_C_DIFF = 0.15e-12       # RCLAMP0524P: 0.3 pF per line to GND -> 0.15 pF differential
CAP_ESL = 0.7e-9            # 0603 100 nF series inductance (differential: 2 x 0.7 nH)
VIA_L = 0.35e-9             # per via, series (differential pair of vias: 2 x)
Z_REF = 100.0


def abcd_line(f, z0, length_m, eeff):
    w = 2 * np.pi * f
    beta = w * np.sqrt(eeff) / C0
    alpha_d = np.pi * f * np.sqrt(eeff) * TAND / C0
    rs = np.sqrt(np.pi * f * 4e-7 * np.pi / 5.8e7)
    alpha_c = rs / (2 * 0.2e-3 * z0) * 0.5            # per-conductor skin loss, 0.2 mm wide, diff half-circuit
    g = (alpha_d + alpha_c) + 1j * beta
    ch, sh = np.cosh(g * length_m), np.sinh(g * length_m)
    A = ch; B = z0 * sh; C = sh / z0; D = ch
    return np.stack([np.stack([A, B], -1), np.stack([C, D], -1)], -2)    # (nf, 2, 2)


def abcd_series(f, z):
    n = len(f)
    M = np.tile(np.eye(2, dtype=complex), (n, 1, 1))
    M[:, 0, 1] = z
    return M


def abcd_shunt(f, y):
    n = len(f)
    M = np.tile(np.eye(2, dtype=complex), (n, 1, 1))
    M[:, 1, 0] = y
    return M


def cascade(mats):
    out = mats[0]
    for m in mats[1:]:
        out = out @ m
    return out


def abcd_to_s(M, z0=Z_REF):
    A, B, C, D = M[:, 0, 0], M[:, 0, 1], M[:, 1, 0], M[:, 1, 1]
    den = A + B / z0 + C * z0 + D
    s11 = (A + B / z0 - C * z0 - D) / den
    s21 = 2 / den
    return s11, s21


def order_segments(seglist):
    """Chain the track segments of one net from its minimum-x end (Core side / signal source) to the other end.
    Each segment is oriented along the walk. Segments not reachable from the chain are appended in stored order."""
    segs_ = [list(x) for x in seglist]
    if not segs_:
        return []
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
    out += [tuple(sg) for i, sg in enumerate(segs_) if not used[i]]
    return out


def sections(pair_tag, p, n):
    """(Core-side, C, K) lists of (length_m, z, eeff) in signal-flow order."""
    out = {}
    for key, sfx in (("core", ""), ("C", "_C"), ("K", "_K")):
        sp_ = order_segments(tc.segs(None, p + sfx))
        sn_ = order_segments(tc.segs(None, n + sfx))
        if not sp_ or not sn_:
            out[key] = []
            continue
        prof = tc.profile(sp_, sn_)
        out[key] = [(dl * 1e-3, (z if z is not None else 100.0), (ee if ee is not None else 3.0)) for dl, z, ee, gap, ly in prof]
    return out


def build(pair_tag, p, n, with_core=True):
    sec = sections(pair_tag, p, n)
    mats = []
    if with_core:
        mats.append(abcd_line(F, 100.0, 38.4e-3, 3.0))
    lens = {}
    for key in ("core", "C", "K"):
        for (l, z, ee) in sec[key]:
            mats.append(abcd_line(F, z, l, ee))
        lens[key] = sum(s[0] for s in sec[key]) * 1e3
        if key == "core":
            mats.append(abcd_series(F, 2j * np.pi * F * (CAP_ESL * 2)))                 # AC coupling capacitor
            mats.append(abcd_series(F, 2j * np.pi * F * (VIA_L * 2) * 0.0 + 0))         # (vias folded into the line model)
        if key == "C":
            mats.append(abcd_shunt(F, 2j * np.pi * F * ESD_C_DIFF))                     # ESD array
    mats.append(abcd_line(F, 100.0, 11e-3, 2.5))                                        # HDMI connector (assumed 100 ohm)
    return cascade(mats), lens


def main():
    tc.GEOM_DATA.update(json.load(open(tc.GEOM)))
    res = {}
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(12, 8))
    for tag, p, n in tc.PAIRS:
        M, lens = build(tag, p, n)
        s11, s21 = abcd_to_s(M)
        db11, db21 = 20 * np.log10(np.abs(s11)), 20 * np.log10(np.abs(s21))
        i1 = int(np.argmin(abs(F - 0.825e9)))
        i2 = int(np.argmin(abs(F - 1.65e9)))
        # TDR (step response of s11) of the whole channel
        S = np.concatenate([[s11[0]], s11])
        t = np.fft.irfft(np.concatenate([[0], s11]) , n=4 * len(F) + 2)
        res[tag] = dict(len_mm=lens, sdd11_825M=float(db11[i1]), sdd11_1650M=float(db11[i2]), sdd11_max_dB=float(db11.max()),
                        sdd21_825M=float(db21[i1]), sdd21_1650M=float(db21[i2]))
        ax[0][0].plot(F / 1e9, db11, label=tag)
        ax[0][1].plot(F / 1e9, db21, label=tag)
        # spec reference: HDMI source SDD11 is not mandated for TMDS; we use <-10 dB up to 1.65 GHz as a design target
    ax[0][0].axhline(-10, color="k", ls=":"); ax[0][0].set_title("SDD11 (reflection at the Core end, 100 ohm ref)"); ax[0][0].set_ylabel("dB")
    ax[0][1].set_title("SDD21 (insertion)"); ax[0][1].set_ylabel("dB")
    for a in (ax[0][0], ax[0][1]):
        a.set_xlabel("GHz"); a.grid(alpha=.3); a.legend()
    # Zdiff profile along the carrier path (core side) for each pair
    for tag, p, n in tc.PAIRS:
        sec = sections(tag, p, n)
        xs = np.cumsum([0] + [s[0] * 1e3 for s in sec["core"]])
        zs = [sec["core"][0][1]] + [s[1] for s in sec["core"]] if sec["core"] else [100]
        ax[1][0].plot(xs[:len(zs)], zs, label=tag)
    ax[1][0].axhspan(85, 115, color="g", alpha=.12); ax[1][0].set_title("Zdiff along the Core-side carrier path (F.Cu pieces)")
    ax[1][0].set_xlabel("mm"); ax[1][0].set_ylabel("ohm"); ax[1][0].grid(alpha=.3); ax[1][0].legend()
    ax[1][1].axis("off")
    ax[1][1].text(0, 1, json.dumps(res, indent=1)[:1500], va="top", fontsize=6, family="monospace")
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, "tmds_sparam.png"), dpi=90)
    json.dump(res, open(os.path.join(HERE, "tmds_sparam.json"), "w"), indent=1)
    for k, v in res.items():
        print(k, "carrier len core/C/K = %.1f/%.1f/%.1f mm" % (v["len_mm"]["core"], v["len_mm"]["C"], v["len_mm"]["K"]),
              "SDD11 825M %.1f dB, 1.65G %.1f dB (max %.1f) | SDD21 825M %.2f dB, 1.65G %.2f dB" % (
                  v["sdd11_825M"], v["sdd11_1650M"], v["sdd11_max_dB"], v["sdd21_825M"], v["sdd21_1650M"]))


if __name__ == "__main__":
    main()
