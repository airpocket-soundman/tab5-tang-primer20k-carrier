# Tab5 × Tang Primer 20K 接続キャリア基板

2026-11-08：FPGA単独推論の実験版4E30を追加。FPGA内RV32IMCが量子化・正規化等を処理し、共通INT8 MACが積和演算を担当する。Tab5/P4はモデル・画像の搬入と表示のみ。全RT-DETR649演算は実RV32 ISA試験で完走し、実機では14整数のCPU＋MAC試験に合格。**全モデルの実機完走・速度は未確認**。[自律実行仕様](docs/NPU_AUTONOMOUS_V1.md)、[ISA検証](docs/NPU_AUTONOMOUS_RV32_ISA_2026-11-08.md)を参照。Linux/MeOS loaderは未実装。

2026-11-07：NPU DDR診断版4E21で、YOLO S256の32MiB超え実行と、学習済みDeiT-tiny全12ブロック・74行列演算の実機実行を確認。Transformerの1000出力は同じP4の独立CPU整数計算と全ビット一致した。既存の積和回路を使い、ピン・通信コマンドの変更はない。非線形演算等はP4が担当し、Linux/MeOSへのホスト実装移植とSTA収束は未完了。[Transformer実機記録](docs/NPU_Transformer_実機検証_2026-11-07.md)、[DDR MatMul検証](docs/NPU_DDR_MatMul_検証_2026-11-07.md)を参照。

2026-11-06の保存点：GPU全8シーン/TX40・RX16検証記録とMEM DMA検証・復元資料をmainへ統合。[当時の現在地・全host適合範囲・整理方針](docs/INTEGRATION_2026-11-06.md)を参照。RX20、長時間soak、DDR付きGFXは未完了。


M5Stack Tab5のM5-BusとTang Primer 20K Coreを接続する専用キャリア基板の設計リポジトリです。

## 状態

2026-11-05のジャンパ接続GFX実機では、全8シーン×3負荷の640×360画像照合とFlow継続照合に合格。
[全8シーンの仕様・実績・失敗候補](docs/GFX全8シーン拡張_2026-11-05.md)を参照。
現行SLogic配線はCLK=D7／DIR=D6／READY=D4／DATA0～7=D15～D8で、
[9往復CRC照合による全チャンネル特定記録](fpga/validation/probe-map-complete-2026-11-05/manifest.json)を保存した。
これはジャンパ実機の結果であり、下記キャリア基板の製造・検証完了を意味しない。

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

Tab5側のソフト実装は[ホストソフト開発ガイド](docs/Tab5ホストソフト開発ガイド.md)を参照してください。

ジャンパ線で先に通信・描画を試す場合は[Dock接続とTab5内蔵LCDのGFX試験手順](docs/Dockジャンパ_GFXテスト手順.md)を参照。Dock用top、32×32 RGB565描画診断、読み戻し照合とホスト側表示経路を開発しています。RTL試験とOSSでの合成・配置配線・ビットストリーム生成は成功、Gowin EDAと実機は未検証です。

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
