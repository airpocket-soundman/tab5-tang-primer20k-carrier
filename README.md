# Tab5 × Tang Primer 20K 接続キャリア基板

M5Stack Tab5のM5-BusとTang Primer 20K Coreを接続する専用キャリア基板の設計リポジトリです。

## 状態

フル125×78mmと廉価版A99×78mmの設計レビュー用データがあります。未製造・未実機検証です。

**実装仕様変更（2026-10-26）：** 片面SMTを優先し、主電源スイッチと旧FPGA専用停止SW3を省くr4へ変更しました。Tab5用J3はLCSC別購入・手はんだです。設計側PCB DRC違反・ERCエラーは両版とも0です。ERC警告はフル版163件、廉価版164件（ライブラリシンボル不一致160／161件と孤立ピンラベル3件）あります。EasyEDA反映・再計算完了のため見積もり用で、製造リリースは未完了です。[現在の仕様](spark/single-sided-r4/README.md)。

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

## FPGAデバイスと利用するホスト

本リポジトリは、キャリア基板と、その上で動くFPGAデバイス（全ビットストリーム）を一元管理します。ホストOSの各リポジトリは本リポジトリの仕様を参照してホスト側を開発します。[リポジトリ分担と参照ルール](docs/リポジトリ分担と参照ルール.md)、[FPGAデバイス構成](docs/FPGAデバイス構成_ビットストリームと機能.md)、[fpga/](fpga/README.md)を参照してください。

| リポジトリ | ホスト側の役割 |
|---|---|
| [tab5-linux-fpga](https://github.com/airpocket-soundman/tab5-linux-fpga) | NOMMU Linux本体、FPGA通信ドライバ、Device Tree、ユーザ空間ツール |
| [tab5-meos-fpga](https://github.com/airpocket-soundman/tab5-meos-fpga) | MeOSのFPGAドライバ（HAL/LL PARLIO）、GUI統合 |
| [tab5-fpga-gpu](https://github.com/airpocket-soundman/tab5-fpga-gpu) | ESP-IDFのホスト実装、ベンチマーク（GPU LAB）、モデル評価 |
| [esp32p4-linux-fpga-memory](https://github.com/airpocket-soundman/esp32p4-linux-fpga-memory) | Linux外部メモリ研究の計画・評価 |

FPGAの機能（GFX、NPU、HDMI、RAMdisk）はどのホストOSからも使う前提です。ビットストリームは機能別に分け、同時搭載は計測で問題がない組合せに限ります。

Linux側では双方向のコマンド・データ転送、128MB DDR3全域への分割読み書き、フロー制御・通知とエラー検出を支えます。描画用途では描画コマンド送信と完成フレーム受信を支え、640×360 RGB565・30FPSの目標に対して、フレーム本体だけで約13.8MB/sを要する受信経路を評価します。DMA対応と実効帯域は未検証であり、性能を保証するものではありません。

共通仕様・デバイス仕様の更新は本リポジトリを起点とし、ホスト側リポジトリに収録した仕様コピーへ反映してください。

## Spark応募用の独立フル機能版

従来設計とA/B/Cの計画を保持し、125×78mm・HDMI・USB PD付きの別版を [spark/](spark/README.md) で開発しています。KiCadで設計・解析してEasyEDAへ移植し、PCBAを優先、手はんだ品もLCSC調達を優先し、適合品をLCSCで調達できない場合のみ秋月電子へ集約します。[検証状況と残件](spark/design/VERIFICATION_STATUS.md)を確認してください。現行の製造データは見積・レビュー用です。
