# FPGA・通信・DDRトライの保存点（2026-11-04）

ユーザー指示による記録・コミット・プッシュの保存点。最後の25MHz試験を終了し、新しい実機試験は開始していない。Tab5はソフトウェアARM解除・描画停止・通信idle。最終アプリやDDR完成を意味しない。

## 実機系列とオフライン候補

| 系列 | ブランチ / ソース | FS先頭 / UserCode | 結果・範囲 |
|---|---|---|---|
| 旧27MHz prefetch | codex/gfx-prefetch | 7405b4bd / 364C | 旧連続RX1/2/5MHzの比較元 |
| raw返信54MHz | codex/gfx-fastreply / 9c314f3 | 5b93ac88 / 9B72 | 有限RX20MHz合格、25/26.7MHz失敗。後の系列と分離 |
| 三角形バッチ | codex/gfx-triangle-batch / 9dee0af | 80c6e57a / 8E22 | 最大64三角形、atomic CRC、CPU画素比較 |
| TX capture付きGFX | codex/gfx-tx-capture / 0aeb406 | 94458f3b / 9320 | ホスト9029の連続RX20MHz、27比較・1000タイル・停止復旧に合格 |
| CLK入力hysteresis | codex/clock-hysteresis / fdcd8dc | fdba97f3 / A072 | 配線・RTL不変の2fuse変更。20MHz合格、25MHz失敗 |
| CLK整形＋vendor RAM＋coverage pipeline | codex/clock-filter / 255e5da | 6c5a10f5 / 7D1F | 公式3domain STA合格。SDK標準POSで8/10MHz、NEGで16/20MHzの各6比較合格。25MHzは両位相失敗 |
| CLK整形＋バッチ | codex/filtered-batch-hold / 88d15cd | 85bac224 / E368 | 全4種STA・CPU参照・BATCH等のオフライン検査と独立review合格。実機未試験 |
| MEM BIST | codex/mem-bist / 658c893 | 62ffa726 / 7A8B | 初回64beat（1KB）が書込みphase1、100ms timeout、verified0 |
| MEM native診断 | codex/mem-native-diag / 1f21915 | cc7a76bd / 990E | 14コマンド・15データ受理後の受付待ちを取得。DDRへの書込み完了数ではない |
| MEM内部FIFO診断 | codex/mem-deep-diag / 08ef3a4 | dbcd88fd / 0F25 | 7コマンド・8データ、command read/send_wr進行0を観測 |
| MEM ready-strobe | codex/mem-ready-strobe / 11d7b04 | 801f478d / A40E | readyでenableを制御し余分なpointer wrapを抑えたが、scheduler停止とBIST失敗は残る |
| MEM scheduler診断024f | codex/mem-scheduler-diag / 872ffa4 | 845dd60a / 579E | 先頭コマンド・26bit状態等の観測候補。全4STA・CDC・ピン・host build合格、実機未試験 |

各行のFS全文hash、source、test・STA結果は対応ブランチの`fpga/validation`へ保存した。元のsource/FSを改変せず、失敗STAも保存した。登録済みDATA出力の次期案は設計段階で、実装・試験済みとしていない。

## 成功版と失敗記録の保存

[hardware-checkpoint manifest](../fpga/validation/hardware-checkpoint-2026-11-04/manifest.json)に20MHz成功版944 FS、元のbuild manifest、書込み記録、実行したoperator recipeをgzipで保存した。復号後のbyte一致とSHA256を検査した。スクリプトは当時のローカル絶対パスを保持した記録で、plan-onlyがdefault。

OSSでpackした944等は公式ProgrammerのSRAM書込みoperation2が100%後exit254になった。成功へ書き換えず保存し、独立status6020/User9320と実アプリのCRC・全画素比較を別の根拠として記録した。公式EDA生成のMEM・6c5aイメージはoperation2/74/73ともexit0だった。UserCodeは各FSの実header/footerから照合し、誤って引継いだ990Eの旧表記は訂正済み。

MEMの初回を含む失敗実機系列は、`codex/mem-scheduler-diag`の`fpga/validation/mem-checkpoint-2026-11-04.json`および各保存先に、raw・Programmer log・FS・STAのbyte一致を検証して保存した。

## タイミング・位相の解釈

新しい公式GFX候補はcore54・sampler216・conditioned reply54の実経路を検査した。旧OSSの「no interior paths」やpost-place passthroughのcoverage不足を、実216MHz合格とは扱っていない。旧OSSのruntime成功と完全な公式STA signoffも区別する。

88d15cdのCDC例外は、保持metadataの非同期第一段30組だけに限定した。mapped source Q→stage0 D→同bit stage1 Dのsole fanout、source保持、8byte prefix、最初のRAM latchを機械検査し、stage0→stage1の全30 setup/holdは通常STAで検証した。その他のoffer・FIFO・算術・reset pathを追加除外していない。恒等LUTは合成で吸収されており、routing closureを「bufferが遅延を増やした証明」とは呼ばない。

P4のDIV→RX_INV_I→CLK_RX→Gate→RX_INV_O→CLK_RX_outという公式クロック図に照らし、以前のi=1/o=0を「出力位相を変えない受信位相だけの反転」とした説明を訂正した。SDK標準NEG0/0とPOS1/1の実機系列を新しく分離した。PAD波形位相は未測定。6c5aのSDF-derived serializer→DATA最長17.054ns（clock配線込み19.991ns）はstructural corner上限であり、sensitized pathの実測やジャンパ線上限の証明ではない。

## DDRで分かったことと未達

設定はMEM324MHz・USER81MHz・x16・row13・CL6/CWL5・configured128MiB。IP校正完了は観測したが、読書きBIST・全域容量・帯域・長時間試験は未合格。FPGA DDRをLinuxの透過的なmain RAM増設とは扱わない。

最初のidle観測でcommand FIFO emptyを確認。strict-strobe後は7受理→write pointer7となったが、read pointer・send_wrは進行しない。生成IPの公開回路から、1:4 BL8の1コマンド＝128bit1件、command readyはfullの反転、scheduler入口にwrite FIFOの隠れた8データ条件がないことを照合した。次は024fのhead/pre_info/issue/state観測で停止条件を絞る。原因が確定した、DDRへ7件書けた、128MiB全域を確認した、とは主張しない。

追加観測VOは出力portとassignだけを追加し、それを取り除くと元の生成VOへbyte一致で復元できる。pstateの未提供6bitは0とvalid mask0x0277EFEDで明示し、状態aliasを捏造しない。Linux/MeOSの新しいGFX/MEM driver実装は未対応として各実験仕様に記録し、共通ABIとESP実機確認を混同していない。

## ホスト側と再開点

[Tab5側の保存点](https://github.com/airpocket-soundman/tab5-fpga-gpu/blob/codex/cpu-gpu-demo/docs/DEVELOPMENT_CHECKPOINT_2026-11-04.md)に生ログ138件、BIN/FS対応、HTML、復旧用host firmware/configを保存した。ソース・実験ブランチを両リポジトリへpushし、既存`main`は変更しない。

現基板は6c5a FPGA／5e23 hostの診断状態でソフトウェアARM解除。成功済みフルアプリは944 FPGA／9029 host。残作業はDATA登録出力、filtered+BATCHと024f候補の実機確認、DDR原因解消、長時間soak、モデル常駐・framebuffer・残り5シーンである。
