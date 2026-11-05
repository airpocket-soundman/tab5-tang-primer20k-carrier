# ESP32-P4 v1.3 DMA初期化監査（2026-11-05）

読み取り専用調査。実機操作・ファーム変更なし。調査時ホスト版 `tab5-fpga-gpu-display` HEAD `7a0cb6272830e8f961dec0f5520e06242bcb7c1c`。開発中のため下記行番号はこの版を基準とする。

## 実機と一次資料

保存済み `tab5-carrier-memv1-resume/fpga/validation/memv1-resume-2026-11-05/flash-dma-guard-cost.txt:5` 等の書込みログは `ESP32-P4 (revision v1.3)`。最新v3.x資料を実機の代わりに使用しない。

- [ESP32-P4 Chip Revision v1.3 TRM, pre-release v0.4](https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_technical_reference_manual_en.pdf)。取得物20,786,220 bytes、SHA256 `ae1fa2a411776760e03329adc3f9a7c13e98c440168cab208f06e3b2d5818830`。PDF本文のページ番号とPDFページ番号は該当箇所で一致する。PDF自体はリポジトリに含めない。
- [公式errata summary](https://docs.espressif.com/projects/esp-chip-errata/en/latest/esp32p4/02-errata-summary/index.html)：DMA-767はv3.0対象、v1.3は対象欄なし。今回のFIFO問題をこのerratumの実証としない。
- [ESP-IDF v5.5.2 PARLIO LL](https://github.com/espressif/esp-idf/blob/v5.5.2/components/hal/esp32p4/include/hal/parlio_ll.h)、[TX driver](https://github.com/espressif/esp-idf/blob/v5.5.2/components/esp_driver_parlio/src/parlio_tx.c)、[RX driver](https://github.com/espressif/esp-idf/blob/v5.5.2/components/esp_driver_parlio/src/parlio_rx.c)。ローカルSDKは `D:/esp/v5.5.2`、ホストは修正版 `third_party/esp_driver_parlio` を利用。

## TRMで確定できる削減境界

§56.5.2 pp2817–2818：非連続clockではFIFO resetのCDC同期にAXI/Core両領域2clockが必要。非連続clock間のresetは一旦内部free-running clockへ切替える。起動時はAPB→GDMA→Coreのreset順序。フレーム間にはCore領域とasync FIFOのresetが要求され、毎フレームのAPB全体resetは要求されていない。

したがって、単に全resetを削除する案ではなく、初回unit生成時の全体初期化を維持し、通常応答ではRX Core/FIFOだけresetするopt-in実験が資料に沿う。RX Core/FIFO resetそのもの、動作clockでの同期、再設定・UPDATEを省略する根拠にはならない。

§56.5.2 p2818と§56.7.1 p2825：開始はclock OFF→START=1→clock ON、終了はclock OFF→START=0。既存flush末尾のSTART=0→clock OFFは資料順の逆で、変更候補では順序も修正する。

§56.7.2 pp2825–2826：TXはGDMA outlink設定後TX_READYを確認してからSTART、clock ON。SDK TX `parlio_tx.c:561` のFIFO-ready待ちはこれに対応する。待ちを無条件に削除してclockを先に出す案は不可。時間測定と安全なtimeout/error回収が先。

## RXだけresetし、所有TXを保持する条件

SDK `hal/.../parlio_ll.h:157–163` のRX Core resetは `reg_rst_en_parlio_rx` のみ。実機向け `soc/esp32p4/register/hw_ver1/soc/hp_sys_clkrst_struct.h:2390–2401` には全体・RX・TXの独立reset bit、`parl_io_struct.h:212–219` にはTX/RX独立FIFO reset bitがある。

全体APB resetでは停止中TXの設定も失うためTX unit保持と両立させない。RX-only方式では同一groupの所有TXがdisabled、`cur_trans==NULL`、inflight=0、PROGRESS/COMPLETE queue空、READY queueはdepth分回収、GDMA停止・IRQ回収済みであることをdriver内で検証する。READY queueが空であることは正常条件ではない。未知の所有者・別unitを許可しない。API戻り値だけでなく状態を確認し、reset中は排他的mutexを維持する。TX/RX両側のclock source/divider・sample phase・clock gate・bus width・FIFO counterが保持されることを測定する。これは次の実験条件であり、実機合格済みとは扱わない。

## 現在の費用と削減候補

- 初期版の毎frame TX/RX new/deleteはキュー・GDMA channel・割込み・descriptor・PM lock・payloadを再生成する。SDK common `parlio_common.c:33–34` はgroup初回取得時に全体reset、最後のrelease時 `:81–88` にbus clockを停止する。再利用自体は想定可能だがソフト状態を整合させる必要がある。現在ホストはRX unit/payloadとTX payload保持へ進行済み、TX unitは全APB resetとの整合のため再生成が残る。
- RX `main/dock_dma_rx.cpp:554–555,633–634` の全capacity zero+C2Mは毎回発生。exact EOF後の有効範囲だけを読むならzero省略候補。ただしCPUがdirtyにしたcache lineが後からDMA結果を上書きしない所有権規則が前提。無効受信の古いtailを有効と誤認させず、長→短→長、CANCEL、timeout後再開、連続patternで検証する。
- 修正版RX driver `:562–563` はdescriptorおよび受信payloadをM2C同期し、module `:586/:689` はさらに全capacityをM2C同期する。重複候補だが、EOF/descriptor callbackの実順・全descriptor完了・cache maintenance失敗の伝播を確認してから外す。cache同期全部を削除しない。TX SDK `:693`（修正版 `:723`）は送信payloadをC2M同期するので、別のmodule flushを足す場合は重複となる。
- 有限MEM受信は `main/dock_dma_rx.cpp:575` の `parlio_rx_unit_wait_all_done()` semaphore待ち。`:169` のbounded spin helperは別pathのoptional処理であり、有限MEMが常時busy-spinするという評価は誤り。TX FIFO-ready待ちは実在する。
- RX receive-done callback/descriptor callback/timeout callbackはISR。callback削除だけではGDMA内部管理を代替できない。debug snapshotやカウンタは最小化できるが、EOF count、受信length、error、semaphore完了は残す。direct mount finite受信ではinfinite/indirect用copyは走らない。
- 余分なRX clock/capture byteはprefix同期・pipeline drainも兼ねる。SDK/TRMにプロジェクト固有の余裕byte数の根拠はない。応答の最大prefix offsetとtrailerが確実にDMAへ到達する波形を確認するまで切り詰めない。
- `clk_gate_en` はvalid信号による出力clock gate（公式RX API flags説明）。Core clock enable、APB bus gate、GPIOへclockを接続する操作は別物。nominal frequencyから実際のGDMA/AXI clockやclock到達を決めつけない。

優先順はRX-only resetのopt-inと所有TX保持、重複cache/zero削減の別opt-in、ready待ち/ISR時間の計測。既存のCRC・EOF count・CANCEL・timeout回復・phase検証を維持して総transfer時間（準備/後処理込み）を比較する。
