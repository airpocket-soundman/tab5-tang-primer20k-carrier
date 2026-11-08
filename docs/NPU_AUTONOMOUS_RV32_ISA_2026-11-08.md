# FPGA内RT-DETR firmware：RV32 ISA検証（2026-11-08）

## 選択済みv7：dirty BSSから全モデルISA実行完了

v6のlinker修正後、v7はMatrix schedulerをFPGA内RV32へ移し、同じ共通Tile MACへ展開する構成とした。v6/v7とも、実ELFのALLOC/NOBITS BSS352Bへ0xA5を書き込んでから起動し、全649演算/57Conv/65MatMul-Gemmを完了した。v7のMMIOは400,368 Tile要求、Matrix command2は0。論理matrix jobは13,067で、NNの行列積をP4やRV32の通常乗算ループへ置換したわけではない。

v7 BINは`0a6fafafc2f56bd5d65d2ce2411b8f91f4ca77d7c2aad12d06d5093edbf3f876`。全1800出力はv6とbit完全一致し、SHA256は`9a4e9b9319e2b2592c9c10d2134c97b71226f0bf32e3b4774dfeb71feca6f715`。実機NN出力を見る前に、同じv7 ELF/BINの物理試験用goldenとして固定した。**この段階の証拠はISA＋INT64 accelerator oracleであり、実FPGA上の全モデル完走ではない。**

v7はhost上472秒、step212,125回、data read18,887,859,307/write13,387,495,518 callbacks。v6は461秒、step212,041回で同じ数値結果。ホスト時間やstepの概算を実機時間と呼ばない。全firmwareソースのcompile時hashと保存snapshotを照合し、一致を確認した。v7のpayload CRC/typed metadata CRCの負試験も、dirty BSS状態からAP_FAILED/error5/4、MAC0・出力非公開を確認した。

[ISA固定証跡](../fpga/validation/npu-autonomous-isa-2026-11-08/README.md)／[4E30全chip fit・STA・実core RTL検証](../fpga/validation/npu-autonomous-4e30-2026-11-08/README.md)／[RUN制御の独立13ケース・57assertion](../fpga/validation/npu-autonomous-run-control-2026-11-08/README.md)。

## 現在の版について

以下のv5結果は履歴である。後のレビューで旧linkerのBSS境界に不具合が見つかり、ゼロ初期化済みのemulator RAMでは隠れていた。**v5を実機へ配備する根拠として使わない。** 境界修正版v6ではBSSを0xA5で汚した状態から検証を実施し、資源削減版v7ではMatrix descriptor生成をFPGA内CPUへ移して同じhardware Tile MACを使う。v6/v7の結果は上記の別証跡で確定した。

また本実験は各RUN前にfirmware BIN全体を再uploadしreadback検証するcold契約である。CLEARだけではmutable .data初期値を復元しないため、warm再起動と扱わない。P4はその搬入・表示だけでNN計算を行わない。

## 到達点と検証の境界

実際のRV32IMC ELFを、F拡張/JITなしのinstruction-set interpreterで実行した。raw RGB640入力のBGR/FLOAT変換、typed metadata/source/payload CRC検査、量子化、全649演算の制御、非MAC処理、逆量子化、検出結果の生成はRV32命令で実行した。Conv/MatMulのMMIOだけを、ホストの独立INT64整数oracleへ接続した。

**全649演算/57Conv/65MatMul-GemmのISA実行は完了したが、これは実FPGAで全モデルが完走した証明ではない。** ソフトコアを使う方式であり、全演算を専用並列回路で実装した意味でもない。実RTLのDDR/cache/arbiter/キャッシュ同期・タイミング・実機性能は別に検証する。

|項目|結果|
|---|---:|
|RV32 firmware|v5、RV32IMC、soft-float、FMA contraction OFF|
|graph完了|649ノード、57 Conv、65 MatMul/Gemm|
|MMIO要求|217,280 Tile、13,067 Matrix|
|整数oracleのMAC数（padding含む）|30,148,231,168|
|最終出力|1,800 FLOAT、7,200B、全値finite|
|出力SHA256|`9a4e9b9319e2b2592c9c10d2134c97b71226f0bf32e3b4774dfeb71feca6f715`|
|ホスト上のISA試験経過時間|448秒、実機予測ではない|
|RV32 data read/write callback|18,887,688,997 / 13,372,602,504（oracleのDDRアクセスは含まない）|
|step slice|212,041回、各要求budget 1,000,000|

最後のstepは途中終了し、ブロック境界のovershootもある。budget合計212,041,000,000は概算のinterpreter cycle/instruction budgetであり、正確なretired命令数やPicoRV32サイクルではない。この規模を27MHzの仮の1命令/cycleで割っても約2.18時間となるため、448秒を実機推論時間として使わない。実機はCPI、DDR/cache、MAC待ちでさらに変わる。正確なretired counterは今回保存しておらず、この統計だけのための全モデル再実行はしていない。

## 数値比較

新RV32 firmwareの数値条件は、以前のP4/FMA実行と同一ではない。比較は全出力を保存し、事前のindexed class完全一致＋atol1e-4/rtol1e-3を別列にした。

|参照|bit差/1800|class行差/300|事前indexed float基準|事後diagnostic score>=0.35対応|
|---|---:|---:|---|---|
|native FAST|1741|241|FAIL|45/46、min IoU約0.9668、score差最大約0.07970|
|native OFF|205|27|FAIL|45/45、min IoU約0.99883、score差最大約0.001721|
|以前のP4+FPGA V6|1742|242|FAIL|45/46、min IoU約0.9666、score差最大約0.07425|

事後対応は同class/IoU>=0.5のgreedy one-to-one診断で、ラベル付きAPや元の厳密FAILの代わりではない。原因を丸めだけと断定しない。以前のP4/FPGA分担RT-DETRのFAILも保持する。

このRV32 ELFとISA整数oracleの結果は、実機の全モデル出力を見る前に固定した。今後この**同じv5 ELF**をFPGA内で実行する試験では、上記SHAの全1800出力bit完全一致を新しいFPGA内実行profileの基準として使える。異なるfirmware版や別数値条件にこのgoldenを流用しない。実機出力を見てから基準を選んだものではない。

## 小規模・異常系

- Tiny smokeは実RV32 firmware自身が8 Conv値と6 Matrix値の14 INT32値を検査し、正常終了した。v4/v6（epoch取得変更）で確認。ホストが出力数だけを偽装した結果ではない。
- 同じv5 firmwareへpayload最終byteを1bit変更したpackageを渡した。RV32上のCRC検査でAP_FAILED/error5/payload_crcとなり、Tile/Matrix/MACは0、出力は非公開。期待する拒否として記録し、execution_completed=falseをPASSに書き換えない。
- 現firmwareの異常分類には、hardware error/epoch lossをuser cancellationと同じstateに分類し得る既知の制約がある。出力非公開の安全性とは別の診断課題として残す。

## ツールと再現

[公式rv32emu](https://github.com/sysprog21/rv32emu)をcommit `ffb041bab9d1513e5329f25f486378778dceed13`へ固定した。MITライセンスを証跡へ保存し、WSL Ubuntu24.04/GCC13.3で最小libraryを構築した。独自変更はignored build内の2ファイルだけで、内部I/O callback installerと、user-modeの6個のRAMアクセスmacroをcallbackへ通す変更。upstreamのuser RAM fast pathはcallbackを迂回するため、installerだけだった初回試行はMMIOでsegfaultした。最初の失敗logはbring-up中に上書きされており、不変の原本証拠があるとは主張しない。修正後のsmoke/full logとpatchは保存した。

再現入口は `fpga/npu/tests/run_autonomous_iss.py`。WindowsではWSLを使い、`--fetch`を明示すると公式pinned sourceを取得する。既存checkoutの無関係な変更や別commitは拒否する。新しい出力ディレクトリを必須とし、元の証跡を上書きしない。任意の未信頼ELFのsandboxではない。

```
python fpga/npu/tests/run_autonomous_iss.py --firmware build/npu-autonomous-firmware-v5/autonomous.elf --package MODEL.rqg --image RGB640.ppm --output build/NEW-ISA-RUN
```

[固定証跡・実ELF・output・source patch](../fpga/validation/npu-autonomous-isa-2026-11-08/README.md)、[全ホスト要求の照合](NPU_AUTONOMOUS_HOST_REVIEW_2026-11-08.md)。
