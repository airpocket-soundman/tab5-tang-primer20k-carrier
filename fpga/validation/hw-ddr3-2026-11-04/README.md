# DDR3 ペア発行候補イメージの実機結果（2026-11-04）

イメージ `be42c604`（UserCode 0xB317）をSRAMのみに書込み、ホスト MEM probe ファーム（ホストmain `6ad1ed6`、ELF SHA-256 `f7c84fe7…`）で確認。

## 段階1（読取り専用）：合格
capability 024f が返った。calibrated=1、command_ready=1、data_ready=1、scheduler_init_done=1、pre_info_valid=0、リフレッシュ要求なし、コマンドFIFO空。

## 段階2（64ビートBIST）：失敗（従来と同じ停止）
書込み段階（phase 1）で error 3（進行なし）。失敗後の観測：
- accepted_commands=7、accepted_write_data=7（ペア発行は機能している）
- コマンドFIFO満杯（write pointer 7、read pointer 0、advances 0）
- scheduler_send_wr は一度も立たない（high cycles 0）、head_write=1
- refresh_request が立ったまま、pre_info_valid=0、bank_state=0

結論：ペア発行だけでは直らない。スケジューラがコマンドを一つも取り出していない。次はメモリクロック（400MHz）、ddr_cs、リセット/PLL lock、リフレッシュ/ZQ待ちを1項目ずつ変えた別イメージで切り分ける（再試行はしていない）。
