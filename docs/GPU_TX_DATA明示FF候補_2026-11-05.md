# TX DATA明示FF候補（2026-11-05）

現行8877/94F0のRTL上の2段DATAレジスタは、Gowin配置配線後にはRAM16S4×2とアドレス制御FFへ推論されていた。論理シミュレーションの2段遅延と、物理的な2段FF構造は区別する。これが実機TX16MHz不安定の原因であるとは未実証。

独立候補 `tab5_dock_request_ff_top` は8877のFAST_FILTER_SYNC=1、REGISTER_OUTPUT=0、RAW_BYPASS=0、FRAME_TIMING=0を維持し、REQUEST_DATA_FF=1だけを変更する。共通モジュールの既定値は0。PIPELINE=1かつFF=1で公式DFFCを16個使用する。DFFCは立上りクロック・非同期active-high CLEAR、DFFRは同期RESETなので使用していない。ピン、クロック、コマンドABIは変更なし。

## 構成と証拠

- ビルド: `fpga/builds/dock/build_request_ff.tcl`、公式Education 1.9.11.03。
- FS: `fpga/build/request-ff-v1/request_ff/impl/pnr/request_ff.fs`、UserCode0454。
- SHA256: `939850a87acf1a7e102c056cd9754ecf782eff04f486c3cab66fc6045dbbfeca`。
- mapped: DFFC16、request経路RAM16S4なし、各stage0のQは対応stage1のDだけに接続。両stageはcore_clk。
- STA最小slack ns: setup2.100、hold0.074、recovery3.028、removal0.954。4種違反0。
- 既存metadata first-stage30例外のみ。新しいfalse path/multicycle/clock groupsなし。serializer/DPB共有clock141endpoint監査合格。
- `fpga/build/request-ff-v1/audit.json`、`metadata-proof.json`、`request-data-proof.json`に根拠。

## 論理検証

- all-scenes LINK: 有効42/無効27vector、CRC、abort、トレーラ検証前書込禁止、画素参照一致。
- 配置配線後functional gate: native Wire初タイル5vector（画像読出し含む）一致。理想PLL・SDFなしであり物理タイミング検証ではない。
- TX10/16/20MHz各10 SYS位相×scalar/TRI64/R2-64/upload64=40ケース全合格。最大1290byteと全640 staging word一致。DATAは立下り側更新の理想信号、メタステーブルをモデル化していない。
- default0対FF1の10000回非同期DATA/CLK変化とresetパルスで観測出力・内部request_data一致。

実機書込と画像一致・最大batch長時間試験は親担当。上記結果のみで16/20MHz達成やジャンパ線限界は主張しない。入力DATAとCLKの相対スキュー、量子化、アナログ品質、MTBFは未保証。

## 保存波形の補足

200MS/sの再確認16MHz captureはCLK12/13sample、最小HIGH25ns。DATA変化は主に立下り付近で、余分なSYS遅延をCLK検出へ足すと次byteを取り込む窓が増える可能性があり、現時点で推奨しない。初回16MHz/200MS表記captureはCLK6/7sampleかつGPIO周期も100MS相当で時間軸不整合として除外。

長captureは30M予定に対し18,350,078sampleでUSB停止し完全性FAIL。含まれた41long packetは固定−15..+20nsの読取りoffsetで全CRC正当。取得範囲外のtimeout原因を判定できない。100MS/200MS捕捉の正常CRCはFPGA内部サンプル一致の証明ではない。
