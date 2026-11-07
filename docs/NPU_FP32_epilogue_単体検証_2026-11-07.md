# NPU FP32 MatMul epilogue単体実装（2026-11-07）

MatMulのINT32出力をFP32へ戻す独立RTL `npu_fp32_epilogue` を追加した。既存4E22のRTL・top・通信・ピン・buildは変更していない。FPGA内で隣接演算を連続実行する[計画](NPU_常駐重みと連続推論計画_2026-11-07.md)の最初の演算部品であり、DDR連結や全Transformer実行を実装したという意味ではない。

## 演算とAPI

ホスト `ddr_matmul.cpp` の実際の式 `float(sum) * (A_scale * B_scale) * alpha` に合わせ、以下を順番に個別丸めする。括弧の移動・FMAは行わない。

1. signed INT32 → FP32、RNE（最近接・同距離偶数）。INT_MAXは2^31へ丸め、INT_MINは正確に変換する。
2. `row_scale * column_scale` → FP32。
3. 変換済みINT32値 × 手順2の結果 → FP32。
4. 手順3の結果 × alpha → FP32。現モデルの1/.125だけでなく対応範囲のFP32値を受け付ける。
5. `bias_enable` が1なら、独立したFP32加算としてbiasを加える。biasは将来graph側の明示演算に接続するための追加機能で、現ホストMatMul内にbiasがあるとは扱わない。

入力はclk/reset_n/abort、in_valid/in_ready、accumulator[31:0]、row_scale/column_scale/alpha/bias[31:0]、bias_enable。出力はout_valid/out_ready、result[31:0]、error、error_code[3:0]。1要求だけを受け付け、出力は受理まで保持する。入力・出力双方の停止が可能で、abortまたは同期resetが入力受理・出力受理より優先する。abort/resetは未完了結果と既存出力を破棄する。

通常結果の出力は受理後3クロック、bias付き非ゼロ加算は6クロック。出力消費後の次受理に1クロック境界を置くため、連続ready時の開始間隔は通常5、bias付き8クロックとなる。エラーやゼロ加算は早く完了する場合がある。これは単体FSMのサイクル数であり、DDRやシステムの実測性能ではない。

## 数値profileと明示エラー

RNE、有限normal、±zeroを対象とする限定profileである。全IEEE754実装ではない。符号付きゼロ、exact cancellationの+zero、ties-to-evenを扱う。24×24bit乗算器を3段の乗算で共有する。bias加算は整列・加減算・正規化丸めを別クロックに分けた。BSRAMは使わない。

| code | 意味 |
|---|---|
| 0 | 対応範囲の数値出力 |
| 1 | 使用するFP32入力がsubnormal、NaN、Inf |
| 2 | 丸め結果が有限normalの上限を超えるoverflow |
| 3 | exact非ゼロ中間結果が最小normal未満 |

code3はIEEEのunderflow flagそのものとは異なる。このprofileは、丸めれば最小normalへ上がる境界もexact値がnormal未満なら拒否する。tinyをゼロへ黙ってflushしない。エラー時はout_validとerrorを提示し、resultビットは0だが数値として採用してはいけない。成功値・エラーを同じハンドシェイクで消費する。無効なbiasはbias_enable=0なら検査しない。scaleの正値制約は上位descriptor側の役割で、単体演算は有限の負値も計算できる。

## 独立検証

[RTL/試験/合成証跡](../fpga/validation/npu-fp32-epilogue-2026-11-07/checkpoint.json)と[SHA256](../fpga/validation/npu-fp32-epilogue-2026-11-07/SHA256SUMS.json)を保存した。再実行は `python fpga/npu/tests/run_fp32_epilogue.py`。Icarus、vvp、NumPyが必要となる。既定出力先は新規部品専用buildディレクトリで、既存bitstreamは触らない。

29,085件に合格し、成功20,229、overflow5,474、unsupported20、tiny3,362だった。独立oracleはNumPyのfloat32変換・乗加算を各段で実行し、exact productを表現できるfloat64でtiny範囲を別検査する。RTLのleading-bit/shift/丸めアルゴリズムはoracleへ移植していない。INT_MIN/MAX、2^24付近の整数丸め、全normal指数範囲、加算指数差1/23/24/25/26/31/32/63/64/100、正負ゼロ、相殺、NaN/Inf/subnormal入力、無効biasの無視、ランダム値を含む。

各結果の3クロックbackpressure保持、abort同時valid/ready、計算途中abort、出力待ちreset、計算途中resetと再試行も検査した。実モデルの全INT32・scale traceは未収録であり、この単体試験をモデル全体の数値証明へ読み替えない。実接続前にP4保存値とのtrace比較と、対応外値が実モデルで発生しないかの全件検査が必要となる。

丸め用語とfull IEEE対応との境界の確認には、一次資料[Berkeley HardFloat documentation](https://www.jhauser.us/arithmetic/HardFloat-1/doc/HardFloat-Verilog.html)を参照した。HardFloatソースを複製した実装ではない。

## 合成資源と残る条件

Gowin V1.9.11.03 Education、GW2A-LV18PG256C8/I7、単体合成のみを行った。初版は推定Fmax26.486MHzで27MHzを下回ったため、bias加算を段階化した。初版レポートと失敗条件も残している。

| 段階化後の単体合成 | 値 |
|---|---:|
| Logic | 3,112（LUT2,902 + ALU210） |
| FF | 380、latch0 |
| DSP | 2（MULT36X36×1、ALU54D×1） |
| BSRAM | 0 |
| 合成推定Fmax | 34.995MHz |

現在4E22へ単純加算した目安はLogic14,156/20,736、FF6,398、DSP14.5/24、BSRAM45/46となる。ただし単体合成結果の足し算は、統合後の資源・配線・Fmax・DDR arbitrationの証明ではない。合成の既定clock constraintは100MHzなのでその制約自体には未達であり、34.995MHzも配置配線後の値ではない。27MHzでの統合STAや実機確認は行っていない。既存4E22自身のSTA未認定も解消していない。

DDR書戻し接続、scale供給、requantization、bias/residualのDDR読出し・融合、量子化、LayerNorm/Softmax/GELUは別段階である。全ホスト向けコマンド・precision profile・失敗時の部分出力無効化をレビューするまで、既存プロトコルへの追加やピン変更は確定しない。参照ホスト版・未実装範囲は常駐推論計画に記録した。
