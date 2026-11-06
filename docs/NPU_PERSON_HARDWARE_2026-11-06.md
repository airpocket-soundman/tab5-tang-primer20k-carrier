# 人物サンプルとNPU実機の初回接続（2026-11-06）

NPU単独版をDockへSRAM書込みし、Tab5からINT8内積を実行した。FPGAには人物検出全graphをまだ実装していない。検出全体はPC FP32の参照結果、実機は先頭Convの一部をINT8化した算術試験である。

- FPGA USERCODE **4E02**、status6020、能力4E01、27MHz。GFX16D0と同時搭載しない。
- Tab5 ELF **c0a8d87fbebe98a3c41a7ef3ded4a752f6a6395695f2aad65d7752ff3232c3e5**。
- 内積回路・MAC・量子化を既存LINKへ接続。[コマンド契約と全ホスト影響](NPU_DOT_V0.md)。新コマンド、パラメータのlittle-endian byte設定、有限待ち、CRC/sequence、正常累積値読出し、中断を定義した。GPIO/電源/Dock .cstは変更しない。
- pin-level 2434コマンド、32演算条件、CRC不良、状態・設定不良、正負overflow、watchdog/復帰に合格。既存LINKのID/echo/CRC等とNPU primitive3種類も回帰PASS。
- 実機正常63条件（shift0..62、length0/1/27/128）、不正入力11件の無送信拒否、正負overflow2件と明示再ARM後の復帰がPASS。
- 人物画像の4位置×全8出力channel、27 MAC/位置の32jobでINT32累積とINT8出力がCPU/Python参照へ一致。通信エラー増加0。

## 性能と資源の扱い

27pair/1jobは現在57回の8byte要求・8byte応答、912 wire bytesを使う。実測平均はhost job13.394ms、TX5.580ms、RX4.584ms、READY待ち0.113ms。P4参照約9.9usにはhex decodeと量子化も含む。FPGA活動30cycleは約1.11us相当だが、入力待ちを除いたcycle集計であり独立した連続kernelの実測時間ではない。job cycleはhost待ちを含む。現在のend-to-endはCPUより遅い。大量の重み・activationを常駐/一括投入する方式へ進むための正確さの基準点で、NPU高速化成功とはしない。

Gowin Education1.9.11.03で配置配線・bitstream生成。標準1.9.12.04はlicense fileが開けずビルド不可だったため既存Education版を使用した。sys27MHzのSTAと資源はcandidate ZIP内の実レポートを参照。非同期GPIOの外部setup/hold全体をSTAで認定していない。小さい単独内積回路のfitをDDR Convや全モデルのfitへ拡張しない。

## 検出モデルとサンプル

[PINTO Wholebody25](https://github.com/PINTO0309/PINTO_model_zoo/tree/main/459_YOLOv9-Wholebody25) N post128×160、SHA b78f1691…を再取得。raw128×160も旧監査52f84f84…と一致。NASA/scikit-image astronaut画像でPC ONNX Runtime CPU参照を実行しBody/Head/Faceを確認。実機fixtureは入力と重みの例示対称INT8化で、全モデルの校正や検出精度は未検証。モデルbinaryはGitへ収録しない。

## 初回失敗と修正

初版USERCODE4E01は、overflow後の54h取得ではstatus5を返すが、5Ah正常累積読出しではstatus4を返していた。実機境界試験で発見。失敗時に数値結果を公開せずDISARMした。4E02では5Ah等もtyped faultを優先し、pin-level regressionと同じ実機63+11+2条件を再実行して合格。旧失敗記録はホスト保存物へ残す。

## 次の順序

1. 一括投入・weight cacheで小要求の往復を削減し、同じ画像/重みで全先頭Convへ拡張する。
2. DDR配置・Conv tile engine・層間INT8契約を接続する。
3. SiLU/Add/Concat/Pool/Resize/DFL等の必要operatorと校正を揃え、全graphを閉じる。
4. 固定画像の全モデル実機推論が合格してから、内蔵カメラ（BSPはSC202CS対応）を同じ入力経路へ接続する。カメラの実機captureは今回未実施。

[FPGA保存物](../fpga/validation/npu-dot-hardware-2026-11-06/)。最終状態はNPU単独版4E02、Tab5 NPU試験画面、DISARM。GPUへ戻すにはTab5停止・DISARMのまま既存16D0をSRAMへ再ロードし、GPU LINK ARMで能力確認する。SPI Flashは変更していない。
