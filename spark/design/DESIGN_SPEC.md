# Spark版設計仕様・要求照合

2026-10-26。ステータスは工学設計候補。応募適格なEasyEDAネイティブ設計、業者承認、製造完了とは区別する。

## 保存する計画

本作業の開始位置はmain0ff1502で、従来設計と廉価版の最新は別作業フォルダ `tab5-tang-primer20k-carrier-audit-pages` のc343f40。そこにはユーザーの未コミット差分もあるため編集しない。主125×78mm版とA/B/Cを読み取り、独立した `spark/` だけを追加する。既存READMEのユーザー差分を保持する。

元設計883ファイルのSHA-256を `../sources/preserved-design-hashes.json` に記録。回路・基板・ライブラリ・部品表・製造表・解析/生成コードを含み、元の作業フォルダの変更検出に使う。

## 要求元と版

| 要求元 | 参照版と確認物 | Spark版の適合方針・未実装 |
| --- | --- | --- |
| tab5-linux-fpga | c1cd5e47f9f07a164bc070b8defe36bb05682c6b。README、docs/DEVELOPMENT_GOALS.md、linux/dts/easystick-stamp-p4.dts、tools/fpga-link/transport.py等 | 双方向コマンド、CRC、分割READ/WRITE、通知線、DDR3全域試験に必要な物理接続を保持。transportはmock実装で、物理PARLIO/DMAドライバ・FPGAノードは未実装/未確定。Device TreeでGPIOを専有する実装は別途必要 |
| tab5-fpga-gpu | 3b1ace3d91c6305ec0e32378f8819fce208c2aa7。README、docs/Project_B_Tab5_FPGA_GPU.md、bringup/tab5/main/board_profile.h、bringup/rtl/link_bus_wrapper.v、main/app_main.cpp | GPIO割当と8bit往復経路を保持。BOARD_PROFILE_VERIFIED=0。wrapperは完成DDR3トップではない。CPU側画面とFPGA物理描画を区別。640×360RGB56530FPS・約13.8MB/s受信は目標 |
| esp32p4-linux-fpga-memory | e4aa69d09b2643d6f62fe686ef0f3284b109c541。README、docs/Project_A_P4_Linux_FPGA_Virtual_MMU.md | 明示的外部データ領域・演算オフロード研究。LinuxメインRAM増設とはしない。Linux本体の調査を代替しない |

LinuxとGPUは別ソフト/ビットストリーム。初期同時動作は不要。今回の追加は実装工程と独立版であり、関連3リポジトリの現行ソフトや共通仕様ファイルを無断で変更しない。量産前に各用途のピン制約・所有権とテスト用board profileをこの版へ明示的に合わせる必要がある。

## ハードウェア構成

| 項目 | Spark版 |
| --- | --- |
| 外形 | 125×78mm、x2..127/y1..79、元版の6取付穴 |
| 積層 | 4層1.6mm、連続したIn1GNDを維持。既存モデルはF.Cu35µm、In1まで0.2104mm。発注積層が異なるなら再評価 |
| 入力 | 安定化12Vのみ。バレルとCH224Kの12VUSB PD。24V不可 |
| Core5V | TPS5430、元のBourns15µH、R6=10k/R7=3.24k、220µF10TPB220M。節約目的の降格置換はしない |
| キャリア3V3 | TLV1117LV33DCYRを維持。汎用AMS1117へ置換しない。外部負荷は今回増やさない |
| Coreソケット | XDAP-4042044-20401/C22471982、別図面対応ランド。PCBA必須。CoreモジュールはBOM外 |
| 通信保護 | Ioffバススイッチ2個、両電源監視、BUS ARM初期開放を維持 |
| 初期直列抵抗 | 15信号680Ω/C23228。廉価版の保守的初期条件を採用するが、配線が変わる本版のSI検証を引き継ぎ済みとはしない |
| 初期転送条件 | 1MHz、DATA setup/hold各250ns以上、DIR切替500ns以上、弱駆動/SLOWから実測開始。40MHz動作の保証ではない |
| HDMI | 電気的追加目標。低背0402AC結合、独立接地型ESD、NPN反転HPD・100nF・Core直前10kを代替版から反映。D2は符号化後全シリアルbitの反転が必要。クロックは反転しない |
| 実装 | SMDと接続ソケット/映像コネクタはPCBA。THTは工程見積。未確定品を架空のLCSC番号で発注表へ入れない |

元のGPIO名を保持しても、Core端子は最新実設計のpin表に従う。共有仕様の初期仮ピン表や古いビットストリームをそのまま使わない。CoreCLKは専用GCLKT_1の52/K14を使う。

## 基板検証と完成品検証

回路ERC、PCB全severityDRC/未接続、モデル対実CADの端子・ネット一致、M5-Bus実物照合済みの向き、電源・隔離・ARM、HDMI導通、BOM/CPLの一致を確認する。元版の検査結果を新しい配線へコピーして合格扱いしない。新規配線のSI/PI、接点抵抗、過渡応答、筐体熱設計、実機性能は別検証。

初回はCore/Tab5を外して短絡・電源を確認し、電子負荷、Core単体DDR3、GPIO初期状態、低速往復CRC、DDR3経由の最小演算、速度上昇、HDMIの順で進める。JP1は検証前に閉じない。

## 応募する完成品

名称案：Tab5 FPGA Workstation。Tab5の既存筐体と追加キャリア保護カバーを一つのシステムとして組み、触れる操作と画面上の結果、実測結果を動画で示す。保護カバーは配線・Coreカード・電源回路を覆い、入力・HDMI・操作・通風・書込み経路を確保する。

筐体は基板外形だけで確定できない。Coreの高さ/挿抜軌跡、5.2mmソケット、M5-Bus嵌合、Tab5背面・電池・Keyboard、スペーサ、電源発熱、操作ボタン高さを実物と3Dで照合後に造形する。現段階で製造済み・干渉なしとは記録しない。
