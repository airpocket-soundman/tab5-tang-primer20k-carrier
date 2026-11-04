# 再生成IP（新ツール）400MHz系5イメージの段階1結果（2026-11-05）

実施：このPC。各イメージをSRAMのみに書込み（USERCODE確認）、MEM probeファーム（ELF `8ae2d3ff…`）で `probe_mem_scheduler_diag.py` を実行。

| イメージ | FS（先頭） | USERCODE | IP設定（400MHz、1:4） | 結果 |
|---|---|---|---|---|
| clk400_notap（対照） | `ad174e10` | 0x8D47 | 既定（CODESCAL "111"、DQ IODELAY 5） | 校正未完了（sys_flags 2136、snapshot_fresh 偽） |
| clk400dp | `4a1823c2` | 0x4783 | Debug Parameter：CODESCAL "101"、DQ IODELAY 6 | 同じ |
| clk400x_dp000 | `80dddcb9` | 0x9DDB | CODESCAL "101"、IODELAY 0 | 同じ |
| clk400x_dp1116 | `63d4db3c` | 0xC783 | CODESCAL "111"、IODELAY 6 | 同じ |
| clk400x_drvhigh | `637a6a16` | 0xA6D4 | OUTPUT DRV HIGH | 同じ |

- 5つとも `calibrated` が真にならない（対照と同一の `sys_flags` 2136）。**Debug Parameter（DLL CODESCAL・DQ IODELAY）の一致と出力強度では、400MHzの校正は通らなかった。**
- 残る差は、コマンド／アドレス／制御／CK用のIODELAY（24個×40段）と `SCAL_EN`＝true（新ツールのIPが生成しない）の可能性が高い（仮説）。
- 方針（`docs/DDR3_方針決定_旧IPを採用_2026-11-05.md`）：追加のバリエーションを数個試し、通らなければペンディング。追加候補（324MHz＋2T、出力強度、300／360MHz）は `claude/newip-more-variants` で用意中。
