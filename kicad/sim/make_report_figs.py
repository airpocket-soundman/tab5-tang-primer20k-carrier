"""Figures for site/hdmi-simulation.html (system python: numpy, scipy, matplotlib).

python -X utf8 kicad/sim/make_report_figs.py   (after tmds_channel.py --extract)
"""
import json
import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "site", "img")
sys.path.insert(0, HERE)
import microstrip2d as m2  # noqa: E402
import tmds_channel as tc  # noqa: E402
import tmds_sparam as sp  # noqa: E402

plt.rcParams.update({"font.family": "Yu Gothic" if os.name == "nt" else "sans-serif", "font.size": 10,
                     "axes.grid": True, "grid.alpha": .3, "axes.unicode_minus": False})
COL = {"D0": "#d62728", "D1": "#1f77b4", "D2": "#2ca02c", "CK": "#ff7f0e"}


def fig_zdiff():
    cache = os.path.join(HERE, "zdiff_sweep.json")
    if os.path.exists(cache):
        data = json.load(open(cache))
    else:
        data = {}
        for w in (0.127, 0.15, 0.2, 0.25):
            data[str(w)] = {}
            for g in (0.10, 0.13, 0.15, 0.20, 0.30, 0.50, 1.0):
                data[str(w)][str(g)] = m2.pair(w, g)["zdiff"]
        json.dump(data, open(cache, "w"))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for w, d in data.items():
        gs = sorted(float(g) for g in d)
        ax.plot(gs, [d[str(g)] for g in gs], "o-", label="線幅 %s mm" % w)
    ax.axhspan(85, 115, color="g", alpha=.12, label="100Ω ±15%")
    ax.axvline(0.13, color="k", ls=":")
    ax.text(0.136, 172, "採用: 0.2mm / 間隔0.13mm", fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("ペア内の間隔 (mm)")
    ax.set_ylabel("差動インピーダンス (Ω)")
    ax.set_title("2Dソルバ: 差動インピーダンス（JLC04161H-7628、L1-L2間 0.2104mm）", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_zdiff.png"), dpi=110)
    plt.close(fig)
    return data


def fig_compare():
    base = {"D0": (3.3, 162), "D1": (10.9, 162), "D2": (13.1, 153), "CK": (11.7, 163)}
    fz = {"D0": 109, "D1": 112, "D2": 112, "CK": 112}
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    names = list(base)
    x = np.arange(4)
    ax[0].bar(x - .18, [base[n][0] for n in names], .36, label="最初の配線（P/Nを個別に配線）", color="#c44")
    ax[0].bar(x + .18, [0.0] * 4, .36, label="最終（ペア配線）", color="#4a4")
    ax[0].axhline(5, color="k", ls=":")
    ax[0].text(3.4, 5.3, "許容 5mm", fontsize=8, ha="right")
    ax[0].set_xticks(x)
    ax[0].set_xticklabels(names)
    ax[0].set_ylabel("ペア内スキュー |P-N| (mm)")
    ax[0].legend(fontsize=8)
    ax[1].bar(x - .18, [base[n][1] for n in names], .36, color="#c44")
    ax[1].bar(x + .18, [fz[n] for n in names], .36, color="#4a4")
    ax[1].axhspan(85, 115, color="g", alpha=.12)
    ax[1].text(-0.4, 118, "100Ω ±15%", fontsize=8)
    ax[1].set_xticks(x)
    ax[1].set_xticklabels(names)
    ax[1].set_ylabel("差動インピーダンス 平均 (Ω, F.Cu)")
    ax[1].set_ylim(0, 190)
    fig.suptitle("配線方式による改善（2Dソルバ＋実配線）")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_compare.png"), dpi=110)
    plt.close(fig)


def fig_route():
    tc.GEOM_DATA.update(json.load(open(tc.GEOM)))
    g = {n: {"segs": tc.segs(None, n), "vias": v["vias"]} for n, v in tc.GEOM_DATA.items()}     # without the bias-resistor branches
    fig, ax = plt.subplots(figsize=(8.5, 9))
    ls = {"F.Cu": "-", "In2.Cu": "--", "B.Cu": ":"}
    for n, v in g.items():
        k = n.split("_")[1][:2]
        pn = n.split("_")[1][2]
        for s in v["segs"]:
            ax.plot([s[0], s[2]], [s[1], s[3]], color=COL[k], ls=ls[s[5]], lw=1.3 if pn == "P" else 2.6,
                    alpha=.9 if pn == "P" else .45, solid_capstyle="round")
        for x, y in v["vias"]:
            ax.plot(x, y, "ko", ms=3)
    for k, c in COL.items():
        ax.plot([], [], color=c, lw=2, label=k)
    ax.plot([], [], "k-", label="F.Cu")
    ax.plot([], [], "k--", label="In2.Cu")
    ax.plot([], [], "k:", label="B.Cu")
    ax.annotate("Core SODIMM\n(偶数列パッド)", (86, 40), ha="right", fontsize=8)
    ax.annotate("HDMI\nコネクタ", (117.5, 20), fontsize=8)
    ax.annotate("AC結合 / ESD", (103, 11), fontsize=8)
    ax.set_xlim(84, 122)
    ax.set_ylim(58, 8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.legend(ncol=3, fontsize=8, loc="lower right")
    ax.set_title("TMDS 4ペアの実配線（細線=P、太線=N、黒点=ビア）", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_route.png"), dpi=110)
    plt.close(fig)


_SEC = {}


def channel(tag, p, n, core_len=38.4e-3, esl=1.4e-9, c_diff=0.15e-12, socket_l=0.0, socket_c=0.0, conn_z=100.0):
    if tag not in _SEC:
        _SEC[tag] = sp.sections(tag, p, n)
    sec = _SEC[tag]
    mats = [sp.abcd_line(sp.F, 100.0, core_len, 3.0)]
    if socket_l:
        mats.append(sp.abcd_series(sp.F, 2j * np.pi * sp.F * socket_l))
    if socket_c:
        mats.append(sp.abcd_shunt(sp.F, 2j * np.pi * sp.F * socket_c))
    for key in ("core", "C", "K"):
        for (l, z, ee) in sec[key]:
            mats.append(sp.abcd_line(sp.F, z, l, ee))
        if key == "core":
            mats.append(sp.abcd_series(sp.F, 2j * np.pi * sp.F * esl))
        if key == "C":
            mats.append(sp.abcd_shunt(sp.F, 2j * np.pi * sp.F * c_diff))
    mats.append(sp.abcd_line(sp.F, conn_z, 11e-3, 2.5))
    return sp.cascade(mats)


def fig_sparam():
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.5))
    res = {}
    for tag, p, n in tc.PAIRS:
        M = channel(tag, p, n)
        s11, s21 = sp.abcd_to_s(M)
        ax[0][0].plot(sp.F / 1e9, 20 * np.log10(abs(s11)), color=COL[tag], label=tag)
        ax[0][1].plot(sp.F / 1e9, 20 * np.log10(abs(s21)), color=COL[tag], label=tag)
        s = _SEC[tag]["core"]
        xs = np.cumsum([0] + [q[0] * 1e3 for q in s])
        zs = [s[0][1]] + [q[1] for q in s]
        ax[1][0].plot(xs, zs, color=COL[tag], label=tag)
        i1 = int(np.argmin(abs(sp.F - .825e9)))
        i2 = int(np.argmin(abs(sp.F - 1.65e9)))
        res[tag] = dict(s11_825=float(20 * np.log10(abs(s11[i1]))), s11_1650=float(20 * np.log10(abs(s11[i2]))),
                        s21_825=float(20 * np.log10(abs(s21[i1]))), s21_1650=float(20 * np.log10(abs(s21[i2]))),
                        s11_max=float((20 * np.log10(abs(s11))).max()))
    ax[0][0].axhline(-10, color="k", ls=":")
    ax[0][0].set_ylim(-45, 0)
    ax[0][0].set_title("SDD11：Core側から見た反射（100Ω基準）")
    ax[0][1].set_title("SDD21：挿入損失")
    for a in (ax[0][0], ax[0][1]):
        a.set_xlabel("周波数 (GHz)")
        a.set_ylabel("dB")
        a.legend()
        a.axvline(0.74 / 2, color="gray", ls="--", lw=.8)
        a.axvline(1.49 / 2, color="gray", ls="--", lw=.8)
    ax[0][0].text(0.38, -4, "720p60", fontsize=7)
    ax[0][0].text(0.76, -4, "1080p60", fontsize=7)
    ax[1][0].axhspan(85, 115, color="g", alpha=.12)
    ax[1][0].set_title("Core側 キャリア配線の差動インピーダンス（F.Cuの区間）")
    ax[1][0].set_xlabel("配線に沿った距離 (mm)")
    ax[1][0].set_ylabel("Ω")
    ax[1][0].legend()
    rows = ["ペア  SDD11 0.825/1.65GHz   SDD21 0.825/1.65GHz"]
    for tag in res:
        r = res[tag]
        rows.append("%-3s  %6.1f / %6.1f dB      %5.2f / %5.2f dB" % (tag, r["s11_825"], r["s11_1650"], r["s21_825"], r["s21_1650"]))
    ax[1][1].axis("off")
    ax[1][1].text(0, 1, "\n".join(rows), va="top", family="monospace", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_sparam.png"), dpi=110)
    plt.close(fig)
    json.dump(res, open(os.path.join(HERE, "report_sparam.json"), "w"), indent=1)
    return res


def fig_sensitivity():
    """How much SODIMM-contact series L / shunt C can the channel tolerate? (worst of the 4 pairs)"""
    Ls = np.linspace(0, 3e-9, 13)
    Cs = np.linspace(0, 1.5e-12, 13)
    grid = np.zeros((len(Cs), len(Ls)))
    grid2 = np.zeros_like(grid)
    i2 = int(np.argmin(abs(sp.F - 1.65e9)))
    for a, c in enumerate(Cs):
        for b, l in enumerate(Ls):
            worst, worst21 = -99.0, 0.0
            for tag, p, n in tc.PAIRS:
                M = channel(tag, p, n, socket_l=l, socket_c=c)
                s11, s21 = sp.abcd_to_s(M)
                worst = max(worst, float(20 * np.log10(abs(s11[sp.F <= 1.65e9])).max()))
                worst21 = min(worst21, float(20 * np.log10(abs(s21[i2]))))
            grid[a, b], grid2[a, b] = worst, worst21
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    ext = [Ls[0] * 1e9, Ls[-1] * 1e9, Cs[0] * 1e12, Cs[-1] * 1e12]
    im = ax[0].imshow(grid, origin="lower", aspect="auto", extent=ext, cmap="RdYlGn_r", vmin=-25, vmax=0)
    cs = ax[0].contour(Ls * 1e9, Cs * 1e12, grid, levels=[-15, -10], colors="k")
    ax[0].clabel(cs, fmt="%d dB")
    plt.colorbar(im, ax=ax[0], label="SDD11 最大 (〜1.65GHz, dB)")
    ax[0].set_xlabel("SODIMM接点の直列L（差動, nH）")
    ax[0].set_ylabel("接点の並列C（差動, pF）")
    ax[0].set_title("反射（悪い方のペア）")
    im2 = ax[1].imshow(grid2, origin="lower", aspect="auto", extent=ext, cmap="RdYlGn", vmin=-3, vmax=0)
    plt.colorbar(im2, ax=ax[1], label="SDD21 @1.65GHz (dB)")
    ax[1].set_xlabel("直列L (nH)")
    ax[1].set_title("挿入損失（悪い方のペア）")
    fig.suptitle("コネクタ接点の反射に対する余裕（感度解析）")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_sensitivity.png"), dpi=110)
    plt.close(fig)
    json.dump(dict(L=list(Ls), C=list(Cs), sdd11=grid.tolist(), sdd21=grid2.tolist()), open(os.path.join(HERE, "report_sensitivity.json"), "w"))
    return float(grid[0, 0]), float(grid[len(Cs) // 2, len(Ls) // 2])


if __name__ == "__main__":
    tc.GEOM_DATA.update(json.load(open(tc.GEOM)))
    fig_zdiff()
    fig_compare()
    fig_route()
    print(fig_sparam())
    print("sensitivity (no socket model / mid), worst SDD11 dB:", fig_sensitivity())
