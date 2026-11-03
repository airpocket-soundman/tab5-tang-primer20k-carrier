# MEM BISTのペア書込み候補と試験計画

2026-11-04。ブランチ `claude/track-d-ddr3`（基点 `main 03eb39a`）。オフライン作業のみ。実機・書込み器・UARTは操作していない。DDR3の物理動作は未検証で、これは透過的なLinux主記憶ではなく、FPGAが明示的に読み書きする領域に関する資料である。

## 1. 現在の停止点（保存された実機記録から）

出典は `fpga/validation/mem-checkpoint-2026-11-04.json` と、各 `*-first64-2026-11-04` の生記録。

- 全てのハードウェアMEM試験は**失敗**。物理メモリのPASSも容量の証明もない。
- アイドル時は `init_calib_complete`（calibrated）=1、`cmd_ready`=1、`wr_data_rdy`=1（native flags 0x060A）。校正完了とコマンド受付可能までは進む。
- 64ビート（1024B）のBISTを起動すると、書込み段階で `no progress`（error 3）になり、8,100,008 USERサイクルでタイムアウトする。`verified_beats`=0、読出しは0回。
- 停止時の状態（診断・deep・ready-strobe系イメージ）: 受理されたコマンド7、受理された書込みデータ8、`command_ready`=0（`command_valid`は、readyでストローブを制限する前のイメージでは1、制限後は0）。つまり**最後のデータだけがコマンドより先に受理され**、そのコマンドが受理されないまま止まる。最初の凍結イメージでは14コマンド／15データで同じ形。
- コントローラ内部の観測（deep words）: コマンドFIFOが満杯（full）、コマンド読出しポインタの進行数=0、書込みデータ読出しポインタの進行数=0、`send_wr`がHighだったサイクル数=0。**DRAMへ書込みが一度も発行されていない**。
- 024f（スケジューラ観測）イメージは、オフラインで適格化済みだが、実機では未実行（`init_done`、`pre_info_valid`、リフレッシュ、self-refresh、バンク状態などを見る目的）。**根本原因は未特定**。

## 2. 公式ガイドとサンプルとの差分（今回の発見）

IPUG281-2.6E の 4.4.6（Figure 4-10）は、書込みデータをコマンドと同じサイクル、その1サイクル前、または1サイクル後に置くと規定する。PDFのラベル座標（サイクル番号の位置とCMD/DATAの位置）から読み取った結果であり、図そのものの目視確認は未実施。

| 項目 | Sipeed公式DDR-test（同じCoreで動作する参照） | 本リポジトリのBIST（変更前） |
|---|---|---|
| 書込みの出し方 | `cmd_rdy && data_rdy` の**両方**が立つ時だけ、コマンドとデータを**同じサイクル**で出す | コマンドとデータを**独立**に出す。両readyが別々に変わると、データがコマンドから2サイクル以上離れる |
| 校正後の待ち | `init_calib_complete` 後に256サイクル待つ | 待ちなし |
| 保留 | 1件ずつ | 1件ずつ（同じ） |
| `ddr_cs` | 0に固定、IPの`O_ddr_cs_n`は未接続 | IPの`O_ddr_cs_n`をピンへ直結 |
| メモリクロック | 400 MHz（ユーザークロック100 MHz） | 324 MHz（81 MHz） |
| tREFI／tRFC | 7.8 µs／160 ns（tRFC 160 nsは2Gbit部品の値と推定） | 3.5 µs／260 ns（より頻繁・保守的） |
| IPバージョン | v3.0（`app_burst_number`あり） | v5.9（`burst`のみ） |

ピン割り当てを機械的に突き合わせた結果、本リポジトリの`mem_bist.cst`のDDR 44本は、公式サンプルの`ddr3.cst`と位置・IO規格・駆動の全属性が一致した（`ddr_addr[13]`のみ設計上除外）。制約は原因ではない。

停止の形（データだけが1個先に受理される）は、ペア発行の違反と整合する。ただし、**最初の書込みすらDRAMに発行されていない**事実は、この違反だけでは説明できない。したがって、本候補の効果は未確認で、根本原因の特定は024fの観測を待つ。

## 3. 今回の変更（`1c9a31c`）

`fpga/mem/rtl/mem_bist.v`:

- `PAIRED_WRITE`（既定1）: 書込みのコマンドとデータを、両readyが立つサイクルにだけ同時発行する。0なら従来の独立発行に戻る（比較用）。
- `CALIBRATION_SETTLE_CYCLES`（既定256）: 校正完了後、この数のUSERサイクルが経過するまで何も発行しない。
- 診断ビット列（debug bundle）と、ホストのABI（コマンド、スナップショット、selector）は不変。ホストの変更は不要。

`fpga/mem/tests/tb_mem_bist.v` と `run_tests.py`:

- ベンチを`PAIRED`でパラメータ化し、従来版（21シナリオ）とペア版（21シナリオ）の両方を実行する。
- ペア版では「書込みコマンドとデータが必ず同じサイクルか」「校正安定前に発行しないか」を毎サイクル検査する。コマンドだけ、データだけがreadyの停止シナリオでは、何も発行されないことを確認する。

## 4. 検証結果（オフライン）

`python fpga/mem/tests/run_tests.py --iverilog … --vvp … --zig … --primitive-lib …` の結果は全て合格。

- deep monitor、mem_bist 21（従来）、mem_bist paired 21、mem_mailbox 122、mem_link 7、mem_heartbeat_abort 39、mem_protocol 622、ベンダー初期化モデル。
- 公式Education 1.9.11.03による合成・配置配線・STA: setup +0.106 ns、hold +0.234 ns、recovery +1.364 ns、removal +0.580 ns、TNSは全て0。論理6534/20736、レジスタ6477/16173。
- **USERクロック（81 MHz）のFmaxは81.700 MHzで、余裕は約0.9%と薄い**。設定上は合格だが、再ビルドで変動しうる。
- イメージ: `fpga/validation/mem-paired-write-2026-11-04/mem_bist.fs.gz`（展開後SHA256 `be42c604aeb3217cbcf7743f46c49a585dbfe414b1900bace6bf703f197ebeea`、UserCode `0x0000B317`）。記録は `fpga/validation/mem-paired-write-prehardware-2026-11-04.json`。
- 実行できなかったもの: `record_build.py --guarded` と `run_ready_equivalence.py`。後者は旧版（`08ef3a4`）との挙動一致を証明するもので、今回は意図的に挙動を変えたため成立しない。ready-strobe候補の履歴としてのみ残す。

未検証: Gowin EDAでの外部I/Oを含む完全なタイミング、DRAMの実際の応答、校正の成否、物理容量、ペア発行による停止の解消。

## 5. オフラインでは解消できない点と必要な手順

| 項目 | 根拠 | 必要なもの |
|---|---|---|
| 停止の根本原因 | 最初の書込みがDRAMへ発行されない理由は、024fの観測（`init_done`、`pre_info_valid`、リフレッシュ、バンク状態）なしには区別できない | 本イメージで024fを実機から読む（下記の段階1） |
| メモリクロックの影響 | 公式サンプルは400 MHz、こちらは324 MHz。IPの設定とPLLの両方を変えるため、別イメージが必要 | 400 MHzのIP設定とPLL（27 MHzからの分周比）を決めて再生成。ライセンス上はEducationで可能だが、実機で試すまで効果は不明 |
| `ddr_cs`の扱い | サンプルは0固定、こちらはIP出力を直結 | 段階2の切り分け候補（1イメージ分の変更） |
| 物理個体 | 資料上の型番（H5TQ1G63EFR）と容量は未確認 | 実機の刻印の確認、容量は別名（alias）試験で確定 |

## 6. 試験計画と合格基準

実機の操作は、親セッション（書込み・UART・ジャンパの担当）が行う。いずれも1回の試行で止まり、自動の再試行やフォールバックはしない。

### 段階0: 準備（実機に触れない）
1. `fpga/validation/mem-paired-write-2026-11-04/mem_bist.fs.gz` を展開し、SHA256が `be42c604…` と一致することを確認する。
2. 古いdeep系ホスト（`ec93b6e`、capability 014f）は024fを**拒否する**。ホストのmain（`6ad1ed6`以降、スケジューラ診断を含む）から `tab5-fpga-gpu/tools/build_mem_probe.ps1` で、新しいビルド名のMEM probeファームを作る（ABIは変更なし）。ホストmain `6ad1ed6` から `build_mem_probe.ps1 -BuildName mem-probe-trackd-6ad1ed6` でオフラインのビルドは成功した（`tab5_gpu_lab.bin` SHA256 `7d417e35…`、ELF SHA256 `f7c84fe7…`、場所 `D:\GitHub	ab5-fpga-gpuuild\mem-probe-trackd-6ad1ed6`）。書込み・実機確認は未実施で、`--expected-elf-sha` にはELFのSHA256を指定する。

### 段階1: 読取り専用の観測（最優先）
- SRAMのみに書込み（SPI flashには書かない）。書込み後にUserCode `0x0000B317` を確認する。
- ホストで読取り専用のスナップショットを取る: `python tools/probe_mem_scheduler_diag.py --execute --port COM4 --record <出力>`（BISTは起動しない）。
- 合格基準: capability `024f` が返る。アイドル時の native flags が、`calibrated`=1 と `cmd_ready`=1、`wr_data_rdy`=1 を示す。`init_done`、`pre_info_valid`、リフレッシュ要求、バンク状態の値を記録する。これは根拠データであり、合否ではない。

### 段階2: 最小の書込み／読出し（64ビート、1024B）
- `python tools/probe_mem_bist.py --execute --port COM4 --base 0 --count 64 --output <出力>`（破壊的、範囲はベース0から1024B）。
- 合格基準: error 0、`verified_beats`=64、`mismatching_beats`=0、`first_bad_byte`なし。受理コマンド数=受理書込みデータ数（ペア発行のため一致する）。
- 失敗した場合: 受理されたコマンド数／データ数、コマンドFIFOのポインタ進行数、`send_wr`のサイクル数を記録して停止する。再試行しない。段階1のデータと合わせて原因を判断する。

### 段階3: パターンと境界（段階2が合格した場合のみ）
- パターン: 00／FF／AA／55、歩行1／0、バイトマスク（BISTは補数＋マスクの2段階を内蔵）。
- アドレス境界: カラム境界（`base=0x1ff0, count=33`）、バンク境界、行境界（`base=0x3ff0`）、最終ビート（`base=0x7fffff0`, `count=1`）を、シミュレーションと同じ値で試す。
- 合格基準: 全てerror 0。

### 段階4: 容量判定（alias）
- アドレス0と、上位ビット（例 `0x4000000` 付近）に別々のパターンを書き、相互に壊れないことを確認する。確定した容量だけを公開範囲にする。先に全域を書かない。
- 合格基準: 128 MiB分のアドレスが別々に保持される。1 Gbit（128 MiB）か2 Gbitかを実測で記録する。

### 段階5: 連続転送
- 大きな`count`（8,388,608ビート＝全域）を、サイズを段階的に上げて試す（1 KiB → 1 MiB → 128 MiB）。各段階で完了時刻と`user_cycles`を保存し、帯域を記録する（DDR内部の測定であり、ホストリンク込みの値ではない）。
- 合格基準: 全てerror 0。最初の不一致のアドレス・期待値・実測値を保存。

### 段階6: 長時間（soak）
- 128 MiB全域のfill／check を、冷起動を複数回挟んで、30分、次に2時間。誤りは0。電源・温度条件を記録する。
- 校正PASS1回を、全域合格とは扱わない。

### 失敗した場合の分岐
- 段階1で`init_done`が立たない、または`pre_info_valid`が立たない: 校正後のIP状態の問題。400 MHz設定、`ddr_cs`の0固定を別イメージで試す。
- 段階2でも`send_wr`が0のまま: DRAM自体が応答していない可能性。物理個体（刻印・電源・VREF／VTT）の確認が先。

## 7. 参照
- `fpga/validation/mem-checkpoint-2026-11-04.json`、`mem-native-diag-first64-2026-11-04/`、`mem-deep-first64-2026-11-04/`、`mem-ready-first64-2026-11-04/`
- [DDR3準備調査](DDR3準備調査_2026-11-04.md)、[MEM_BIST構成案](MEM_BIST構成案.md)、[MEM_SCHEDULER診断](MEM_SCHEDULER診断.md)
- IPUG281-2.6E 4.4.5〜4.4.7、Sipeed `TangPrimer-20K-example` DDR-test（`tester.v`）
