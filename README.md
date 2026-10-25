# Tab5 × Tang Primer 20K 接続キャリア基板

M5Stack Tab5のM5-BusとTang Primer 20K Coreを接続する専用キャリア基板の設計リポジトリです。

## 状態

現行125×78mm版の回路図・PCB・少数PoC用製造データを作成済みです。実機通信・DDR3・HDMIは未検証です。

2026-10-25：現行版を保持して、廉価版A／B／Cの回路図・配線済みPCB・製造レビュー候補を追加しました。3案ともDRC違反0・未接続0と必須通信・電源の設計検査を通過しています。

- [廉価版3案の一覧と発注用フォルダ](variants/README.md)
- [3案の共通設計仕様](variants/DESIGN_SPEC.md)
- [廉価版レポートページ](site/lite-variants.html)

ソケットの在庫・治具・PCBA実装プレビュー等は製造業者との確認事項です。設計検査の通過を実機動作の保証とは扱いません。

## 設計の起点

[共通ハードウェア仕様・設計チェック項目](docs/ESP32P4_FPGA_共通ハード仕様.md)

- 初期通信：8bit PARLIOと制御線。将来16bit化を検討。
- 電源：外部約12VからTab5 HVINへ供給し、FPGAには独立した12V→5V DC-DCで供給。
- 共通GNDとし、Tab5の5VレールとFPGA用5Vは直結しない。
- DDR3はCore搭載のものを使用する。

GPIO割り当て・コネクタ・電源条件は暫定です。一次資料との照合、I/O電圧・競合・起動状態・逆給電の確認を行い、仕様のチェック項目を完了してから製造に進みます。

## 利用する2つの独立プロジェクト

- [Tab5 Linux本体・通信ドライバ](https://github.com/airpocket-soundman/tab5-linux-fpga)（[関連する外部メモリ研究計画](https://github.com/airpocket-soundman/esp32p4-linux-fpga-memory)も照合）
- [Tab5外付けGPU](https://github.com/airpocket-soundman/tab5-fpga-gpu)

本リポジトリは両者で使用する接続基板を扱います。ソフトウェアとFPGAビットストリームは各プロジェクトで管理し、同時動作は初期要件に含めません。
共通仕様の更新は本リポジトリを起点とし、各プロジェクトに収録した仕様へ反映してください。
