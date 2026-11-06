# NPU Transformer実機検証（2026-11-07、4E21）

**既存4E21の1×1 Conv回路で、学習済みDeiT-tinyの全74 MatMulを実FPGA実行した。保存した1000 logitsは同じP4上の独立CPU整数積和参照と全ビット一致した。** 初回PC native参照との数値FAILは保持する。最終UI版のFPGA再試験v3も全1000値bit一致で合格し、画面確認後はFPGA結果表示・idleとなった。

## 回路・処理範囲

Transformer専用のRTLや新opcodeは追加していない。`conv_tile_engine_8oc.v`、DDR loader/core、LINK、pin、電気条件は4E21から変更なし。USERCODEは4E21、wire capabilityは互換4E20。bitstream SHA256は`a9bdae1126f7ffdba349d14293271addbeb4901cee3019bb2315383bf650c05c`。

ホストがA[M,K]をCHW、B[K,N]をOIHWへ量子化・配置し、IC16/OC8でK方向を継続積算する。M197はOH13/OW16へまとめ、余分なtokenを0で埋めて結果から除く。Aはtokenごと、Bは出力列ごとの対称INT8 scaleを使う。patch projection、QKV、QKᵀ/AV、projection、MLP、classifierの全MatMulがFPGA積和を通り、失敗時のCPU MatMul fallbackはない。

LayerNorm、GELU、Softmax、bias/residual、量子化・逆量子化、グラフ制御はP4が行う。定数と活性値はFPGA DDRに置く。全NNがFPGAだけで動く構成ではない。配置・API・native/RTL証跡は[DDR MatMul検証](NPU_DDR_MatMul_検証_2026-11-07.md)を参照。

## 実機の到達点と数値判定

対象は固定revision `b3428f18dcc7b543470d07f14b4a4157815d1880`の`facebook/deit-tiny-patch16-224`、224×224 RGB/197token/12 block/1000クラス分類。重みSHA256は`e1a51b0c81ff812e079d2189352747947879fee56429e4480064a6695cb34b2c`。公式transformers実装によるモデル変換照合と実機INT8精度は区別する。

| 試験 | 確認結果 | 判定 |
|---|---|---|
| 初回実FPGA、CREW | 12 block、199演算、74 FPGA MatMul、122 batch、51468tile、CPU MatMul0、session維持 | 全グラフ完走 |
| 初回FPGA対PC native FMA | 最大差0.145496249、平均0.033049703、974/1000値が0.001超、Top5同順 | **事前最大差0.001基準はFAILのまま保存** |
| 同じP4のCPU整数積和参照対保存済み初回FPGA | 全1000値がbit一致、最大差0、CPU MatMul74/FPGA0 | **厳密比較PASS** |
| 最終UI版FPGA再試験v3 | 全12/199/74 FPGA/122 batch/51468tile、CPU MatMul0、phase集計一致、全1000値bit一致 | **PASS、最大差0** |

P4 CPU参照と保存済み初回FPGAの共通出力SHA256は`ee03e13dffb253c886318761969da2fd3de6ae40f41e10ca0eeb24544525240b`。共通のhost量子化・CPU非MatMul処理に対し、積和を独立CPU演算へ替えて照合した。これはPC/P4間で異なる参照の試験を分けたもので、初回FAILを基準緩和により合格へ変えたものではない。cross-target float差の発生箇所そのものは未特定。

最終FPGA v3は推論625.110044秒・総742.005252秒、P4 CPU参照は推論62.204609秒・総123.868030秒。初回FPGAの625.179秒/741.946秒も履歴として保持する。CPU側はPSRAMへ25,440,336Bを確保した。CPU版と最終UI版はELFが異なるが、graph/MatMul/DDR serviceの6ソース一致を確認した。PSRAMと外部DDRのI/O経路差を含む実測比較で、現FPGA推論時間はCPUの約10.05倍。FPGAの速度優位や、このDeiTでのPSRAM容量超えは主張しない。YOLO S256の32MiB超え実証と、未完走のS544は別試験である。

## 現在の版と証跡

host worktreeは`tab5-fpga-gpu-resume-20261106`、branch `codex/resume-20261106`。hostソースの確定commitは`1db0d022d6e54b3ce046836ba8126de90a13ff20`（push済み）で、保存checkpointにも記録した。[hostのTransformer検証報告](https://github.com/airpocket-soundman/tab5-fpga-gpu/blob/codex/resume-20261106/docs/validation/transformer-2026-11-07.md)に取得元、公式照合、処理分担、時間を記録する。

- 初回FPGA：host `build/transformer-device/crew-rowwise/{result.json,FPGA_DDR.f32}`。ELF `f8faa2d9c90492182259a2cff7df048edddabed0c9b2009f528696f7824b9ab1`。PC比較FAILも同dirに残す。
- P4 CPU比較：host `build/transformer-device/crew-cpu-v1/{result.json,CPU_REFERENCE.f32}`。ELF `bb09cf0ae4766f37a54c765dd14523cc81a5407efd23e9b5e36811ff06662dd4`。
- 最終UI v3：host `build/transformer-device/crew-fpga-v3/result.json`、ELF **`a31e8dae6fccde1fea5da46241c79bb910fb5c3df28509f63891307ab304cb75`**。最終判定PASS、全1000値bit一致。画像pivot修正、SD3画像選択、CPU/FPGAセレクターが見えることを画面確認し、最終状態はFPGA結果表示・idle。
- host `build/transformer-device/math-source-identity.json`で初回/CPU版/最終UI版のgraph・MatMul・DDR serviceの6ソースhash一致を確認。UI変更前のv2はupload中にSTOPで明示中止し、数値不一致とは区別する。
- carrierの`fpga/build/matmul-ddr-packed-pin-proof/`と`matmul-ddr-rowwise-pin-proof/`に既存4E21の全ピン試験とsource snapshot一致を保持。後者はM197/K64/N9のsmokeであり、全モデル実機証跡へ置き換えない。

carrier内の実機保存物は[transformer-device-2026-11-07](../fpga/validation/transformer-device-2026-11-07/)。`first-fpga-failed/`、`physical-cpu-reference/`、`final-fpga-v3/`の3結果・3raw tensorを保存し、`checkpoint.json`と`SHA256SUMS.json`で照合する。host最終版の保存先は`docs/validation/transformer-2026-11-07/final-fpga-v3/`。初回FAIL・CPU一致・最終再試験を別々に保持する。

## ホスト適合性と残る制限

前段の要求照合版はLinux `cfc9a6e`、MeOS `78274b4`、外部メモリ研究 `e84b59e`、ESP-IDFは上記resume開発版（確定commit `1db0d02`）。これらは要求照合時の版であり、各repoの現在HEADという意味ではない。今回wire/pin/電源/DDR方式の変更はなく、新しいコマンドへの移行は不要。Linux/MeOS向けのTransformer/MatMulホストアダプターは**未移植・未検証**で、ESP-IDFの実機結果を全OS適合として扱わない。DDRは明示READ/WRITEのデバイスメモリで、透過的なLinux主記憶増設ではない。

4E21はLogic10979、Register6015、BSRAM45/46、DSP12.5/24で配置配線した診断版。無例外STAにはsetup1408/hold111違反が残り、vendor reset/CDC等が未解消。同一ドメインTNS0や実機完走はtiming sign-offではない。[4E21実装検証](NPU_8OC候補4E21_実装検証_2026-11-07.md)を参照。GPIO half/setup100nsは公称ソフト待ちであり、実測周波数・配線限界ではない。

最終UI版v3の完走・1000値・時間・画面確認は完了した。次は[hostの通信・量子化高速化候補](https://github.com/airpocket-soundman/tab5-fpga-gpu/blob/codex/resume-20261106/docs/TRANSFORMER_NEXT_OPTIMIZATIONS_2026-11-07.md)を数値基準を維持して検証する。S544の全層実機完走と数値・時間は引き続き未確認。確定host commitはcheckpointへ記録済み。
