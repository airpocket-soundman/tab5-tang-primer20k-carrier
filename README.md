# Tab5 × Tang Primer 20K 接続キャリア基板

M5Stack Tab5のM5-BusとTang Primer 20K Coreを接続する専用キャリア基板の設計リポジトリです。

## 状態

構想・設計前。共通仕様と確認項目を登録した段階で、回路図・PCB・製造データは未作成です。

## 設計の起点

[共通ハードウェア仕様・設計チェック項目](docs/ESP32P4_FPGA_共通ハード仕様.md)

- 初期通信：8bit PARLIOと制御線。将来16bit化を検討。
- 電源：外部約12VからTab5 HVINへ供給し、FPGAには独立した12V→5V DC-DCで供給。
- 共通GNDとし、Tab5の5VレールとFPGA用5Vは直結しない。
- DDR3はCore搭載のものを使用する。

GPIO割り当て・コネクタ・電源条件は暫定です。一次資料との照合、I/O電圧・競合・起動状態・逆給電の確認を行い、仕様のチェック項目を完了してから製造に進みます。

## 利用する2つの独立プロジェクト

- [Linux向け外部メモリ管理・演算補助](https://github.com/airpocket-soundman/esp32p4-linux-fpga-memory)
- [Tab5外付けGPU](https://github.com/airpocket-soundman/tab5-fpga-gpu)

本リポジトリは両者で使用する接続基板を扱います。ソフトウェアとFPGAビットストリームは各プロジェクトで管理し、同時動作は初期要件に含めません。
共通仕様の更新は本リポジトリを起点とし、各プロジェクトに収録した仕様へ反映してください。
