# TX216MHz捕捉FIFO候補（2026-11-05）

独立候補 `tab5_dock_request_fifo_top` はrequestだけを216MHzで捕捉し、16byte FIFOから54MHz parserへ渡す。描画・reply serializer・DPB・ピン・コマンドABIは8877と同じ。REQUEST_CAPTURE_FIFO=0が既定で、既定のSYS54経路を維持する。既存0454明示FF候補はTX16/20安定化に至らなかったため別構成として保存する。

## データと制御

DATA2段16個とCLK3段は公式DFFC明示。STA後netlistでもDFFC16+3、DATA1段目fanoutは対応2段目Dのみ。Gray各5bit往復は合計20DFFC、1段目は2段目のみ。メモリだけがRAM16SDP4×2である。`audit_request_capture_fifo.py` と `capture-proof.json` が確認する。

header最終byte後、batch_startがreceivingへ反映されるまではreadyを落としてFIFO内にbodyを保持する。通常消費はfetch+consumeの2 SYS cycle、理想上限27MB/s。DIR0のparser/CRC/batch入力だけがready/validイベントへ切替わり、DIR1 replyの進行は従来SYS rise。overflowはstickyで、同期検出後parser/offer破棄、renderer/batch abort、OE/READY停止。自動fallbackやretryはしない。

overflow解除のARMはFPGAの物理arm_swから生成されるarm信号であり、Tab5 APIのsoft disarm/armではない。物理ARM OFF/ON、FPGA reset、またはSRAM再ロードで復旧する。物理ARMをON固定したままのsoft再ARMではoverflowを解除できない。

DIR1でFIFOセッションを即resetするので、最終要求byteがSYSへ消費される前にDIRを変えてはならない。ESP-IDF hostのTX完了末尾CRC保持2us (`dock_dma_tx.cpp`) と入力化後guard (`dock_gpu.cpp`) を前提とする。20MHzならFIFO最大17byte程度の滞留は理想約0.63us＋同期/捕捉遅延、ただしこれをアナログ保証や任意のbackpressure保証と解釈しない。パーサ停止が続く場合はoverflowで停止する。

## CDCとSTA

216/54MHzは同27MHz入力からの生成clockとして制約し、新しいclock group/false path/multicycleを追加していない。既存reply metadata30例外だけを維持。Grayは各write/read増分で1bitだけ変化し、対応ポインタの2段同期後にempty/full判定する。storageはwrite済みポインタが2段同期を通ってからSYSがreadする。消費後read pointerが2段同期で戻るまで同じslotは再使用しない。Gray同期や束データに対して「非同期だから安全」というwaiverは使用せず、実配置配線の通常setup/holdも確認する。外部DATA/CLKのアナログsetup/holdやメタステーブルMTBFを証明するものではない。

v1はsession_reset_nをwrite_eventへ直接ANDしたためSYS54 reset/ARM→216 CEにsetup12違反、最悪−0.496nsで不採用。v2は非同期killをsample_releaseのCLEARに保ち、機能writeenableは同期解除後sample_reset_nだけを使用する。v1ログ/FSは失敗記録として保存する。

v2: User5166、FS SHA256 `fe5b1d815861bc15056f508e97d09fb78089de390f13153b08f63feee5fcc38f`。
`fpga/build/request-fifo-v2/request_fifo/impl/pnr/request_fifo.fs`。
STA最小slack ns: setup0.753/hold0.074/recovery1.593/removal0.445、違反0。metadata30、reply-DPB共有clock監査合格。

## 検証

- 10/16/20MHz、各10位相×scalar/TRI64/R2-64/upload64=40ケース完全一致。最大1290byte、全640 staging words一致。
- 明示DFFC capture単体32位相×2仮想skew×5系列、412800byte一致、backpressure/停止HIGH/ARM/DIR/overflow sticky。
- bridge control: ready停止でheader8byteを保持、overflow時OE/READY停止とbatch_abort、DIRで復旧しない、物理ARM解除復旧、停止HIGHで偽byteなし。
- LINK有効42/無効27vector、FAST_REPLY有効、CRC/abort/参照画素一致。
- mapped gate nativeWire5vectorと画像読出し一致。理想PLL・SDFなし。
- 既定FIFO=0対0454 immutable snapshot: 10000回非同期DATA/CLK/reset比較一致。

## ホスト参照

ESP-IDF `67fa6728` のREADME/Project_B資料と通信実装を照合。対象は実験GFXのみで、他OSへ新ABIを要求しない。
MeOS `78274b46` のREADME/FPGA_CARRIER_REQUIREMENTSとdrivers/fpga/fpga_gpio.cを確認。現GPIO guard200us、要求資料に高速profile2us guardがありFIFO排出に十分な設計余裕を持つが、当候補の実機適合は未検証。
Linux `cfc9a6ec` のREADME/DEVELOPMENT_GOALS、研究repo `e84b59e8` の計画書を照合。Linux FPGA通信/PARLIO driverは未検証、現Linux本体にこのLINKを動かす実装/DT適合を確認できていない。将来driverは末尾byte保持/入力化後DIR guardとfailclosed復旧を満たす必要がある。DDRやLinuxメインRAMを変更しない。

実機書込・全画素比較・長時間maxbatchは親担当。STAとデジタル試験だけで16/20MHz実機成立を主張しない。
