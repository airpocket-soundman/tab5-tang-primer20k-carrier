# MEMV1 の実機結果（2026-11-05）

実施：このPC。ホスト：MEM probeファーム（`claude/memv1-host` 31ad6be 系、ELF SHA-256 `9bda75e5…`）の `xferx`（長フレーム）。FPGA：`mem_v1_top`（旧IP＋自前ロジック、`claude/memv1-adapter` 1cbd008、FS `8dd98907…`、USERCODE 0xA692、PIPELINE=4相当、PLL memory 398.25MHz／USER 99.5625MHz）をSRAMのみに書込み。リンクはGPIO、500kHz以下。

## 経緯
- 初版（USERCODE 0x6470）は、イメージ準備スクリプトがPLLの分周 `IDIV_SEL=3` を落とし、memoryクロックが1593MHzになって校正が完了しなかった（STATUSの校正・USER起動フラグが0、`device_status 5`）。ビルドログの `PA1019`／`TA1123` で検出できる。修正版で再ビルド。初版の `.fs` は無効。
- `readonly.json` は初版（失敗）、`v2-readonly2.json` と `v2-full.json` が修正版。

## 修正版の結果（`v2-full.json`、result PASS）
caps、status（診断語7＝0x01bb、世代1）、rd1、rd256（4096B）、wr1、wr256（CRC32 0x1ae63def）、crc32（FPGA側計算、一致）、invalid（14ケース）、crc_error（5ケース）、tail（0x7fff000）、cancel（`wr_completed_cancel_dropped`）。上書き領域は 0x100000 からの8KiBと末尾4KiB。

## 限界
- 帯域は未測定（リンクはGPIO・500kHz以下、4KiBで片道約1.3秒）。DMA経由の高速化は未実施。
- CANCELは、決定的に実行中へ当てられず、`wr_completed_cancel_dropped` に分類された（取消しの実効性は未検証）。
- STAは診断用の非同期SDC下の結果（最悪setup +0.057ns）。冷起動の繰返し、温度、長時間は未実施。旧IPの再配布条件は未確認。
