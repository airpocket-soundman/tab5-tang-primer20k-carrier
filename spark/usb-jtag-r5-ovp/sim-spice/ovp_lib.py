"""OVP(C案)シミュレーション共通ライブラリ: ngspice ラッパ + ネットリスト生成。

import しても何も実行されない(ngspice.dll の読み込みだけ)。
ngspice.dll は KiCad 同梱を使う(ダウンロード不要)。場所を変えたい場合は
環境変数 OVP_NGSPICE_DLL にフルパスを指定する。

通常の Python(64bit) から使える:  python run_all.py
"""
import ctypes
import os
import re
import tempfile

DLL_PATH = os.environ.get("OVP_NGSPICE_DLL", r"C:\Program Files\KiCad\10.0\bin\ngspice.dll")

_dll = None
_OUT = []

SEND = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
STAT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
EXIT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)


@SEND
def _send(msg, ident, user):
    _OUT.append(msg.decode(errors="replace"))
    return 0


@STAT
def _stat(msg, ident, user):
    return 0


@EXIT
def _exit(a, b, c, d, e):
    return 0


def _init():
    global _dll
    if _dll is not None:
        return
    d = os.path.dirname(DLL_PATH)
    if hasattr(os, "add_dll_directory") and os.path.isdir(d):
        os.add_dll_directory(d)
    _dll = ctypes.CDLL(DLL_PATH)
    _dll.ngSpice_Init(_send, _stat, _exit, None, None, None, None)


_NUM = r"[-+0-9.eE]+"


def _parse(lines):
    res = {}
    for l in lines:
        m = re.match(r"stdout\s+(\w+)\s*=\s*(" + _NUM + ")", l)
        if m:
            res[m.group(1)] = float(m.group(2))
        elif "stderr" in l and ("rror" in l):
            res.setdefault("err", []).append(l[:160])
    return res


def version():
    """ngspice のバージョン文字列(取得できなければ空)。"""
    _init()
    _OUT.clear()
    _dll.ngSpice_Command(b"version")
    return " ".join(l.replace("stdout ", "").strip() for l in _OUT if l.strip())[:300]


class Sim:
    """1回のトランジェントを実行し、その結果に対して .meas を何度でも投げられる。"""

    def __init__(self, netlist):
        _init()
        fd, self.fn = tempfile.mkstemp(suffix=".cir", prefix="ovp_")
        with os.fdopen(fd, "w", encoding="ascii") as f:
            f.write(netlist)
        _OUT.clear()
        _dll.ngSpice_Command(b"destroy all")
        _dll.ngSpice_Command(("source " + self.fn.replace("\\", "/")).encode())
        _dll.ngSpice_Command(b"run")
        self.log = list(_OUT)
        self.errors = [l for l in self.log if "stderr" in l and "rror" in l]

    def meas(self, cmd):
        """'meas tran x MAX v(vout)' のような1コマンドを実行し {x: 値} を返す(失敗なら空)。"""
        _OUT.clear()
        _dll.ngSpice_Command(cmd.encode())
        return _parse(_OUT)

    def close(self):
        try:
            os.remove(self.fn)
        except OSError:
            pass


MODELS = """
.model AO3401 PMOS(LEVEL=1 VTO=-0.9 KP=4.07 LAMBDA=0.01)
.model DAO D(IS=1e-12 RS=0.02 CJO=100p BV=40)
.model N2N7002 NMOS(LEVEL=1 VTO={vtn} KP=0.147 LAMBDA=0.01)
.model Q3904 NPN(IS=6.734f XTI=3 EG=1.11 VAF=74.03 BF=416.4 NE=1.259 ISE=6.734f IKF=66.78m XTB=1.5 BR=.7371 NC=2 RC=1 CJC=3.638p MJC=.3085 VJC=.75 FC=.5 CJE=4.493p MJE=.2593 VJE=.75 TR=239.5n TF=301.2p ITF=.4 VTF=4 XTF=2 RB=10)
.model DZ D(IS=1e-14 N=1 BV={bv} IBV=5m NBV={nbv} RS=30 CJO=100p)
"""

# 確定値(回路図と一致)
NOMINAL = dict(vz=6.2, nbv=3, vtn=1.6, temp=27, r91=10e3, r92=100e3, r93=1e3, r94=4.7e3)


def netlist(vin_src, tstop, tstep, load="5", cload="10u", vz=6.2, nbv=3, vtn=1.6,
            temp=27, r91=10e3, r92=100e3, r93=1e3, r94=4.7e3):
    """OVP 回路のネットリスト。

    Q9=AO3401A(M1) / R91 / Q10=2N7002(M2) / R92 / Q11=MMBT3904 / D12 / R93 / R94。
    vz はゼナーの BV(5mA 時の電圧) [V]。nbv は低電流域のドループ(NBV)。
    """
    models = MODELS.format(bv=vz, nbv=nbv, vtn=vtn)
    return f"""OVP
.options temp={temp}
Vin vin 0 {vin_src}
* Q9: PMOS series, S=vin(VBUS_PD) D=vout(VBUS_PGM) G=g(OVP_G)
M1 vout g vin vin AO3401
Dbd vout vin DAO
Cgs g vin 700p
Cgd g vout 100p
R91 vin g {r91}
* Q10: NMOS, D=g S=GND G=ng(OVP_NG)
M2 g ng 0 0 N2N7002
Cgs2 ng 0 30p
R92 vin ng {r92}
* Q11: NPN, C=ng E=GND B=b(OVP_B)
Q11 ng b 0 Q3904
* D12: cathode=vin, anode=z(OVP_Z)
D12b z vin DZ
R93 z b {r93}
R94 b 0 {r94}
Rload vout 0 {load}
Cload vout 0 {cload}
{models}
.tran {tstep} {tstop}
.end
"""


def corners16():
    """Vz=±5%, NBV=1/6, 温度 -20/85, Vth(2N7002) 1.0/2.5 の 2^4=16 通り。"""
    out = []
    for tol in (-0.05, 0.05):
        for nbv in (1, 6):
            for T in (-20, 85):
                for vtn in (1.0, 2.5):
                    out.append(dict(vz=6.2 * (1 + tol), nbv=nbv, temp=T, vtn=vtn,
                                    tag=f"Vz{tol:+.0%} NBV{nbv} T{T} Vth{vtn}"))
    return out


def corners36():
    """温度 -20/27/85 と Vth 1.0/1.6/2.5 の 3 値まで広げた 2*2*3*3=36 通り(補足確認用)。"""
    out = []
    for tol in (-0.05, 0.05):
        for nbv in (1, 6):
            for T in (-20, 27, 85):
                for vtn in (1.0, 1.6, 2.5):
                    out.append(dict(vz=6.2 * (1 + tol), nbv=nbv, temp=T, vtn=vtn,
                                    tag=f"Vz{tol:+.0%} NBV{nbv} T{T} Vth{vtn}"))
    return out


def run_peak(vin_src, tstop, tstep, **kw):
    """Vout のピークと、そのときの Vin、tstop 直前の Vout を返す。"""
    s = Sim(netlist(vin_src, tstop, tstep, **kw))
    try:
        vpk = s.meas("meas tran vpk MAX v(vout)").get("vpk")
        vin_pk = None
        if vpk is not None:
            # ピーク電圧に最後に達した時点(=ピーク直後)の Vin
            vin_pk = s.meas(f"meas tran vinpk FIND v(vin) WHEN v(vout)={vpk * 0.9999:.6f} CROSS=LAST").get("vinpk")
        return dict(vpk=vpk, vin_at_peak=vin_pk, errors=s.errors)
    finally:
        s.close()
