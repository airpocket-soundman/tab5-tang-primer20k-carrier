#!/usr/bin/env python3
"""NPU(INT8推論)の理論スループット見積もり。すべて「見積もり」であり実測ではない。

実機・FPGAツールには触れない純粋な算術。前提値は下のDEFAULTSまたはCLI引数で変更できる。
使い方:  python fpga/npu/estimate_throughput.py [--json out.json]
"""
import argparse, json, sys
sys.stdout.reconfigure(encoding="utf-8")

MODEL_MAC = 61_063_640          # WholeBody25 N 128x160 (引継ぎ資料7章)
IN_BYTES = 61_440               # 128*160*3
OUT_BYTES = 1 * 29 * 420        # 12,180 (INT8出力と仮定)
WEIGHT_BYTES = 600_000          # 約0.6MB (INT8)
BSRAM_BYTES = 46 * 18 * 1024 // 8   # 46 BSRAM x 18Kbit = 105,984 B (約103.5KiB)
DSP_MULT9 = 96                  # GW2A-18: 18x18が48個、9x9なら最大96 (未検証)

# P4側の持続MAC/s (esp-dl issue #339 の実測ベース。出典はdocに記載)
P4_PEAK_MACS = 4.446e9          # 360MHz, 3x3 conv最良ケース実測
P4_THEORY_MACS = 360e6 * 16     # 仮定: 128bit PIE = INT8 16MAC/cycle (一次資料で未確認, 推論)
P4_OVERALL_LOW = 0.67e9         # YOLOv8n 320: 約815MMAC/1211ms (報告者の表の合計からの概算)
P4_OVERALL_HIGH = 1.66e9        # 同 492ms (3.3.14+tiling提案)

def fpga_time(lanes, clk_hz, util, ddr_bw, traffic_bytes):
    """compute律速とメモリ律速の大きい方。戻り値 (秒, compute秒, mem秒)"""
    tc = MODEL_MAC / (lanes * clk_hz * util)
    tm = traffic_bytes / ddr_bw if ddr_bw else 0.0
    return max(tc, tm), tc, tm


# ---- 上位FPGA比較 (公開仕様。DSPの9x9分割・クロック・DDR3帯域は仮定) ----
# (名前, LUT4, 18x18乗算器数, BSRAM[Kbit], DDR3搭載)
BOARDS = [
    ("Tang Primer 20K (GW2A-18)", 20736, 48, 828, "あり(128MB, 現状未動作)"),
    ("Tang Primer 25K (GW5A-25)", 23040, 28, 1008, "なし(SDRAMアドオンのみ)"),
    ("Tang Mega 60K (GW5AT-60)", 59904, None, None, "未確認"),
    ("Tang Mega 138K Pro (GW5AST-138)", 138240, 298, 6120, "1GB(512MBx2, 1333Mbps/pin)"),
]

def board_table(p4_target_ms=(36.8, 91.1), link_mbs=10.0):
    print("\n== 上位FPGA比較 (見積もり。9x9分割で乗算器数x2と仮定) ==")
    comm = (IN_BYTES + OUT_BYTES) / (link_mbs * 1e6)
    for name, lut, mul, bram, ddr in BOARDS:
        if mul is None:
            print(f"{name}: LUT {lut}, 乗算器/BSRAM/DDR3は未確認のため計算せず"); continue
        lanes = mul * 2
        w_fit = "重み0.6MBがBSRAMに収まる" if bram * 1024 / 8 >= WEIGHT_BYTES else "重みはBSRAMに入らない"
        print(f"{name}: LUT {lut}, BSRAM {bram/8:.0f}KB({w_fit}), DDR3 {ddr}")
        for clk in (54e6, 100e6, 150e6):
            for util in (0.3, 0.6):
                tc = MODEL_MAC / (lanes * clk * util)
                print(f"    {lanes:4d}レーン {clk/1e6:4.0f}MHz 稼働{util:.1f}: {lanes*clk*util/1e9:5.1f} GMAC/s, "
                      f"compute {tc*1e3:6.1f} ms, 通信{link_mbs:.0f}MB/s込み {(tc+comm)*1e3:6.1f} ms")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--act-traffic-mb", type=float, default=20.0,
                    help="特徴マップのDDR3往復量[MB]。未算出の仮定値(層ごとの形状から要計算)")
    a = ap.parse_args()
    traffic = WEIGHT_BYTES + a.act_traffic_mb * 1e6
    rows = []
    print(f"[見積もり] モデル {MODEL_MAC/1e6:.1f} MMAC, 重み {WEIGHT_BYTES/1e3:.0f}KB, "
          f"BSRAM合計 {BSRAM_BYTES/1e3:.1f}KB, 特徴マップ往復 {a.act_traffic_mb} MB(仮定)")
    print("\n== P4側 (推論時間 ms) ==")
    for name, r in [("理論16MAC/cyc@360M(推論)", P4_THEORY_MACS), ("最良実測", P4_PEAK_MACS),
                    ("全体実効(高)", P4_OVERALL_HIGH), ("全体実効(低)", P4_OVERALL_LOW)]:
        print(f"  {name:28s} {r/1e9:5.2f} GMAC/s -> {MODEL_MAC/r*1e3:7.1f} ms")
    print("\n== FPGA側 (ms)  compute/memory の大きい方 ==")
    print(f"{'lanes':>5} {'MHz':>4} {'util':>4} {'DDR GB/s':>8} | {'GMAC/s':>6} {'compute':>8} {'mem':>7} {'total':>7}")
    for lanes in (16, 32, 64, 96):
        for clk in (27e6, 54e6):
            for util in (0.3, 0.6):
                for bw in (0.0, 0.8e9):   # 0=メモリ無視(BSRAM内完結の理想), 0.8GB/s=DDR3実効の仮定
                    t, tc, tm = fpga_time(lanes, clk, util, bw, traffic)
                    rows.append(dict(lanes=lanes, clk_mhz=clk/1e6, util=util, ddr_gbs=bw/1e9,
                                     gmacs=lanes*clk*util/1e9, compute_ms=tc*1e3, mem_ms=tm*1e3, total_ms=t*1e3))
                    print(f"{lanes:5d} {clk/1e6:4.0f} {util:4.1f} {bw/1e9:8.1f} | {lanes*clk*util/1e9:6.2f} "
                          f"{tc*1e3:8.1f} {tm*1e3:7.1f} {t*1e3:7.1f}")
    print("\n== 通信込み損益分岐 (FPGA total + 通信 <= P4時間) ==")
    io = IN_BYTES + OUT_BYTES
    for link in (5e6, 10e6, 20e6):
        tcomm = io / link
        print(f" 実効リンク {link/1e6:4.0f} MB/s: 入出力 {io} B -> {tcomm*1e3:5.2f} ms")
        for p4name, p4 in [("P4最良実測", P4_PEAK_MACS), ("P4全体実効(高)", P4_OVERALL_HIGH), ("P4全体実効(低)", P4_OVERALL_LOW)]:
            tp4 = MODEL_MAC / p4
            budget = tp4 - tcomm
            if budget <= 0:
                print(f"   vs {p4name}: 通信だけでP4時間を超える"); continue
            need = MODEL_MAC / budget   # 必要な実効MAC/s
            for clk in (27e6, 54e6):
                print(f"   vs {p4name} ({tp4*1e3:.0f}ms): 必要 {need/1e9:.2f} GMAC/s = {need/clk:.0f} 有効レーン@{clk/1e6:.0f}MHz")
    print("\n注: DSP上限は96レーン(9x9, 未検証)。有効レーン=レーン数x稼働率。"
          "\n    LUT: int8_requantize約2361セルはレーン複製不可(共有/時分割が必要)。全て見積もり。")
    board_table()
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)

if __name__ == "__main__":
    main()
