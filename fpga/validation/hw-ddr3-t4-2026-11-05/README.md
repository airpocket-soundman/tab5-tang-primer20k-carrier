# DDR3 `sampleip_map_t4` の実機結果（2026-11-05）

実施：このPC（引継ぎ後のメインセッション）。イメージ `sampleip_map_t4`（FS `39ff4409…`、USERCODE 0x0233、PIPELINE=4、旧IP＋自前ロジック、STA違反0。ただし診断用の非同期SDC下の結果で、最悪setup +0.024ns）をSRAMのみに書込み（USERCODE・Status 0x6020を確認）。ホスト：MEM probeファーム（ホスト `claude/track-p-ddr3-clk400-host` 79a28e7 から再ビルド、ELF SHA-256 `8ae2d3ff…`、申告 `app_elf_sha256` 一致）。

| 段階 | 内容 | 結果 |
|---|---|---|
| 段階1（読取り専用） | 校正・ready・sys_flags | 校正済み、command_ready・data_ready 真、sys_flags 905 |
| patterns | seed 0／FFFFFFFF／AAAAAAAA／55555555／歩行1×6、各1KB | 10／10 合格 |
| boundaries | 列→バンク、バンク→行、行ビット4／11、半分、最終ビート | 6／6 合格 |
| scale | 64ビート、64Ki、1Mi、8Mi（128MiB全域） | 4／4 合格 |
| fullseeds | 128MiB全域 × 8 seed | 8／8 合格 |
| soak（10分） | 繰返し（1／26／51／76番目などを保存） | 96ジョブ 全合格 |

限界：電源投入後1回目の校正に対する試験で、**冷起動の繰返し、温度、電源条件は未実施**。BISTは帯域測定ではない（約31サイクル／ビート／相）。物理容量（1Gbit）とサンプルの「ビット26での容量判定」との整合は未解決。校正が通ったIPは旧IP（Gowin製の暗号化生成物、再配布条件は未確認）。
