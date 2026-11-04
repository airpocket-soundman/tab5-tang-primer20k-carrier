# sampleip_map の実機結果（段階1と段階3：パターン・境界・規模）（2026-11-04）

実施：メインセッション。イメージ `sampleip_map`（自前ロジック＋**サンプルの旧IP 400MHz**、FS `626ada6e559b…`、USERCODE 0x4C2B、書込み後 Status 0x6020）。ホストMEM probeファームは `claude/track-p-ddr3-clk400-host`（`mem-probe-clk400-host`、ELF SHA-256 `1839488d…`）、ランナーはホスト `395d269`。元ファイルは `D:\esp\ddr3\stage3\`。

**これは「この個体、この1つの構成で、各ジョブが1回ずつ合格した」記録で、確定的な合格・長期安定・電気的な余裕の証明ではない。**

## 結果（各ジョブの最終スナップショット。ランナーのJSONの先頭snapshotは書込み相の途中値）
| 段階 | ジョブ | 結果 |
|---|---|---|
| 段階1 | 読取り専用 | calibrated 真、snapshot_fresh 真 |
| patterns（10） | seed 0／FFFFFFFF／AAAAAAAA／55555555／1・2・0x80・0x8000・0x10000・0x80000000、各 base 0・64ビート | 10/10 PASS（各 verified_beats 128、不一致0、user_cycles 約4000） |
| boundaries（6） | col→bank（base 0x7f0）、bank→row（0x3ff0）、row bit（0x1fff0・0x3fff0）、64MiB手前（0x3fffff0）、最終ビート（0x7fffff0、1ビート） | 6/6 PASS（不一致0） |
| scale（4） | 64ビート（1KiB）／65,536ビート（1MiB）／1,048,576ビート（16MiB）／**8,388,608ビート（128MiB全域）**、seed 0x12345678 | 4/4 PASS |

128MiB全域：error 0、phase 5、verified_beats 16,777,216（＝2相×8,388,608）、mismatching_beats 0、user_cycles 524,489,946、device_ms 5267.9（USER 99.5625MHz）。16MiB：658.5ms、1MiB：41.2ms。

## 注意
- BISTの読み書きは約31サイクル／ビート／相（524,489,946 ÷ 16,777,216）。これは**帯域測定ではない**（コマンドとデータを1件ずつ処理し、バーストや連続発行を使わない）。
- STAは setup 違反が残る（最悪 −0.526ns）。結果はタイミング適合の証明にならない。
- 全域の1回合格は、アドレス別名がないことの1回分の確認（データがアドレス依存）。物理容量は、サンプルが `DDR Size: 1G` と報告した。
- 未試験：複数seedでの全域、長時間soak、冷起動の再現、温度、電源余裕、実帯域、リフレッシュを跨ぐ長時間。次の手順は `docs/DDR3_冷起動_複数seed_soak手順_2026-11-04.md`。
