"""OVP(C案) 全ケース一括実行。結果を results.json に保存する。

使い方(このディレクトリで):
    python run_all.py            # ケース a〜g を全部(数分以内)
    python run_all.py a e g      # 指定ケースだけ実行し、results.json の該当部分を更新
ケース: a=正常時DC  b=スローランプ(コーナー)  c=PDステップ  d=高速ランプ
        e=5.5V誤遮断なし  f=部品値感度  g=12V/20V定常(電流・電力)

前提: KiCad 同梱の ngspice.dll(環境変数 OVP_NGSPICE_DLL で変更可)。
モデルは汎用の簡易モデルで、メーカー提供のSPICEモデルではない。結果は「この仮定下の机上値」。
出力は UTF-8。
"""
import itertools
import json
import os
import sys
import time

from ovp_lib import Sim, corners16, corners36, netlist, run_peak, version, NOMINAL

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.json")

NOM = dict(vz=6.2, nbv=3, vtn=1.6, temp=27, tag="nominal")


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return dict(min=None, max=None, width=None, n=0)
    return dict(min=round(min(vals), 4), max=round(max(vals), 4), width=round(max(vals) - min(vals), 4), n=len(vals))


def cparams(c):
    return {k: c[k] for k in ("vz", "nbv", "vtn", "temp")}


# ---------------------------------------------------------------- a
def case_a():
    out = {}
    for v in (4.75, 5.0, 5.5):
        row = {}
        for label, load in (("1A(5ohm)", "5"), ("open(1Gohm)", "1G")):
            s = Sim(netlist(f"PWL(0 0 100u {v})", "1m", "1u", load=load, cload="10u"))
            vo = s.meas("meas tran vo FIND v(vout) AT=0.9m").get("vo")
            iin = s.meas("meas tran ii FIND i(Vin) AT=0.9m").get("ii")
            s.close()
            row[label] = dict(vout=vo, drop=None if vo is None else v - vo,
                              i_in_mA=None if iin is None else -iin * 1e3)
        # 4.75V での Vout/降下の16コーナー最悪値(1A)
        drops = []
        for c in corners16():
            s = Sim(netlist(f"PWL(0 0 100u {v})", "1m", "1u", load="5", cload="10u", **cparams(c)))
            vo = s.meas("meas tran vo FIND v(vout) AT=0.9m").get("vo")
            s.close()
            drops.append(None if vo is None else v - vo)
        row["drop_1A_16corners"] = stats(drops)
        out[f"{v}V"] = row
    return out


# ---------------------------------------------------------------- b
def case_b():
    """0→15V, 1V/ms。遮断(Voutピーク)電圧。負荷10Ω+10uF。"""
    src, tstop, tstep = "PWL(0 0 15m 15)", "15m", "5u"
    nom = run_peak(src, tstop, tstep, load="10", cload="10u", **cparams(NOM))
    rows = []
    for c in corners16():
        r = run_peak(src, tstop, tstep, load="10", cload="10u", **cparams(c))
        rows.append(dict(tag=c["tag"], vpk=r["vpk"], vin_at_peak=r["vin_at_peak"]))
    rows36 = []
    for c in corners36():
        r = run_peak(src, tstop, tstep, load="10", cload="10u", **cparams(c))
        rows36.append(dict(tag=c["tag"], vpk=r["vpk"], vin_at_peak=r["vin_at_peak"]))
    # 刻み収束確認(公称)
    conv = {ts: run_peak(src, tstop, ts, load="10", cload="10u", **cparams(NOM))["vpk"] for ts in ("20u", "5u", "2u")}
    return dict(nominal=dict(vpk=nom["vpk"], vin_at_peak=nom["vin_at_peak"]),
                corners16=rows, stats16=stats([r["vpk"] for r in rows]),
                stats16_vin=stats([r["vin_at_peak"] for r in rows]),
                corners36_stats=stats([r["vpk"] for r in rows36]),
                step_convergence_nominal=conv,
                worst_low=min(rows, key=lambda r: r["vpk"]), worst_high=max(rows, key=lambda r: r["vpk"]))


# ---------------------------------------------------------------- c
def case_c():
    """5V→12V を 30mV/us(約233us)。start 100us。"""
    src = "PWL(0 5 100u 5 333u 12 600u 12)"
    loads = {"10ohm+1uF": ("10", "1u"), "5ohm+10uF": ("5", "10u"), "1kohm+1uF(軽負荷)": ("1k", "1u")}
    out = {}
    for lname, (load, cl) in loads.items():
        rows = []
        for c in [NOM] + corners16():
            s = Sim(netlist(src, "600u", "0.5u", load=load, cload=cl, **cparams(c)))
            vpk = s.meas("meas tran vpk MAX v(vout)").get("vpk")
            vend = s.meas("meas tran ve FIND v(vout) AT=0.59m").get("ve")
            vin_pk = None
            if vpk:
                vin_pk = s.meas(f"meas tran vinpk FIND v(vin) WHEN v(vout)={vpk * 0.9999:.6f} CROSS=LAST").get("vinpk")
            s.close()
            rows.append(dict(tag=c["tag"], vpk=vpk, vin_at_peak=vin_pk, vout_after_cutoff=vend))
        out[lname] = dict(rows=rows, stats_vpk=stats([r["vpk"] for r in rows[1:]]),
                          nominal=rows[0], max_vout_after=max(r["vout_after_cutoff"] for r in rows if r["vout_after_cutoff"] is not None))
    return out


# ---------------------------------------------------------------- d
def case_d():
    """0→12V を 12us (1V/us)。R91=10k と 4.7k。参考値。"""
    src = "PWL(0 0 12u 12 200u 12)"
    out = {}
    for r91 in (10e3, 4.7e3):
        rows = []
        for c in [NOM] + corners16():
            s = Sim(netlist(src, "200u", "0.1u", load="10", cload="1u", r91=r91, **cparams(c)))
            vpk = s.meas("meas tran vpk MAX v(vout)").get("vpk")
            vend = s.meas("meas tran ve FIND v(vout) AT=0.19m").get("ve")
            vin_pk = None
            if vpk:
                vin_pk = s.meas(f"meas tran vinpk FIND v(vin) WHEN v(vout)={vpk * 0.9999:.6f} CROSS=LAST").get("vinpk")
            s.close()
            rows.append(dict(tag=c["tag"], vpk=vpk, vin_at_peak=vin_pk, vout_end=vend))
        out[f"R91={r91 / 1e3:g}k"] = dict(nominal=rows[0], stats_vpk=stats([r["vpk"] for r in rows[1:]]),
                                         rows=rows[1:])
    return out


# ---------------------------------------------------------------- e
def case_e():
    out = {}
    for load, lname in (("5", "1A"), ("1G", "open")):
        rows = []
        for c in [NOM] + corners16():
            s = Sim(netlist("PWL(0 0 100u 5.5)", "1m", "1u", load=load, cload="10u", **cparams(c)))
            vo = s.meas("meas tran vo FIND v(vout) AT=0.95m").get("vo")
            s.close()
            rows.append(dict(tag=c["tag"], vout=vo))
        thr = 5.3 if load == "5" else 5.45
        bad = [r["tag"] for r in rows if r["vout"] is None or r["vout"] < thr]
        out[lname] = dict(rows=rows, false_trips=bad, n=len(rows), vout_min=min(r["vout"] for r in rows),
                          threshold_for_pass=thr)
    return out


# ---------------------------------------------------------------- f
def trip_window(vz_nom, r91, r93, r94):
    vals = []
    for c in corners16():
        kw = cparams(c)
        kw["vz"] = vz_nom * (1 + (c["vz"] / 6.2 - 1))  # 同じ ±5%
        r = run_peak("PWL(0 0 12m 12)", "12m", "10u", load="10", cload="10u", r91=r91, r93=r93, r94=r94, **kw)
        vals.append(r["vpk"])
    nomr = run_peak("PWL(0 0 12m 12)", "12m", "10u", load="10", cload="10u", r91=r91, r93=r93, r94=r94,
                    vz=vz_nom, nbv=3, vtn=1.6, temp=27)["vpk"]
    return dict(nominal=nomr, **stats(vals))


def case_f():
    cfgs = []
    for vz, r91, r93, r94 in itertools.product((5.6, 6.2, 6.8), (4.7e3, 10e3, 22e3), (1e3, 4.7e3), (2.2e3, 4.7e3, 10e3)):
        w = trip_window(vz, r91, r93, r94)
        cfgs.append(dict(vz=vz, r91_k=r91 / 1e3, r93_k=r93 / 1e3, r94_k=r94 / 1e3, **w))
    cur = next(c for c in cfgs if c["vz"] == 6.2 and c["r91_k"] == 10 and c["r93_k"] == 1 and c["r94_k"] == 4.7)
    better = [c for c in cfgs if c["min"] is not None and c["min"] >= 5.5 and c["max"] < cur["max"] - 0.02]
    better.sort(key=lambda c: c["max"])
    # 補足: Vz=6.2V 固定で R93/R94 を細かく振り、窓を「上限が下がる向き」にずらせるか見る(E系列の市販値)
    fine = []
    for r93, r94 in itertools.product((330, 470, 680, 1e3), (4.7e3, 5.6e3, 6.8e3, 8.2e3, 10e3)):
        w = trip_window(6.2, 10e3, r93, r94)
        fine.append(dict(vz=6.2, r91_k=10.0, r93_k=r93 / 1e3, r94_k=r94 / 1e3, **w))
    fine_better = [c for c in fine if c["min"] is not None and c["min"] >= 5.5 and c["max"] < cur["max"] - 0.02]
    fine_better.sort(key=lambda c: c["max"])
    return dict(configs=cfgs, current=cur, recommended_candidates=better,
                fine_scan_vz6p2=fine, fine_scan_candidates=fine_better)


# ---------------------------------------------------------------- g
def case_g():
    out = {}
    for V in (12.0, 20.0):
        rows = []
        for c in [NOM] + corners16():
            s = Sim(netlist(f"PWL(0 0 1m {V})", "4m", "2u", load="10", cload="10u", **cparams(c)))
            t = "3.9m"
            m = {}
            for name, expr in (("vin", "v(vin)"), ("vout", "v(vout)"), ("vg", "v(g)"), ("vng", "v(ng)"),
                               ("vb", "v(b)"), ("vz", "v(z)"), ("iin", "i(Vin)")):
                m[name] = s.meas(f"meas tran {name} FIND {expr} AT={t}").get(name)
            s.close()
            if None in m.values():
                rows.append(dict(tag=c["tag"], error="meas failed", m=m))
                continue
            iz = (m["vz"] - m["vb"]) / NOMINAL["r93"]
            ib = iz - m["vb"] / NOMINAL["r94"]
            ic = (m["vin"] - m["vng"]) / NOMINAL["r92"]
            rows.append(dict(
                tag=c["tag"], vout=m["vout"], vsg_q9=m["vin"] - m["vg"], v_ng=m["vng"],
                i_d12_mA=iz * 1e3, v_d12=m["vin"] - m["vz"], p_d12_mW=(m["vin"] - m["vz"]) * iz * 1e3,
                i_q11_c_mA=ic * 1e3, i_q11_b_mA=ib * 1e3,
                p_q11_mW=(m["vng"] * ic + m["vb"] * ib) * 1e3,
                p_r93_mW=iz * iz * NOMINAL["r93"] * 1e3, p_r92_mW=ic * ic * NOMINAL["r92"] * 1e3,
                i_vbus_mA=-m["iin"] * 1e3))
        good = [r for r in rows if "error" not in r]
        out[f"{V:g}V"] = dict(
            rows=rows,
            max_vout=max(r["vout"] for r in good), max_vsg_q9=max(r["vsg_q9"] for r in good),
            max_i_d12_mA=max(r["i_d12_mA"] for r in good), max_p_d12_mW=max(r["p_d12_mW"] for r in good),
            max_i_q11_b_mA=max(r["i_q11_b_mA"] for r in good), max_p_q11_mW=max(r["p_q11_mW"] for r in good),
            max_p_r93_mW=max(r["p_r93_mW"] for r in good), max_p_r92_mW=max(r["p_r92_mW"] for r in good),
            max_i_vbus_mA=max(r["i_vbus_mA"] for r in good))
    return out


CASES = dict(a=case_a, b=case_b, c=case_c, d=case_d, e=case_e, f=case_f, g=case_g)


def main(argv):
    sel = [x for x in argv if x in CASES] or list(CASES)
    res = {}
    if os.path.exists(RESULTS) and len(sel) < len(CASES):
        with open(RESULTS, encoding="utf-8") as f:
            res = json.load(f)
    res["meta"] = dict(ngspice=version(), note="汎用簡易モデルによる机上値。メーカーSPICEモデルではない。",
                       circuit=dict(NOMINAL))
    timing = res.setdefault("elapsed_s", {})
    for k in sel:
        t0 = time.time()
        print(f"== case {k} ...", flush=True)
        res[f"case_{k}"] = CASES[k]()
        timing[k] = round(time.time() - t0, 1)
        print(f"   done {timing[k]} s", flush=True)
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("saved", RESULTS)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
