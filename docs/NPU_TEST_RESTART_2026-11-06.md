# NPU試験再開（2026-11-06）

NPUの既存部品を再試験した。Tab5/FPGAの書込み・ARM・GPIO操作は行わず、GPU Julia MORPHの現行保存点を維持した。

|試験|結果|範囲|
|---|---|---|
|NPU host vectors|9件PASS|生成・独立参照照合|
|MAC/量子化/内積RTL|3種類PASS|Icarusによるcycle単位の照合|
|関連RTL回帰|全11種類PASS|GFX/リンクを含む既存runner|
|GW2A部品合成|MAC/量子化/内積すべてPASS|I/Oなし。配置配線・タイミング・実機ではない|
|ESP-IDF CPU参照|17件PASS|Conv、量子化、2層接続、ファイルprobe、weight package。通常とUBSan|

CPU参照側は102772 scalar、16通りの2層接続、68箇所のI/O失敗点を含む。RTL側はstall、reset、符号端値、overflow、異常parameterの拒否を含む。内積の合成ではMULT9X9×1とMULT36X36×1を使用する。合成cell数を20K FPGA全体の搭載余裕や到達周波数に換算しない。

## 再現

`python fpga/tools/run_existing_rtl.py --npu-only --require --iverilog EXISTING_IVERILOG --vvp EXISTING_VVP`

NPUのみ実行する選択肢を追加した。既定の全RTL回帰は維持。既存compiler/runtimeを使用し、インストールやUSB操作は行わない。

各部品の合成は `python fpga/builds/components/build.py mac|requant|dot --yosys EXISTING_YOSYS` を各名称で実行する。

[原記録・ソース・合成結果](../fpga/validation/npu-retest-2026-11-06/evidence.zip)、[manifest](../fpga/validation/npu-retest-2026-11-06/manifest.json)。

## 実機試験に残る段階

1. DDRなしの内積jobを既存LINKへ接続する独立NPUビットストリームと、ホスト共通の能力照会・parameter検証・timeout/abort仕様を確定する。
2. 同じvectorをTab5から転送し、CPUとFPGAの全出力一致を確認。送信・計算・受信を分離して測る。
3. DDR tile入出力を接続し、Conv/量子化の層単位照合、メモリpeak・転送量を確認。
4. 実モデルの校正と必要operatorを確認してgraphへ進む。

現状はhost-accessible NPU bitstream、DDR接続、descriptor実行器、全モデル推論が未実装。上記合格をNPU実機動作や推論高速化の証拠にはしない。

## ホスト照合

ESP-IDF bf111d7のProject_B・推論・通信・表示、Linux cfc9a6eのREADME/DEVELOPMENT_GOALS/Device Tree（FPGA driver未実装）、MeOS 78274b4のREADME/FPGA_CARRIER_REQUIREMENTS/通信とNPU CPU参照、外部メモリ研究e84b59eの計画を確認。MeOSのNPU関数もCPU参照で、wire ABIは未定義と明記されている。今回はRTL算術・仕様・pin・電源を変更せず、各ホストdriverへの反映は不要。次のNPU command追加前に全ホストへの適合をレビューする。
