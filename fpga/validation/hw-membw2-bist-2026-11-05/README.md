# `sampleip_map_t4_bw2`（BW_ENABLE=1、帯域測定エンジン入り）の旧BIST実機結果（2026-11-05）

イメージ：`claude/membw-sta` bcd635e、FS本体SHA-256 `7ea8f78c…`、USERCODE 0xAF（STAは診断用SDC下で違反0、最悪setup +0.079ns）。ホスト：MEM probeファーム（ELF `8ae2d3ff…`）。SRAMのみに書込み。

| 段階 | 結果 |
|---|---|
| patterns（10本） | 全合格 |
| boundaries（6本） | 全合格 |
| scale（64ビート〜128MiB全域、4本） | 全合格 |

意味：帯域測定エンジンと共有enable段を追加しても、旧BIST経由のDDR3の動作は変わらない（BW=1イメージでBISTが従来どおり通る）。**帯域の測定自体は未実施**（ホストの `bw` アクションが未実装、`claude/mem-bw-host` で作成中）。診断用SDC下の結果で、余裕は薄い。
