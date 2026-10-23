"""Differential-mode channel estimate of the TMDS pairs from the routed board (system python: numpy, scipy, matplotlib).

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/tmds_channel.py --extract
  python -X utf8 kicad/sim/tmds_sparam.py

Chain (signal flow): Core board (line Z_CORE, 38.4 mm) -> [SODIMM contact: series L, shunt C] -> carrier Core-side pair
  -> AC-coupling cap (ESL) -> carrier pair to the ESD tap -> ESD (shunt C at the tap, copper-strapped pads) -> carrier pair to the HDMI
  connector -> connector (100 ohm, 11 mm) -> 100 ohm.
  499 ohm bias resistors are modelled as branches: each branch is a 0.127 mm line (single-ended Z_BR) of its real length ending in 499 ohm
  to GND, attached at its real tap position. In the differential half-circuit every line contributes Y/2 (odd-mode symmetry; P and N
  branches of different length are treated independently, i.e. mode conversion is ignored).
Each carrier section is a cascade of 0.1 mm line pieces with the local Zdiff from the 2D solver; all layers use the microstrip table.
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
TAND = 0.02
ESD_X = (107.4, 108.7)          # x range of the ESD package (pads/straps); the shunt is inserted where the path crosses its centre
ESD_XC = 108.0
R_BIAS = 499.0
Z_BR = 85.0                     # single-ended impedance of the 0.127 mm branch trace (2D solver: ~85 ohm)
EEFF_BR = 3.0
DEFAULTS = dict(core_z=100.0, core_len=38.4e-3, esd_cd=0.35e-12, esl=1.4e-9, socket_l=0.0, socket_c=0.0, conn_z=100.0, branches=True)
Z_REF = 100.0


def abcd_line(f, z0, length_m, eeff):
    w = 2 * np.pi * f
    beta = w * np.sqrt(eeff) / C0
    alpha_d = np.pi * f * np.sqrt(eeff) * TAND / C0
    rs = np.sqrt(np.pi * f * 4e-7 * np.pi / 5.8e7)
    alpha_c = rs / (2 * 0.2e-3 * z0) * 0.5
    g = (alpha_d + alpha_c) + 1j * beta
    ch, sh = np.cosh(g * length_m), np.sinh(g * length_m)
    return np.stack([np.stack([ch, z0 * sh], -1), np.stack([sh / z0, ch], -1)], -2)


def abcd_series(f, z):
    M = np.tile(np.eye(2, dtype=complex), (len(f), 1, 1))
    M[:, 0, 1] = z
    return M


def abcd_shunt(f, y):
    M = np.tile(np.eye(2, dtype=complex), (len(f), 1, 1))
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
    return (A + B / z0 - C * z0 - D) / den, 2 / den


def branch_admittance(f, length_m):
    """Input admittance of a branch (line of single-ended impedance Z_BR and given length terminated by R_BIAS)."""
    w = 2 * np.pi * f
    beta = w * np.sqrt(EEFF_BR) / C0
    t = 1j * np.tan(beta * length_m)
    zin = Z_BR * (R_BIAS + Z_BR * t) / (Z_BR + R_BIAS * t)
    return 1 / zin


def sections(p, n):
    """{'core': [...], 'C': [...]} lists of (dl_m, z, eeff, x, y) in signal-flow order, plus the branch descriptions."""
    out = {}
    for key, sfx in (("core", ""), ("C", "_C")):
        sp_, _ = tc.order_segments(tc.segs(None, p + sfx))
        sn_, _ = tc.order_segments(tc.segs(None, n + sfx))
        prof = tc.profile(sp_, sn_) if sp_ and sn_ else []
        out[key] = [(dl * 1e-3, z, ee, x, y) for dl, z, ee, gap, ly, x, y in prof]
    br = []
    for net in (p + "_C", n + "_C"):
        segs = tc.branch_segs(net)
        if not segs:
            continue
        L = tc.length(segs)
        pts = [(s[0], s[1]) for s in segs] + [(s[2], s[3]) for s in segs]
        main = [(q[3], q[4]) for q in out["C"]]
        # tap = branch point closest to the main path
        best = min(((math.hypot(a[0] - m[0], a[1] - m[1]), m) for a in pts for m in main), key=lambda t: t[0])
        br.append(dict(net=net, length=L * 1e-3, tap=best[1]))
    out["branches"] = br
    return out


_SEC = {}


def channel(tag, p, n, **kw):
    o = dict(DEFAULTS)
    o.update(kw)
    if tag not in _SEC:
        _SEC[tag] = sections(p, n)
    sec = _SEC[tag]
    mats = [abcd_line(F, o["core_z"], o["core_len"], 3.0)]
    if o["socket_l"]:
        mats.append(abcd_series(F, 2j * np.pi * F * o["socket_l"]))
    if o["socket_c"]:
        mats.append(abcd_shunt(F, 2j * np.pi * F * o["socket_c"]))
    for (l, z, ee, x, y) in sec["core"]:
        mats.append(abcd_line(F, z, l, ee))
    mats.append(abcd_series(F, 2j * np.pi * F * o["esl"]))
    # carrier C chain with the ESD shunt and the bias branches inserted at their real positions
    chain = sec["C"]
    shunts = []                                              # (x, y, admittance array)
    shunts.append((ESD_XC, None, 2j * np.pi * F * o["esd_cd"]))
    if o["branches"]:
        # P and N branches form ONE differential shunt: Y_d = Y_P * Y_N / (Y_P + Y_N) (series of the two line-to-ground admittances)
        ys = []
        for b in sec["branches"]:
            bl = o.get("branch_len")
            bl = b["length"] if bl is None else (bl.get(b["net"], b["length"]) if isinstance(bl, dict) else bl)
            ys.append(branch_admittance(F, bl))
        if len(ys) == 2:
            yd = ys[0] * ys[1] / (ys[0] + ys[1])
            shunts.append((None, sec["branches"][0]["tap"], yd))
        else:
            for yy, b in zip(ys, sec["branches"]):
                shunts.append((None, b["tap"], 0.5 * yy))
    placed = [False] * len(shunts)
    for (l, z, ee, x, y) in chain:
        for i, (sx, sp_, y_) in enumerate(shunts):
            if placed[i]:
                continue
            if sx is not None and x >= sx:
                mats.append(abcd_shunt(F, y_)); placed[i] = True
            elif sp_ is not None and math.hypot(x - sp_[0], y - sp_[1]) < 0.06:
                mats.append(abcd_shunt(F, y_)); placed[i] = True
        mats.append(abcd_line(F, z, l, ee))
    for i, ok in enumerate(placed):
        if not ok:
            mats.append(abcd_shunt(F, shunts[i][2]))
    mats.append(abcd_line(F, o["conn_z"], 11e-3, 2.5))
    return cascade(mats)


def metrics(s11, s21):
    i1, i2 = int(np.argmin(abs(F - 0.371e9))), int(np.argmin(abs(F - 0.742e9)))        # 720p60: Nyquist 371 MHz, 3rd harmonic region
    band = F <= 1.5e9
    d = lambda a: 20 * np.log10(abs(a))                      # noqa: E731
    return dict(s11_371=float(d(s11[i1])), s11_742=float(d(s11[i2])), s11_max_1500=float(d(s11[band]).max()),
                s21_371=float(d(s21[i1])), s21_742=float(d(s21[i2])), s21_1500=float(d(s21[int(np.argmin(abs(F - 1.5e9)))])),
                s11_max_3300=float(d(s11).max()))


def main():
    tc.load()
    res = {}
    for tag, p, n in tc.PAIRS:
        M = channel(tag, p, n)
        s11, s21 = abcd_to_s(M)
        m = metrics(s11, s21)
        sec = _SEC[tag]
        m["len_mm"] = dict(core=sum(s[0] for s in sec["core"]) * 1e3, C=sum(s[0] for s in sec["C"]) * 1e3)
        m["branch_mm"] = [round(b["length"] * 1e3, 1) for b in sec["branches"]]
        res[tag] = m
        print(tag, "carrier core/C %.1f/%.1f mm, branches %s mm | SDD11 371M %.1f 742M %.1f max(<=1.5G) %.1f dB | SDD21 371M %.2f 742M %.2f 1.5G %.2f dB" % (
            m["len_mm"]["core"], m["len_mm"]["C"], m["branch_mm"], m["s11_371"], m["s11_742"], m["s11_max_1500"], m["s21_371"], m["s21_742"], m["s21_1500"]))
    json.dump(res, open(os.path.join(HERE, "tmds_sparam.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
