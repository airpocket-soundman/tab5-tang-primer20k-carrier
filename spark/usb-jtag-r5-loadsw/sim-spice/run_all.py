"""r5 ロードスイッチ式(+5V 経路を SW4 の接点ではなく PMOS で通す案)の ngspice 検証。

汎用の簡易モデルによる机上検証。メーカーのSPICEモデルではない。実機は未検証。
実行: python run_all.py   (通常の Python 3 / 64bit。KiCad 同梱の ngspice.dll を使う)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spice_lib import Sim  # noqa: E402  (ngspice ラッパ。r5-ovp の ovp_lib.py と同じもの)

H = Path(__file__).resolve().parent

MODELS = """
.model AO3401 PMOS(LEVEL=1 VTO={vtp} KP=4.07 LAMBDA=0.01)
.model DAO D(IS=1e-12 RS=0.02 CJO=100p BV=40)
.model DZ D(IS=1e-14 N=1 BV={bv} IBV=5m NBV={nbv} RS=30 CJO=100p)
"""

# 確定値(この案の部品値)
NOM = dict(vtp=-0.9, vz=6.2, nbv=3, temp=27, rpu=100e3, rd=4.7e3, rkg=100e3)


RKG = float(__import__("os").environ.get("LS_RKG", "10e3"))  # ガード検出抵抗(Qk のゲート側)。既定 10k


def netlist(vbuck, vbus, run, pgm, load, tstop="20m", vtp=-0.9, vz=6.2, nbv=3, temp=27,
            rpu=100e3, rd=4.7e3, rkg=RKG, guard=True, v5pre=None):
    """vbuck / vbus は SPICE の電圧源記述('DC 5' や 'PWL(...)')。run / pgm は SW4 の位置(True=その経路を ON にする)。"""
    models = MODELS.format(vtp=vtp, bv=vz, nbv=nbv)
    sw_run = f"Rswr gr 0 {rd}\n" if run else ""
    sw_pgm = f"Rswp gp 0 {rd}\n" if pgm else ""
    g = (f"Mk gp kg scp scp AO3401\nDkb gp scp DAO\nRkg scp kg {rkg}\nDz 0 kg DZ\nCkg kg 0 10p\n" if guard else "")
    pre = f".ic v(v5)={v5pre}\n" if v5pre is not None else ""
    return f"""loadsw
.options temp={temp}
Vb bk0 0 {vbuck}
Rb bk0 bk 0.05
Vv vb0 0 {vbus}
Rv vb0 vbus 0.05
* RUN path: BUCK_5V(bk) <-> +5V(v5), back-to-back PMOS with common source scr
M1 bk gr scr scr AO3401
M2 v5 gr scr scr AO3401
Db1 bk scr DAO
Db2 v5 scr DAO
Cgs1 gr scr 700p
Rpur scr gr {rpu}
{sw_run}
* PGM path: VBUS_PD(vbus) <-> +5V(v5), back-to-back PMOS with common source scp
M3 vbus gp scp scp AO3401
M4 v5 gp scp scp AO3401
Db3 vbus scp DAO
Db4 v5 scp DAO
Cgs3 gp scp 700p
Rpup scp gp {rpu}
{sw_pgm}
* PGM path over-voltage guard: PMOS Mk pulls gp up to scp when VBUS exceeds about 7V
{g}
Rload v5 0 {load}
Cload v5 0 100u
Rleak v5 0 1Meg
Rleak2 scr 0 100Meg
Rleak3 scp 0 100Meg
Rleak4 gr 0 100Meg
Rleak5 gp 0 100Meg
{pre}
{models}
.tran 10u {tstop}
.end
"""


_VEC = ("v(v5)", "i(Vb)", "i(Vv)", "v(scr)", "v(scp)", "v(gp)")


def _wave(s):
    """波形を wrdata でファイルへ出し、{時刻: [値...]} の列を返す(ngspice の meas AT が不安定なため)。"""
    import os
    import tempfile
    import spice_lib as L
    fd, fn = tempfile.mkstemp(suffix=".dat", prefix="ls_")
    os.close(fd)
    L._OUT.clear()
    L._dll.ngSpice_Command(("wrdata " + fn.replace("\\", "/") + " " + " ".join(_VEC)).encode())
    rows = []
    for line in open(fn):
        p = line.split()
        if len(p) < 2 * len(_VEC):
            continue
        t = float(p[0])
        rows.append((t, [float(p[1 + 2 * i]) for i in range(len(_VEC))]))
    os.remove(fn)
    return rows


def run(label, **kw):
    s = Sim(netlist(**kw))
    try:
        rows = _wave(s)
        idx = {n: i for i, n in enumerate(_VEC)}
        last = rows[-1][1]
        out = {"v5": last[idx["v(v5)"]], "v5max": max(r[1][idx["v(v5)"]] for r in rows),
               "i_bk": last[idx["i(Vb)"]], "i_vbus": last[idx["i(Vv)"]],
               "vscr": last[idx["v(scr)"]], "vscp": last[idx["v(scp)"]],
               "n_points": len(rows), "t_end": rows[-1][0], "errors": s.errors}
        # 時刻付き: PGM 経路のピーク(ランプ区間 5〜9ms と 全体)
        out["v5max_after_5ms"] = max(r[1][idx["v(v5)"]] for r in rows if r[0] >= 0.005)
        return out
    finally:
        s.close()


def corners():
    out = []
    for vtp in (-0.6, -1.3):
        for vz_tol in (-0.05, 0.05):
            for nbv in (1, 6):
                for T in (-20, 85):
                    out.append(dict(vtp=vtp, vz=6.2 * (1 + vz_tol), nbv=nbv, temp=T))
    return out


def tag(c):
    return f"Vtp{c['vtp']} Vz{c['vz']:.2f} NBV{c['nbv']} T{c['temp']}"


def main():
    res = {}
    LOAD = 5  # 1A 相当(5V/5Ω)

    cases = [
        ("a_RUN_12V_USB", dict(vbuck="DC 5", vbus="DC 12", run=True, pgm=False, load=LOAD)),
        ("b_RUN_DC_only", dict(vbuck="DC 5", vbus="DC 0", run=True, pgm=False, load=LOAD)),
        ("c_OFF_both_present", dict(vbuck="DC 5", vbus="DC 5", run=False, pgm=False, load=LOAD)),
        ("d_PGM_5V", dict(vbuck="DC 0", vbus="DC 5", run=False, pgm=True, load=LOAD)),
        ("e_PGM_5V5", dict(vbuck="DC 0", vbus="DC 5.5", run=False, pgm=True, load=LOAD)),
        ("f_PGM_12V_misuse", dict(vbuck="DC 0", vbus="DC 12", run=False, pgm=True, load=LOAD)),
        ("g_PGM_DC_only", dict(vbuck="DC 5", vbus="DC 0", run=False, pgm=True, load=LOAD)),
        ("h_PGM_VBUS_ramp_5to12", dict(vbuck="DC 0", vbus="PWL(0 5 5m 5 6m 12 20m 12)", run=False, pgm=True, load=LOAD)),
        ("i_RUN_to_PGM_VBUS12_ramp_down", dict(vbuck="DC 0", vbus="PWL(0 12 5m 12 15m 5 20m 5)", run=False, pgm=True, load=LOAD)),
        ("j_PGM_12V_noguard_reference", dict(vbuck="DC 0", vbus="DC 12", run=False, pgm=True, load=LOAD, guard=False)),
    ]
    for name, kw in cases:
        res[name] = run(name, **kw)
        r = res[name]
        print(name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "errors"}, r["errors"][:1])

    # コーナー: 通常 PGM(5V/5.5V)で v5 が十分高い・ガードが誤動作しない / 12V 誤用で v5 が低いまま
    cs = corners()
    cn = {"pgm_5V": [], "pgm_5V5": [], "pgm_12V": [], "pgm_ramp": [], "slow_ramp_0_15V": []}
    for c in cs:
        for key, kw in (("pgm_5V", dict(vbus="DC 5")), ("pgm_5V5", dict(vbus="DC 5.5")),
                        ("pgm_12V", dict(vbus="DC 12")), ("pgm_ramp", dict(vbus="PWL(0 5 5m 5 6m 12 20m 12)")),
                        ("slow_ramp_0_15V", dict(vbus="PWL(0 0 15m 15 20m 15)"))):
            r = run(tag(c), vbuck="DC 0", run=False, pgm=True, load=LOAD, **kw, **c)
            cn[key].append(dict(corner=tag(c), v5=r["v5"], v5max=r["v5max"]))
    res["corners"] = {k: dict(min_v5=min(x["v5"] for x in v), max_v5=max(x["v5"] for x in v),
                              max_v5peak=max(x["v5max"] for x in v), detail=v) for k, v in cn.items()}
    for k, v in res["corners"].items():
        print("corners", k, "v5 min/max", round(v["min_v5"], 3), round(v["max_v5"], 3), "peak", round(v["max_v5peak"], 3))
    (H / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf8")


if __name__ == "__main__":
    main()
