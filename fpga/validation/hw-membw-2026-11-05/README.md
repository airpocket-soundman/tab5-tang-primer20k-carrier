# DDR3 帯域の実機測定（2026-11-05）

イメージ `sampleip_map_t4_bw2`（`claude/membw-sta`、USERCODE 0xAF、旧IP＋自前ロジック、USER 99.5625MHz、STAは診断用SDC下で違反0）。ホスト：MEM probeファーム `claude/mem-bw-host` 378f68f（`mem-bw-host-2`、ELF SHA-256 `45ac516b…`）。GPIOリンク（500kHz以下）で設定・結果取得。測定はFPGA内部（DDR3のネイティブIFのサイクル数）で、ホストリンクの帯域を含まない。範囲：1MiB（`--mib 1`）、測定後にBIST再合格（`--bist-after`）。

| パターン | 帯域（MB/s） | 効率（理論1593MB/s比） | 平均遅延（ns） | コマンドstall比 |
|---|---:|---:|---:|---:|
| write_seq | 511.6 | 0.321 | ― | 0.679 |
| read_seq | 513.6 | 0.322 | 337.0 | 0.677 |
| mixed_seq_4_4 | 406.4 | 0.255 | 375.6 | 0.490 |
| write_rowmiss16k | 141.8 | 0.089 | ― | 0.911 |
| read_rowmiss16k | 194.9 | 0.122 | 537.6 | 0.877 |
| write_page_runs | 511.7 | 0.321 | ― | 0.679 |
| read_page_runs | 513.4 | 0.322 | 337.3 | 0.677 |
| write_bank_rot | 149.8 | 0.094 | ― | 0.906 |
| read_bank_rot | 200.4 | 0.126 | 527.7 | 0.874 |
| write_scatter | 149.8 | 0.094 | ― | 0.906 |
| read_scatter | 200.4 | 0.126 | 526.6 | 0.874 |

- 旧BISTの約31サイクル／ビート／相（約51MB/s相当）より、シーケンシャルで約10倍。バーストなし（`--burst` 未使用）の値。バースト（`app_burst_number`）の効果は未測定（意味は未確認）。
- 限界：1MiBのみ、1回ずつ。冷起動の繰返し、温度、長時間、全域は未実施。タイミングは診断用SDC下の結果で余裕は薄い（+0.079ns）。旧IPの再配布条件は未確認。
