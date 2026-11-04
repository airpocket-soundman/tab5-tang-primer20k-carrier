#!/usr/bin/env python3
"""YOLOv8 n/s/m/l/x をDDR3常駐重みで動かす場合の見積もり。すべて「見積もり」であり実測ではない。

実機・FPGAツールには触れない純粋な算術。YOLOv8の層構成(ultralytics yaml)を再構成して
パラメータ数・MAC数・活性サイズ・DDR3トラフィックを数える。公表値(記憶ベース、出典未照合)と突き合わせる。
使い方:  python fpga/npu/estimate_yolo_ddr3.py [--json out.json]
"""
import argparse, json, math, sys
sys.stdout.reconfigure(encoding="utf-8")

# (深さ倍率, 幅倍率, 最大チャンネル)  ultralytics yolov8.yaml のscales
SCALES = {"n": (0.33, 0.25, 1024), "s": (0.33, 0.50, 1024), "m": (0.67, 0.75, 768),
          "l": (1.00, 1.00, 512), "x": (1.00, 1.25, 512)}
# 公表値(記憶ベース・出典未照合): params[M], FLOPs@640[G] (FLOPs=2*MAC)
PUBLISHED = {"n": (3.2, 8.7), "s": (11.2, 28.6), "m": (25.9, 78.9), "l": (43.7, 165.2), "x": (68.2, 257.8)}

# --- DDR3 (BIST実測と理論値は区別する) ---
DDR_USER_HZ = 99.5625e6
DDR_BEAT_BYTES = 16                               # 128bit/ビート
DDR_THEORY_BW = DDR_USER_HZ * DDR_BEAT_BYTES      # 約1.593GB/s (理論値)
BIST_CYC_PER_BEAT = 31                            # BIST実測: 約31サイクル/ビート/相
DDR_BIST_BW_LOW = DDR_USER_HZ / BIST_CYC_PER_BEAT * DDR_BEAT_BYTES   # 約51MB/s (1相=1ビートと解釈、解釈は未確認)
DDR_BIST_BW_HIGH = DDR_BIST_BW_LOW * 2            # 「相」の数え方が不明なため2倍まで幅を持たせる(未確認)
BSRAM_BYTES = 46 * 18 * 1024 // 8                 # 105,984B
PSRAM_BYTES = 32 * 1024 * 1024
DDR3_BYTES = 128 * 1024 * 1024
LINK_BW = 20e6                                    # 20MHz x 8bit 前提

# P4の持続MAC/s (esp-dl issue #339 実測ベース。docの出典節を参照)
P4_BEST = 4.446e9         # 重みがキャッシュに収まる3x3 convの最良
P4_OVERALL_HIGH = 1.66e9  # YOLOv8n 320 の全体実効(高)
P4_OVERALL_LOW = 0.67e9   # 同(低)
P4_PSRAM_BOUND = 0.14e9   # 重み144KB超の層(PSRAM帯域律速)の実測下限138〜204MMAC/s


class Net:
    def __init__(self, scale, res, nc=80):
        d, w, maxc = SCALES[scale]
        self.scale, self.res, self.nc = scale, res, nc
        self.layers = []            # dict(name, w_bytes, mac, in_b, out_b, held)
        self.params = 0
        self.held = 0
        r = lambda c: int(math.ceil(min(c, maxc) * w / 8) * 8)   # 8の倍数に丸め(ultralyticsのmake_divisible相当)
        n = lambda k: max(round(k * d), 1)

        def conv(name, cin, cout, k, hw, stride=1):
            ohw = hw // stride
            wb = cin * cout * k * k + cout        # INT8重み + バイアス(BN融合後)
            mac = cin * cout * k * k * ohw * ohw
            self.params += wb
            self.layers.append(dict(name=name, w_bytes=wb, mac=mac, in_b=cin * hw * hw,
                                    out_b=cout * ohw * ohw, held=self.held))

        def c2f(name, cin, cout, nrep, hw):
            c = cout // 2
            conv(name + ".cv1", cin, 2 * c, 1, hw)
            for i in range(nrep):
                conv(f"{name}.b{i}a", c, c, 3, hw); conv(f"{name}.b{i}b", c, c, 3, hw)
            conv(name + ".cv2", (2 + nrep) * c, cout, 1, hw)

        c1, c2, c3, c4, c5 = r(64), r(128), r(256), r(512), r(1024)
        hw = res
        conv("stem", 3, c1, 3, hw, 2); hw //= 2
        conv("conv1", c1, c2, 3, hw, 2); hw //= 2
        c2f("c2f1", c2, c2, n(3), hw)
        conv("conv2", c2, c3, 3, hw, 2); hw //= 2
        c2f("c2f2", c3, c3, n(6), hw); hw3 = hw; self.held += c3 * hw * hw
        conv("conv3", c3, c4, 3, hw, 2); hw //= 2
        c2f("c2f3", c4, c4, n(6), hw); hw4 = hw; self.held += c4 * hw * hw
        conv("conv4", c4, c5, 3, hw, 2); hw //= 2
        c2f("c2f4", c5, c5, n(3), hw)
        h = c5 // 2
        conv("sppf.cv1", c5, h, 1, hw); conv("sppf.cv2", 4 * h, c5, 1, hw)
        hw5 = hw; self.held += c5 * hw * hw
        # neck: concat入力は(アップサンプル後+スキップ)のチャンネル和
        hw = hw4
        c2f("n1", c5 + c4, c4, n(3), hw); self.held += c4 * hw * hw
        hw = hw3
        c2f("n2", c4 + c3, c3, n(3), hw); self.held += c3 * hw * hw
        conv("n3.down", c3, c3, 3, hw, 2); hw = hw4
        c2f("n4", c3 + c4, c4, n(3), hw); self.held += c4 * hw * hw
        conv("n5.down", c4, c4, 3, hw, 2); hw = hw5
        c2f("n6", c4 + c5, c5, n(3), hw)
        # Detect (reg_max=16)
        c2d = max(16, c3 // 4, 64); c3d = max(c3, min(nc, 100))
        for chn, hwx in ((c3, hw3), (c4, hw4), (c5, hw5)):
            conv("det.r1", chn, c2d, 3, hwx); conv("det.r2", c2d, c2d, 3, hwx); conv("det.r3", c2d, 64, 1, hwx)
            conv("det.c1", chn, c3d, 3, hwx); conv("det.c2", c3d, c3d, 3, hwx); conv("det.c3", c3d, nc, 1, hwx)
        self.anchors = hw3 ** 2 + hw4 ** 2 + hw5 ** 2
        self.out_bytes = (nc + 4) * self.anchors      # DFL後のbox4+cls80(INT8想定)
        self.raw_out_bytes = (64 + nc) * self.anchors  # DFL前の生出力
        self.in_bytes = 3 * res * res

    @property
    def macs(self): return sum(l["mac"] for l in self.layers)

    @property
    def weight_bytes(self): return self.params   # INT8: 1B/param

    def peak_act(self):
        """(低, 高)。低=1演算の入力+出力の最大(concatは入力に含む)、高=低+保持中のスキップ接続。"""
        lo = max(l["in_b"] + l["out_b"] for l in self.layers)
        hi = max(l["in_b"] + l["out_b"] + l["held"] for l in self.layers)
        return lo, hi

    def ddr_traffic(self, wbuf, abuf, overhead=1.0):
        """層ごとに2戦略の小さい方。A: 重みを1回、入力を重みブロック数だけ再読込。
        B: 空間タイル毎に重みを再読込、入出力は1回。入出力がabufに収まる層は活性のDDR3往復なし。
        戻り値 (重み転送B, 活性転送B)"""
        wt = at = 0
        for l in self.layers:
            io = l["in_b"] + l["out_b"]
            if io <= abuf:
                wt += l["w_bytes"]; continue
            nb = math.ceil(l["w_bytes"] / wbuf)
            ta = l["w_bytes"] + l["in_b"] * nb + l["out_b"]
            tiles = math.ceil(io / abuf)
            tb = l["w_bytes"] * tiles + l["in_b"] + l["out_b"]
            if ta <= tb:
                wt += l["w_bytes"]; at += l["in_b"] * nb + l["out_b"]
            else:
                wt += l["w_bytes"] * tiles; at += l["in_b"] + l["out_b"]
        return wt * overhead, at * overhead


# FPGA 持続MAC/sシナリオ: (名前, レーン, Hz, 稼働率, DDR帯域, 計算とメモリの重なり)
SCEN = [
    ("最良(理論DDR3帯域)", 96, 54e6, 0.60, DDR_THEORY_BW, "max"),
    ("目標(理論の60%)", 96, 54e6, 0.60, 0.6 * DDR_THEORY_BW, "max"),
    ("中間(理論の30%)", 96, 54e6, 0.30, 0.3 * DDR_THEORY_BW, "sum"),
    ("計算最良x BIST実測(上)", 96, 54e6, 0.60, DDR_BIST_BW_HIGH, "sum"),
    ("計算最良x BIST実測(下)", 96, 54e6, 0.60, DDR_BIST_BW_LOW, "sum"),
    ("BIST実測(上側解釈)", 48, 27e6, 0.30, DDR_BIST_BW_HIGH, "sum"),
    ("BIST実測(下側解釈)", 48, 27e6, 0.30, DDR_BIST_BW_LOW, "sum"),
]
# バッファ前提: (重みバッファB, 活性バッファB, トラフィック余剰係数) 良/悪
BUF_GOOD = (48 * 1024, 48 * 1024, 1.0)
BUF_BAD = (24 * 1024, 32 * 1024, 1.25)


def fpga_latency(net, scen, buf):
    _, lanes, clk, util, bw, ov = scen
    tc = net.macs / (lanes * clk * util)
    wt, at = net.ddr_traffic(*buf)
    tm = (wt + at) / bw
    comm = (net.in_bytes + net.out_bytes) / LINK_BW
    t = (max(tc, tm) if ov == "max" else tc + tm) + comm
    return dict(total_s=t, compute_s=tc, mem_s=tm, comm_s=comm, w_traffic=wt, a_traffic=at)


def p4_latency(net):
    """P4単体。戻り値 (最速秒, 最遅秒, 載るか, 必要メモリ低, 高)。"""
    lo, hi = net.peak_act()
    need_lo, need_hi = net.weight_bytes + lo, net.weight_bytes + hi
    if need_hi <= 0.75 * PSRAM_BYTES:
        fit = "載る"
    elif need_lo <= PSRAM_BYTES:
        fit = "ぎりぎり/不確実"
    else:
        fit = "載らない"
    # 重み4MiB以下(nのみ)はYOLOv8n実測(0.49〜1.2s@320)の範囲、それ以上は重み律速層が増えるため下限をPSRAM帯域律速とする
    slow = P4_OVERALL_LOW if net.weight_bytes <= 4 * 2**20 else P4_PSRAM_BOUND
    return net.macs / P4_OVERALL_HIGH, net.macs / slow, fit, need_lo, need_hi


def fmt_t(s):
    return f"{s*1e3:.0f}ms" if s < 1 else (f"{s:.1f}s" if s < 100 else f"{s/60:.1f}min")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--json"); a = ap.parse_args()
    out = []
    print("[見積もり] YOLOv8 n/s/m/l/x、INT8、BN融合後。層構成はultralytics yamlから再構成(計算値)")
    print(f"DDR3: 理論 {DDR_THEORY_BW/1e9:.3f}GB/s、BIST実測換算 {DDR_BIST_BW_LOW/1e6:.0f}〜{DDR_BIST_BW_HIGH/1e6:.0f}MB/s"
          f"(約{BIST_CYC_PER_BEAT}サイクル/ビート/相; 相の解釈は未確認)")
    print("\n== (1) モデル諸元 ==")
    print(f"{'':3}{'解像度':>6} | {'param(計算)':>11} {'公表':>6} | {'重みMiB':>7} | {'GMAC(計算)':>10} {'公表/2':>7} | {'活性低MiB':>9} {'活性高MiB':>9}")
    nets = {}
    for sc in SCALES:
        for res in (640, 320):
            net = Net(sc, res); nets[(sc, res)] = net
            lo, hi = net.peak_act()
            pp, pf = PUBLISHED[sc]
            print(f"{sc:3}{res:6d} | {net.params/1e6:10.2f}M {pp:5.1f}M | {net.weight_bytes/2**20:7.1f} | "
                  f"{net.macs/1e9:10.2f} {pf/2*(res/640)**2:7.2f} | {lo/2**20:9.2f} {hi/2**20:9.2f}")
            out.append(dict(model=sc, res=res, params=net.params, macs=net.macs, act_lo=lo, act_hi=hi))
    print("\n== (2) 1枚あたりレイテンシ(FPGA、通信20MB/s込み)とP4単体 ==")
    for (sc, res), net in nets.items():
        tmin, tmax, fit, nlo, nhi = p4_latency(net)
        print(f"\nYOLOv8{sc} {res}x{res}: {net.macs/1e9:.2f}GMAC, 重み{net.weight_bytes/2**20:.1f}MiB, "
              f"P4必要メモリ {nlo/2**20:.1f}〜{nhi/2**20:.1f}MiB/32MiB -> {fit}; DDR3 128MiBには"
              f"{'載る' if nhi <= DDR3_BYTES else '載らない'}")
        print(f"   P4単体の推定: {fmt_t(tmin)}〜{fmt_t(tmax)}" + ("  (参考。実際は動かない)" if fit == "載らない" else ""))
        for s in SCEN:
            g = fpga_latency(net, s, BUF_GOOD); b = fpga_latency(net, s, BUF_BAD)
            print(f"   FPGA {s[0]:18s}: {fmt_t(g['total_s'])}〜{fmt_t(b['total_s'])} "
                  f"(compute {fmt_t(g['compute_s'])}, DDR3転送 {(g['w_traffic']+g['a_traffic'])/1e6:.0f}〜"
                  f"{(b['w_traffic']+b['a_traffic'])/1e6:.0f}MB, 通信 {fmt_t(g['comm_s'])})")
            out.append(dict(model=sc, res=res, scen=s[0], t_good=g["total_s"], t_bad=b["total_s"]))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
