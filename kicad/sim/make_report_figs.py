"""Figures for site/hdmi-simulation.html (system python: numpy, scipy, matplotlib).

python -X utf8 kicad/sim/make_report_figs.py   (after tmds_channel.py --extract, tmds_channel.py, tmds_sparam.py)
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
# branch lengths of the first routed version (before the fix, audit item B), mm
OLD_BRANCH = {"HDMI_D0P_C": 21.0, "HDMI_D0N_C": 23.3, "HDMI_D1P_C": 20.9, "HDMI_D1N_C": 31.7, "HDMI_D2P_C": 29.8,
              "HDMI_D2N_C": 32.3, "HDMI_CKP_C": 29.2, "HDMI_CKN_C": 53.5}


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
    fig.savefig(os.path.join(OUT, "sim_zdiff_r2.png"), dpi=110)
    plt.close(fig)


def fig_compare():
    base = {"D0": (3.3, 162), "D1": (10.9, 162), "D2": (13.1, 153), "CK": (11.7, 163)}
    summ = json.load(open(os.path.join(HERE, "tmds_summary.json")))
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    names = list(base)
    x = np.arange(4)
    ax[0].bar(x - .18, [base[n][0] for n in names], .36, label="最初の配線（P/Nを個別に配線）", color="#c44")
    ax[0].bar(x + .18, [abs(summ[n]["skew"]) for n in names], .36, label="最終（ペア配線、是正後）", color="#4a4")
    ax[0].axhline(5, color="k", ls=":")
    ax[0].text(3.4, 5.3, "自主目標 5mm", fontsize=8, ha="right")
    ax[0].set_xticks(x)
    ax[0].set_xticklabels(names)
    ax[0].set_ylabel("ペア内スキュー |P-N| (mm)")
    ax[0].legend(fontsize=8)
    ax[1].bar(x - .18, [base[n][1] for n in names], .36, color="#c44")
    ax[1].bar(x + .18, [summ[n]["zmean"] for n in names], .36, color="#4a4")
    ax[1].axhspan(85, 115, color="g", alpha=.12)
    ax[1].text(-0.4, 118, "100Ω ±15%", fontsize=8)
    ax[1].set_xticks(x)
    ax[1].set_xticklabels(names)
    ax[1].set_ylabel("差動インピーダンス 平均 (Ω)")
    ax[1].set_ylim(0, 190)
    fig.suptitle("配線方式による改善（2Dソルバ＋実配線）")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_compare_r2.png"), dpi=110)
    plt.close(fig)


def fig_route():
    fig, ax = plt.subplots(figsize=(8.5, 9))
    ls = {"F.Cu": "-", "In2.Cu": "--", "B.Cu": ":"}
    for tag, p, n in tc.PAIRS:
        for net, pn in ((p, "P"), (n, "N")):
            for sfx in ("", "_C"):
                for s in tc.segs(None, net + sfx):
                    ax.plot([s[0], s[2]], [s[1], s[3]], color=COL[tag], ls=ls[s[5]], lw=1.3 if pn == "P" else 2.6,
                            alpha=.9 if pn == "P" else .45, solid_capstyle="round")
                for s in tc.branch_segs(net + sfx):
                    ax.plot([s[0], s[2]], [s[1], s[3]], color="k", ls=ls[s[5]], lw=0.8, alpha=.8)
        for net in (p + "_C", n + "_C"):
            for x, y in tc.GEOM_DATA.get(net, {}).get("vias", []):
                ax.plot(x, y, "ko", ms=2.5)
    for k, c in COL.items():
        ax.plot([], [], color=c, lw=2, label=k)
    ax.plot([], [], "k-", lw=.8, label="499Ω枝")
    ax.annotate("Core SODIMM", (86, 40), ha="right", fontsize=8)
    ax.annotate("HDMI\nコネクタ", (117.5, 20), fontsize=8)
    ax.annotate("AC結合 / ESD / 499Ω", (101, 7.2), fontsize=8)
    ax.set_xlim(84, 122)
    ax.set_ylim(58, 6)
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.legend(ncol=3, fontsize=8, loc="lower right")
    ax.set_title("TMDS 4組の実配線（細線=P、太線=N、黒細線=499Ω枝）", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_route_r2.png"), dpi=110)
    plt.close(fig)


def fig_sparam():
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.5))
    res = {}
    for tag, p, n in tc.PAIRS:
        M = sp.channel(tag, p, n)
        s11, s21 = sp.abcd_to_s(M)
        res[tag] = sp.metrics(s11, s21)
        ax[0][0].plot(sp.F / 1e9, 20 * np.log10(abs(s11)), color=COL[tag], label=tag)
        ax[0][1].plot(sp.F / 1e9, 20 * np.log10(abs(s21)), color=COL[tag], label=tag)
        sec = sp._SEC[tag]["core"]
        xs = np.cumsum([0] + [q[0] * 1e3 for q in sec])
        zs = [sec[0][1]] + [q[1] for q in sec]
        ax[1][0].plot(xs, zs, color=COL[tag], label=tag)
    ax[0][0].axhline(-10, color="k", ls=":")
    ax[0][0].set_ylim(-45, 0)
    ax[0][0].set_title("SDD11：Core側から見た反射（100Ω基準、ESD 0.35pF、枝あり）", fontsize=9)
    ax[0][1].set_title("SDD21：挿入損失")
    for a in (ax[0][0], ax[0][1]):
        a.set_xlabel("周波数 (GHz)")
        a.set_ylabel("dB")
        a.legend()
        a.axvline(0.371, color="gray", ls="--", lw=.8)
        a.axvline(1.5, color="gray", ls=":", lw=.8)
    ax[0][0].text(0.39, -4, "720p60 Nyquist", fontsize=7)
    ax[0][0].text(1.52, -4, "観察上限1.5GHz", fontsize=7)
    ax[1][0].axhspan(85, 115, color="g", alpha=.12)
    ax[1][0].set_title("Core側 キャリア配線の差動インピーダンス（2Dソルバ）")
    ax[1][0].set_xlabel("配線に沿った距離 (mm)")
    ax[1][0].set_ylabel("Ω")
    ax[1][0].legend()
    rows = ["ペア SDD11 371/742MHz   最大(<=1.5G)  SDD21 371/742MHz"]
    for tag, r in res.items():
        rows.append("%-3s %6.1f / %6.1f dB   %6.1f dB   %5.2f / %5.2f dB" % (tag, r["s11_371"], r["s11_742"], r["s11_max_1500"], r["s21_371"], r["s21_742"]))
    ax[1][1].axis("off")
    ax[1][1].text(0, 1, "\n".join(rows), va="top", family="monospace", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_sparam_r2.png"), dpi=110)
    plt.close(fig)
    json.dump(res, open(os.path.join(HERE, "report_sparam.json"), "w"), indent=1)
    return res


def worst(kw):
    """Worst-pair SDD11 maximum up to 1.5 GHz and SDD21 at 742 MHz for a parameter set."""
    w11, w21 = -99.0, 0.0
    i = int(np.argmin(abs(sp.F - 0.742e9)))
    for tag, p, n in tc.PAIRS:
        s11, s21 = sp.abcd_to_s(sp.channel(tag, p, n, **kw))
        w11 = max(w11, float(20 * np.log10(abs(s11[sp.F <= 1.5e9])).max()))
        w21 = min(w21, float(20 * np.log10(abs(s21[i]))))
    return w11, w21


def fig_variants():
    sc = [("理想（ESD・枝なし）", dict(esd_cd=0.0, branches=False)),
          ("是正後（現在の枝）", dict()),
          ("是正前の枝（21〜53mm）", dict(branch_len={k: v * 1e-3 for k, v in OLD_BRANCH.items()})),
          ("ESD 0.2pF", dict(esd_cd=0.2e-12)), ("ESD 0.35pF（基準）", dict()), ("ESD 0.5pF", dict(esd_cd=0.5e-12)),
          ("Core 85Ω", dict(core_z=85.0)), ("Core 100Ω（基準）", dict()), ("Core 115Ω", dict(core_z=115.0))]
    vals = [worst(kw) for _, kw in sc]
    colors = ["#888", "#4a4", "#c44"] + ["#69c"] * 3 + ["#c96"] * 3
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    y = np.arange(len(sc))
    ax[0].barh(y, [v[0] for v in vals], color=colors)
    ax[0].axvline(-10, color="k", ls=":")
    ax[0].set_yticks(y)
    ax[0].set_yticklabels([s[0] for s in sc])
    ax[0].invert_yaxis()
    ax[0].set_xlabel("SDD11 最大 (〜1.5GHz, dB)　悪い方のペア")
    ax[0].set_xlim(-30, 0)
    ax[1].barh(y, [v[1] for v in vals], color=colors)
    ax[1].set_yticks(y)
    ax[1].set_yticklabels([])
    ax[1].invert_yaxis()
    ax[1].set_xlabel("SDD21 @742MHz (dB)　悪い方のペア")
    fig.suptitle("是正の効果と、仮定値に対する感度")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_variants_r2.png"), dpi=110)
    plt.close(fig)
    out = {s[0]: dict(sdd11_max_1500=v[0], sdd21_742=v[1]) for s, v in zip(sc, vals)}
    json.dump(out, open(os.path.join(HERE, "report_variants.json"), "w"), indent=1, ensure_ascii=False)
    return out


def fig_sensitivity():
    Ls = np.linspace(0, 3e-9, 13)
    Cs = np.linspace(0, 1.5e-12, 13)
    grid = np.zeros((len(Cs), len(Ls)))
    grid2 = np.zeros_like(grid)
    for a, c in enumerate(Cs):
        for b, l in enumerate(Ls):
            grid[a, b], grid2[a, b] = worst(dict(socket_l=l, socket_c=c))
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    ext = [Ls[0] * 1e9, Ls[-1] * 1e9, Cs[0] * 1e12, Cs[-1] * 1e12]
    im = ax[0].imshow(grid, origin="lower", aspect="auto", extent=ext, cmap="RdYlGn_r", vmin=-25, vmax=0)
    cs = ax[0].contour(Ls * 1e9, Cs * 1e12, grid, levels=[-15, -10], colors="k")
    ax[0].clabel(cs, fmt="%d dB")
    plt.colorbar(im, ax=ax[0], label="SDD11 最大 (〜1.5GHz, dB)")
    ax[0].set_xlabel("SODIMM接点の直列L（差動, nH）")
    ax[0].set_ylabel("接点の並列C（差動, pF）")
    ax[0].set_title("反射（悪い方のペア）")
    im2 = ax[1].imshow(grid2, origin="lower", aspect="auto", extent=ext, cmap="RdYlGn", vmin=-3, vmax=0)
    plt.colorbar(im2, ax=ax[1], label="SDD21 @742MHz (dB)")
    ax[1].set_xlabel("直列L (nH)")
    ax[1].set_title("挿入損失（悪い方のペア）")
    fig.suptitle("SODIMM接点の寄生に対する余裕（感度解析）")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sim_sensitivity_r2.png"), dpi=110)
    plt.close(fig)
    json.dump(dict(L=list(Ls), C=list(Cs), sdd11=grid.tolist(), sdd21=grid2.tolist()), open(os.path.join(HERE, "report_sensitivity.json"), "w"))
    return float(grid[0, 0])


if __name__ == "__main__":
    tc.load()
    fig_zdiff()
    fig_compare()
    fig_route()
    print(fig_sparam())
    print(fig_variants())
    print("sensitivity: worst SDD11 with ideal socket", fig_sensitivity())
