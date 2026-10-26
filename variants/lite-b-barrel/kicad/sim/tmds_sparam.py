"""Four-port (P/N) channel model of the TMDS pairs from the routed board (system python: numpy, scipy, matplotlib).

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/tmds_channel.py --extract
  python -X utf8 kicad/sim/tmds_sparam.py

Signal flow (each element is a 4x4 ABCD matrix in the P/N basis [Vp, Vn, Ip, In]):
  Core board (pair, Zo = core_z/2 per line, 38.4 mm) -> [SODIMM contact: series L, shunt C per line] -> carrier Core-side pair (pad escape
  stub + coupled pair, clipped at the pad) -> AC-coupling cap (ESL) -> carrier pair to the ESD tap -> ESD (shunt C per line, copper-strapped
  pads) -> carrier pair to the HDMI connector (stub) -> connector (100 ohm, 11 mm) -> 100 ohm.
  Coupled sections use the even/odd-mode impedances and effective permittivities of the 2D field solver at the local width/gap (0.1 mm steps).
  The 499 ohm bias resistors are branches of their real length (0.127 mm line, single-ended Z 85 ohm, terminated 499 ohm to GND) attached to
  the P line and to the N line at THEIR OWN tap positions (arc length along the line); P/N asymmetry therefore produces mode conversion.
  Differential quantities (SDD11, SDD21) and the differential-to-common conversion (SCD21) come from the 4-port S matrix (Z0 = 50 ohm per
  line, 100 ohm differential). All copper layers use the F.Cu microstrip table (assumption, see docs). Vias are not modelled.
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
ESD_XC = 108.0                  # x of the ESD package centre: the ESD shunt is inserted where each line crosses it
R_BIAS = 510.0
Z_BR = 85.0                     # single-ended impedance of the 0.127 mm branch trace (2D solver: ~85 ohm)
EEFF_BR = 3.0
DEFAULTS = dict(core_z=100.0, core_len=38.4e-3, esd_cd=0.35e-12, esl=1.4e-9, socket_l=0.0, socket_c=0.0, conn_z=100.0,
                branches=True, branch_mode="own")   # branch_mode: "own" = P and N branches at their own tap positions, "p_only" = old approximation
Z0 = 50.0
T2 = np.array([[1.0, 1.0], [1.0, -1.0]])
T2I = T2 / 2.0


# ------------------------------------------------------------------ 4x4 ABCD elements, shape (nf, 4, 4)
def blocks(A, B, C, D):
    nf = A.shape[0]
    M = np.zeros((nf, 4, 4), dtype=complex)
    M[:, :2, :2], M[:, :2, 2:], M[:, 2:, :2], M[:, 2:, 2:] = A, B, C, D
    return M


def _loss(f, z, eeff):
    alpha_d = np.pi * f * np.sqrt(eeff) * TAND / C0
    rs = np.sqrt(np.pi * f * 4e-7 * np.pi / 5.8e7)
    return alpha_d + rs / (2 * 0.2e-3 * z) * 0.5


def coupled(f, zo, eo, ze, ee, length_m):
    """Symmetric coupled pair: odd mode (Zo, eps eo), even mode (Ze, eps ee) per line."""
    out = []
    for z, e in ((ze, ee), (zo, eo)):
        g = _loss(f, z, e) + 1j * 2 * np.pi * f * np.sqrt(e) / C0
        out.append((np.cosh(g * length_m), z * np.sinh(g * length_m), np.sinh(g * length_m) / z))
    (che, bhe, che_), (cho, bho, cho_) = out
    nf = len(f)

    def sym(xe, xo):
        d = np.zeros((nf, 2, 2), dtype=complex)
        d[:, 0, 0], d[:, 1, 1] = xe, xo
        return T2 @ d @ T2I
    return blocks(sym(che, cho), sym(bhe, bho), sym(che_, cho_), sym(che, cho))


def uncoupled(f, z, length_m, eeff):
    return coupled(f, z, eeff, z, eeff, length_m)


def series_line(f, zp, zn):
    nf = len(f)
    eye2 = np.tile(np.eye(2, dtype=complex), (nf, 1, 1))
    B = np.zeros((nf, 2, 2), dtype=complex)
    B[:, 0, 0], B[:, 1, 1] = zp, zn
    return blocks(eye2, B, np.zeros_like(B), eye2)


def shunt_line(f, yp, yn):
    nf = len(f)
    eye2 = np.tile(np.eye(2, dtype=complex), (nf, 1, 1))
    C = np.zeros((nf, 2, 2), dtype=complex)
    C[:, 0, 0], C[:, 1, 1] = yp, yn
    return blocks(eye2, np.zeros_like(C), C, eye2)


def cascade(mats):
    out = mats[0]
    for m in mats[1:]:
        out = out @ m
    return out


def abcd_to_s4(M, z0=Z0):
    """4-port S matrix (ports 0,1 = P,N at the input; 2,3 = P,N at the output) from the 4x4 ABCD matrix."""
    A, B, C, D = M[:, :2, :2], M[:, :2, 2:], M[:, 2:, :2], M[:, 2:, 2:]
    nf = M.shape[0]
    I2 = np.tile(np.eye(2, dtype=complex), (nf, 1, 1))
    X = np.zeros((nf, 4, 4), dtype=complex)
    Y = np.zeros((nf, 4, 4), dtype=complex)
    X[:, :2, :2], X[:, :2, 2:] = I2, -(A + B / z0)
    X[:, 2:, :2], X[:, 2:, 2:] = I2, (z0 * C + D)
    Y[:, :2, :2], Y[:, :2, 2:] = -I2, (A - B / z0)
    Y[:, 2:, :2], Y[:, 2:, 2:] = I2, -(z0 * C - D)
    return np.linalg.solve(X, Y)             # [b1; b2] = S [a1; a2]


def mixed(S):
    sdd11 = 0.5 * (S[:, 0, 0] - S[:, 0, 1] - S[:, 1, 0] + S[:, 1, 1])
    sdd21 = 0.5 * (S[:, 2, 0] - S[:, 2, 1] - S[:, 3, 0] + S[:, 3, 1])
    scd21 = 0.5 * (S[:, 2, 0] - S[:, 2, 1] + S[:, 3, 0] - S[:, 3, 1])
    return sdd11, sdd21, scd21


# ------------------------------------------------------------------ geometry -> sections
def branch_admittance(f, length_m):
    """Input admittance of a branch (line of single-ended impedance Z_BR and given length terminated by R_BIAS)."""
    w = 2 * np.pi * f
    beta = w * np.sqrt(EEFF_BR) / C0
    t = 1j * np.tan(beta * length_m)
    zin = Z_BR * (R_BIAS + Z_BR * t) / (Z_BR + R_BIAS * t)
    return 1 / zin


def _line_path(net):
    """Ordered, pad-clipped signal path of one net: (segments, clipped in-pad length per end)."""
    ordered, loose = tc.order_segments(tc.segs(None, net))
    if loose:
        raise RuntimeError("%s: %d path segments not reachable from the chain (unclassified)" % (net, len(loose)))
    return tc.clip_at_pads(ordered, tc.GEOM_DATA.get(net, {}).get("pads", []))


def sections(p, n):
    """Per 0.1 mm section data of the Core-side ('core') and carrier ('C') pair, plus the branch description of the P and N line."""
    out = {"clipped": {}}
    for key, sfx in (("core", ""), ("C", "_C")):
        sp_, cp = _line_path(p + sfx)
        sn_, cn = _line_path(n + sfx)
        out["clipped"][key] = dict(P=cp, N=cn)
        secs, s = [], 0.0
        for dl, z, eo, gap, ly, x, y, ze, ee in tc.profile(sp_, sn_):
            secs.append(dict(dl=dl * 1e-3, zo=z / 2, eo=eo, ze=ze, ee=ee, x=x, y=y, s0=s * 1e-3, gap=gap, layer=ly))
            s += dl
        out[key] = secs
        out[key + "_paths"] = dict(P=sp_, N=sn_)
    br = {}
    for line, net in (("P", p + "_C"), ("N", n + "_C")):
        bs = tc.branch_segs(net)
        if not bs:
            continue
        pts = [(s[0], s[1]) for s in bs] + [(s[2], s[3]) for s in bs]
        best, s_acc = None, 0.0
        for sg in out["C_paths"][line]:
            seglen = math.hypot(sg[2] - sg[0], sg[3] - sg[1])
            nstep = max(int(seglen / 0.05), 1)
            for i in range(nstep + 1):
                mx, my = sg[0] + (sg[2] - sg[0]) * i / nstep, sg[1] + (sg[3] - sg[1]) * i / nstep
                for a in pts:
                    d = math.hypot(a[0] - mx, a[1] - my)
                    if best is None or d < best[0]:
                        best = (d, s_acc + seglen * i / nstep, (mx, my))
            s_acc += seglen
        br[line] = dict(net=net, length=tc.length(bs) * 1e-3, tap_s=best[1] * 1e-3, tap_xy=best[2], tap_gap=best[0])
    out["branches"] = br
    return out


_SEC = {}


def _x_cross(secs, xc):
    for sec in secs:
        if sec["x"] >= xc:
            return sec["s0"]
    return secs[-1]["s0"] + secs[-1]["dl"]


def _shunt_groups(events, zero):
    """Merge shunt events at the same position into one element per position: [(s, yp, yn)]."""
    out = []
    for s in sorted({round(e[0], 9) for e in events}):
        grp = [e for e in events if abs(e[0] - s) < 1e-9]
        out.append((s, sum((e[2] for e in grp if e[1] == "P"), zero), sum((e[2] for e in grp if e[1] == "N"), zero)))
    return out


def channel(tag, p, n, **kw):
    """4x4 ABCD of the whole channel."""
    o = dict(DEFAULTS)
    o.update(kw)
    if tag not in _SEC:
        _SEC[tag] = sections(p, n)
    sec = _SEC[tag]
    nf = len(F)
    zero = np.zeros(nf, dtype=complex)
    mats = [uncoupled(F, o["core_z"] / 2, o["core_len"], 3.0)]
    if o["socket_l"]:
        zl = 2j * np.pi * F * o["socket_l"] / 2             # differential L -> per line
        mats.append(series_line(F, zl, zl))
    if o["socket_c"]:
        yc = 2j * np.pi * F * o["socket_c"] * 2             # differential C -> per line to GND
        mats.append(shunt_line(F, yc, yc))
    for s_ in sec["core"]:
        mats.append(coupled(F, s_["zo"], s_["eo"], s_["ze"], s_["ee"], s_["dl"]))
    zesl = 2j * np.pi * F * o["esl"] / 2
    mats.append(series_line(F, zesl, zesl))
    chain = sec["C"]
    ycd = 2j * np.pi * F * o["esd_cd"] * 2                   # ESD: differential C -> per line to GND
    s_esd = _x_cross(chain, ESD_XC)
    events = [(s_esd, "P", ycd), (s_esd, "N", ycd)]
    if o["branches"]:
        bl = o.get("branch_len")
        for line in ("P", "N"):
            b = sec["branches"].get(line)
            if not b:
                continue
            L = b["length"] if bl is None else (bl.get(b["net"], b["length"]) if isinstance(bl, dict) else bl)
            s_t = sec["branches"]["P"]["tap_s"] if (o["branch_mode"] == "p_only" and "P" in sec["branches"]) else b["tap_s"]
            if o.get("branch_ideal"):                          # comparison case: short symmetric branches at the cap pad
                L, s_t = o["branch_ideal"], 0.0
            events.append((s_t, line, branch_admittance(F, L)))
    groups = _shunt_groups(events, zero)
    gi = 0
    for s_ in chain:
        while gi < len(groups) and groups[gi][0] <= s_["s0"] + 1e-12:
            mats.append(shunt_line(F, groups[gi][1], groups[gi][2]))
            gi += 1
        mats.append(coupled(F, s_["zo"], s_["eo"], s_["ze"], s_["ee"], s_["dl"]))
    while gi < len(groups):
        mats.append(shunt_line(F, groups[gi][1], groups[gi][2]))
        gi += 1
    mats.append(uncoupled(F, o["conn_z"] / 2, 11e-3, 2.5))
    return cascade(mats)


def metrics(M):
    sdd11, sdd21, scd21 = mixed(abcd_to_s4(M))
    i1, i2 = int(np.argmin(abs(F - 0.371e9))), int(np.argmin(abs(F - 0.742e9)))        # 720p60: Nyquist 371 MHz, 3rd harmonic region
    band = F <= 1.5e9
    d = lambda a: 20 * np.log10(np.maximum(abs(a), 1e-12))   # noqa: E731
    return dict(s11_371=float(d(sdd11[i1])), s11_742=float(d(sdd11[i2])), s11_max_1500=float(d(sdd11[band]).max()),
                s21_371=float(d(sdd21[i1])), s21_742=float(d(sdd21[i2])), s21_1500=float(d(sdd21[int(np.argmin(abs(F - 1.5e9)))])),
                s11_max_3300=float(d(sdd11).max()), scd21_max_1500=float(d(scd21[band]).max()), scd21_742=float(d(scd21[i2])),
                scd21_371=float(d(scd21[i1])))


def curves(M):
    return mixed(abcd_to_s4(M))


def main():
    tc.load()
    res = {}
    for tag, p, n in tc.PAIRS:
        m = metrics(channel(tag, p, n))
        sec = _SEC[tag]
        m["len_mm"] = dict(core=sum(s["dl"] for s in sec["core"]) * 1e3, C=sum(s["dl"] for s in sec["C"]) * 1e3)
        m["clipped_in_pad_mm"] = {k: {l: round(v, 3) for l, v in d.items()} for k, d in sec["clipped"].items()}
        m["branch_mm"] = [round(sec["branches"][l]["length"] * 1e3, 1) for l in ("P", "N") if l in sec["branches"]]
        m["branch_tap_s_mm"] = {l: round(b["tap_s"] * 1e3, 2) for l, b in sec["branches"].items()}
        m["old_approx"] = metrics(channel(tag, p, n, branch_mode="p_only"))
        res[tag] = m
        print(tag, "carrier core/C %.1f/%.1f mm, branches %s mm, taps %s | SDD11 371M %.1f 742M %.1f max(<=1.5G) %.1f dB | SDD21 371M %.2f 742M %.2f 1.5G %.2f dB | SCD21 max(<=1.5G) %.1f dB" % (
            m["len_mm"]["core"], m["len_mm"]["C"], m["branch_mm"], m["branch_tap_s_mm"], m["s11_371"], m["s11_742"], m["s11_max_1500"],
            m["s21_371"], m["s21_742"], m["s21_1500"], m["scd21_max_1500"]))
    json.dump(res, open(os.path.join(HERE, "tmds_sparam.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
