# Tab5 × Tang Primer 20K 接続キャリア基板

M5Stack Tab5のM5-BusとTang Primer 20K Coreを接続する専用キャリア基板の設計リポジトリです。

## 状態

フル125×78mmと廉価版A99×78mmの設計レビュー用データがあります。未製造・未実機検証です。

**主電源仕様の訂正（2026-10-26）：** 必要なのは押すごとにON/OFFを保持する外部給電の主電源です。既存SW3のFPGA専用停止回路は要求と異なります。現行PCB・EasyEDAデータ・製造資料は旧回路の記録であり、新仕様の発注用データとして使用できません。[改訂状況](spark/main-power-r2/README.md)を参照してください。

## 保持している従来版

125×78mmの従来版と廉価版A/B/Cは保存しています。既存の製造・解析記録は各版のものです。Spark主電源改訂の検証結果ではありません。

- [廉価版3案の一覧](variants/README.md)
- [3案の共通設計仕様](variants/DESIGN_SPEC.md)
- [廉価版レポート](site/lite-variants.html)

## 設計の起点

[共通ハードウェア仕様・設計チェック項目](docs/ESP32P4_FPGA_共通ハード仕様.md)

- 初期通信：8bit PARLIOと制御線。将来16bit化を検討。
- 電源：外部約12VからTab5 HVINへ供給し、FPGAには独立した12V→5V DC-DCで供給。
- 共通GNDとし、Tab5の5VレールとFPGA用5Vは直結しない。
- DDR3はCore搭載のものを使用する。

GPIO割り当て・コネクタ・電源条件は暫定です。一次資料との照合、I/O電圧・競合・起動状態・逆給電の確認を行い、仕様のチェック項目を完了してから製造に進みます。

## 利用する2つの独立プロジェクト

- [Tab5 Linux本体・FPGA通信ドライバ](https://github.com/airpocket-soundman/tab5-linux-fpga)（研究計画・FPGA回路・評価は [esp32p4-linux-fpga-memory](https://github.com/airpocket-soundman/esp32p4-linux-fpga-memory)）
- [Tab5外付けGPU](https://github.com/airpocket-soundman/tab5-fpga-gpu)

本プロジェクトの目的は、上記2プロジェクトの要求を満たす共通キャリア基板を設計・検証することです。作業開始時と仕様変更前には、両リポジトリの要求資料と関連実装を確認することを前提とします。

Linux側では双方向のコマンド・データ転送、128MB DDR3全域への分割読み書き、フロー制御・通知とエラー検出を支えます。GPU側では描画コマンド送信と完成フレーム受信を支え、640×360 RGB565・30FPSの目標に対して、フレーム本体だけで約13.8MB/sを要する受信経路を評価します。DMA対応と実効帯域は未検証であり、性能を保証するものではありません。

本リポジトリは両者で使用する接続基板を扱います。ソフトウェアとFPGAビットストリームは各プロジェクトで管理し、同時動作は初期要件に含めません。
共通仕様の更新は本リポジトリを起点とし、各プロジェクトに収録した仕様へ反映してください。

## Spark応募用の独立フル機能版

従来設計とA/B/Cの計画を保持し、125×78mm・HDMI・USB PD付きの別版を [spark/](spark/README.md) で開発しています。KiCadで設計・解析してEasyEDAへ移植し、PCBAを優先、手はんだ品もLCSC調達を優先し、適合品をLCSCで調達できない場合のみ秋月電子へ集約します。[検証状況と残件](spark/design/VERIFICATION_STATUS.md)を確認してください。現行の製造データは見積・レビュー用です。
