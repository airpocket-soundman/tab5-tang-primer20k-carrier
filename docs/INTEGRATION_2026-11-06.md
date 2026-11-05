# FPGA/ホスト開発統合記録（2026-11-06）

## 方針と統合対象

本repoは基板・ピン/電気条件・wire protocol・全FPGA/bitstream・共通codec・RTL検証を管理し、各OSのDMA/アプリは各hostに置く。GFX/MEM/NPUは用途別を維持し、資源・性能を測らない同時搭載を行わない。

carrier `2f54ae3`（GPU全8/216MHz要求捕捉/FIFO/登録返信/7375保存点）、MEM記録 `a0752b2`、重複済みGPU準備 `e0a81a7` を履歴を保ってmainへ統合する。変更がmainに完全に含まれるGPU/MEM関連codex開発branchだけを整理。未マージの位相/演算候補、PCB等の別作業は保持する。棚卸しとtipは [branch-inventory.json](integration-2026-11-06/branch-inventory.json) に保存。

元primary mainには未コミット・未追跡の基板等の変更があるため、pullの衝突で停止した。そのtreeをreset/stash/cleanせず、独立統合treeでmainを更新する。元treeのHEAD/未保存変更が自動的にmain最新へ移動したと誤解しない。

## 現在の基準と未検証範囲

- 検証済みGPU：7375、FS SHA4aaac60cf35ec9effa1eb48aec657c8d29c9ea18655eca7c0d20a0667af8427b、host ELFdb939ca49a08684dc8569dc1d8edc5e9e44920cfeaf35f70879d30462300ab90、TX40POS/RX16NEG。詳細は [通信高速化引継ぎ](引継ぎ_通信高速化_2026-11-06.md) を正とする。
- 全8シーンを含む33画像一致、最大batch1000回、再起動profile、LIVE切替が記録済み。RX20/長時間soak/全24条件120frameは未完。SDK40MHz設定の合格を全エッジ波形/analog余裕/配線限界と混同しない。hostの後続SLogic復旧報告も基本周期観測とエッジ不足を区別する。
- 新しい2D/Fire等はALL_SCENES_ENABLEを明示したGFX候補だけで有効。既存opcode/CRC/方向転換/ピン/電源は維持、新機能は能力問合せ後に使う。既存bitstreamに能力を読み替えない。
- 旧MEM DMA最適化・累積表・復元一式は統合して保存。[11月5日PC移動資料](引継ぎ_2026-11-05_第3版_PC移動.md) は当時の保存点として維持する。MEMの8/8や旧D7F5 RX20をGPU7375の合格点にしない。
- DDR独立burst帯域は約1.48GB/sの別試験。GFX DDR統合、NPUモデル実行、SDローダー/カメラ/進捗表示の完了を意味しない。
- host非同期キューは既存TRI_BATCHをまとめる診断候補。通常描画・全host共通driverへの統合は未完。wire ABIの汎用バッチ変更は今回行わない。

## 全host照合

|host|読取り版・内容|本統合の適合範囲/未実装|
|---|---|---|
|ESP-IDF|GPU ca5d853＋MEM RX20候補87ff0fa、README/Project_B/通信・表示/検証|7375/ELF指定のESP-IDF実機結果のみ。統合後はPC/SDK検証、追加実機試験なし|
|Linux|f1deceb、README/DEVELOPMENT_GOALS/DT tab5-fpga-dock/通信tab5_parallel_linux.c|GPIO cdev v2の低速Dock opt-in、起動無出力。新ALL_SCENES/40MHz DMAの実機適合は未実装/未検証|
|MeOS|78274b4、README/FPGA_CARRIER_REQUIREMENTS/parlio_native_rx.inc|既存能力/所有制御を維持。新ALL_SCENES/7375の実機適合は未検証、高速設定を自動適用しない|
|Linux memory研究|e84b59e、README/Project_A計画|明示外部メモリ/演算研究。透過Linux main RAM増設ではない|

Linux/MeOSは新GFX機能へ自動追従させず、採用時に能力・codec版・bitstream・clock・OS実装を照合する。新opcode/電源/pinを本統合で追加確定しない。既存実験仕様・OS差・未検証を残してmainへ一元化する。

## 統合検証

今回実機のflash/ARM/再測定をしない。FIFO 40MHz相当のデジタル位相試験と全8pin-level RTL/CRC/feature-off回帰、host PCテスト/SDK buildで統合の整合性を確認する。vendor DFFCを使う全8試験にはGW2A primitive libraryが必要。最初のlibrary未指定時はDFFC未定義でelaboration失敗したため、primitive指定で再実行した結果を正とする。詳細結果/原logは integration-2026-11-06 に保存。

## 続ける順序

1. main保存点の復元確認、長時間GPU/最大batch混在soakと全24条件120frame。
2. RX20のbit別遅延・sampling窓・CLK/DATA相対時刻・SLogic完全取得条件の切分け。
3. host非同期要求キューの通常描画統合とCPU実時間/全体時間比較。FPGA汎用バッチABIは全host要求レビュー後。
4. DDR活用GFX/NPUの容量/operator監査、SD重みロード、画像入力、結果座標返送、Tab5 BB表示/進捗。未実装を明示。


## 基板作業の除外

ユーザー指示により基板/回路/PCBデータと関連branchの整理は別セッションに委ねる。本セッションではkicad/spark/PCB/schematicデータを変更せず、元primaryのdirty差分にも触れない。整理対象は統合済みGPU/MEM関連codex branchに限定し、PCB/電源/基板関連branchを保持する。


## 実機接続の読み取り確認

統合作業中に対象Tab5（COM4/30:ED:A0:E2:FE:C0）、FTDI機器、SLogic16U3（202512191855）を列挙。host info/statusだけを読み、ELFf073cfba…、CPU/LIVE、DISARM、TX40/RX16設定、last_step_error=noneを確認。保存資料の旧LIVE最終状態を現在状態へ転用しない。FPGA USERCodeの再読やflash/reset/ARMはこの段階で実施していない。


## ブランチ整理の完了

2026-11-06、mainへの包含と各tip一致を確認してGPU/MEM関連の完了済みリモートbranch21本を削除。記録は branch-cleanup-result.json。基板/電源/PCB/claude等の別作業branchと未マージ候補を保持し、ローカルworktreeは削除していない。host側もmain包含確認後18本を整理。今後はmainを基点に必要な実験branchだけを作り、実績と候補を区別して統合する。
