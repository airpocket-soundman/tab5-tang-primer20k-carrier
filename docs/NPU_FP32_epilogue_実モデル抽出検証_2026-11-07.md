# FP32 epilogue：実モデルからの層化抽出検証（2026-11-07）

[FP32 epilogue単体](NPU_FP32_epilogue_単体検証_2026-11-07.md)を、DeiT-tiny全12ブロックの実際の中間値で検査した。ホスト `ddr_matmul.cpp` のコピーにだけ計測フックを追加し、既存FPGA RTL・ホストproductionコード・モデル・bitstreamは変更していない。

## 試験対象と抽出範囲

固定DTP1 packageはSHA256 `1e297d336e6e204d09fc01139012c211fb3e56c61f67f84455c71f35a6af3d21`。SD準備済みCREW/ASTRONAUTの正規化RGB FP32入力を用いる。各画像で全74 MatMul、122バッチ、各出力列について、行0・floor(M/2)・M−1を抽出した。同一行は重複させない。全5,974,636出力中91,972件（約1.54%）の層化抽出であり、全出力の証明ではない。

記録はINT32累積値、A行scale、B列scale、alpha。静的BはModel.weight()のaddress照合で識別し、直後のweight index+1から実biasを読む。静的Bの63,784件はbiasを独立加算し、QK/AVの28,188件はbias無効とする。記録フックはgraphへ値を書き戻さない。サンプル元の全graphは、計測後も各画像の既存native FP32最終1000値と全ビット一致することを必須とした。

## oracleとRTL

C++側の実式 `(float(sum) * (A_scale * B_scale)) * alpha` の各FP32丸めを保持し、必要なbiasを別の加算にする。NumPyの独立float32順次演算が、計測C++期待ビット列と一致することを全サンプルで確認した。その後、同一入力をIcarusで実RTLへ渡し、bit exact・error0を検査した。出力backpressure、計算途中abort/reset、同時valid/readyの優先順位も単体試験のTBを再利用して確認する。

RTLはSHA256 `dc59532b8d5a591f3ef8cc84e9b5488787552c9b4aa2cabe6f0a91e7dab5f916` のまま。限定normal/zero profileの対応外値は、この抽出範囲では発生しなかった。全モデルの全中間値が対応範囲に入るという主張ではない。

[検証証跡](../fpga/validation/npu-fp32-model-trace-2026-11-07/checkpoint.json)には画像別result、native/RTL実行コマンド、最終1000値、圧縮した層化サンプル、計測コピーと生成harness、元ソースSHAを保存する。モデル本体・画像本体・巨大vectors/vvp/netlistは保存しない。圧縮サンプルの形式は各レコード11個のuint32 LEで、operation、batch、row、column、signed sumのビット、A scale、B scale、alpha、bias、bias enable、期待FP32ビットの順。モデル・入力のSHAと全列/行/バッチのcoverageはresult.jsonに記録する。

再実行例：`python fpga/npu/tests/run_fp32_model_trace.py --host D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106 --image CREW`。ASTRONAUTは `--image ASTRONAUT --output fpga/build/epilogue-model-trace-astronaut`。Zig C++、NumPy、Icarus/vvpと、固定package/準備済みFP32画像/既存native参照出力が必要となる。source_snapshot下のコピーだけを計測用に変更し、最後にproductionソースのSHAが不変であることを確認する。

native graphのoperation番号はprogress observerを付けた時だけ進む既存仕様のため、harnessはno-op observerを指定する。演算内容は変えない。今回のgoldenはnative FMA-fast参照である。CREWのSHA `f4fe056e8b93134171d8aeaf482e942a3c1bb9eb7c65d8234d868ac687c76f04` は、実機P4参照の `ee03e13d...` と異なる。既知のPC/P4浮動小数差を取り消したり、実機trace取得済みと扱ったりしない。

この試験では合成・配置配線・実機アクセスは行っていない。DDR epilogue接続、scale供給、オペレータ融合、LayerNorm/Softmax/GELUのFPGA化は引き続き未実装である。

## 確定結果

| 画像 | 抽出数 | bias有効 / 無効 | NumPy対C++ | RTL対期待値 | graph最終1000値 |
|---|---:|---:|---|---|---|
| CREW | 91,972 | 63,784 /28,188 | 全bit一致 | 全bit一致、error0 | 既存native goldenと全bit一致 |
| ASTRONAUT | 91,972 | 63,784 /28,188 | 全bit一致 | 全bit一致、error0 | 既存native goldenと全bit一致 |

合計183,944件に合格した。ASTRONAUT最終値SHA256は `7a9075b7689f720034f837c2b34230f3e6f4a9408b52d9ffa3e353794d72d376`。証跡アーカイブは約2.77MBで、画像ごとの圧縮fixtureは約1.32MB。fixtureは実モデル中間値の層化標本であり、モデルパラメータ・入力画像・全中間tensorのコピーではない。
