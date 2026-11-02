# Tab5ホストソフト開発ガイド

更新日：2026-10-28。対象：ESP-IDF、MeOS、NOMMU LinuxでFPGAドライバや描画アプリを開発する担当者。
本書は現在の実装に対する参照資料であり、ピン・電源・wire仕様を変更しない。

## 1. 最初に読む資料と参照版

| 資料 | 役割 |
|---|---|
| 本書 | ホストの実装範囲、初期化、通信、エラー、描画・表示の契約 |
| [dock-gfx-v0](../fpga/link/DOCK_GFX_V0.md) | 現在実装したフレーム、タイミング、命令、状態の正本 |
| [共通C codec](../fpga/host/link_protocol.h) | フレーム生成・CRC・成功応答検査 |
| [Dock試験手順](Dockジャンパ_GFXテスト手順.md) | 配線、ビルド、コンソール操作、実機記録 |
| [検証記録](../fpga/validation/README.md) | 実行した試験と未検証範囲 |
| [デバイス構成](FPGAデバイス構成_ビットストリームと機能.md) | 将来のGFX／NPU／MEM／HDMI構成案。実装済みAPIの一覧ではない |

現行の開発版はキャリア`e5a386d`を基点とする`codex/dock-jumper-gfx`の作業ツリー。
この基点SHAだけには診断機能は入っていない。共有・採用時には、診断機能と本書を含むコミットSHAを固定する。
未コミットの検証内容は`fpga/validation/dock-gfx-2026-10-28.json`のソースハッシュで識別する。
ブランチ名や同名ファイルのコピーだけで互換性を判断しない。

ホスト側の参照記録には以下を残す。

```text
carrier_commit: 診断実装を含む採用コミットSHA（未確定なら未確定と記す）
protocol: dock-gfx-v0
board_profile: dock-jumper-v0
bitstream_top: tab5_dock_top または tab5_dock_gfx_top
bitstream_sha256: 実機に使用した.fsのSHA-256（未生成なら未生成）
codec_path: fpga/host/link_protocol.h
codec_sha256_lf: LF正規化したcodecのSHA-256
host_commit: ホスト実装のコミットSHA
validation: mock / RTL / build / hardware を区別した結果
```

## 2. 現在使えるものと各ホストの作業

| 項目 | 現状 |
|---|---|
| LINK診断 | ID、echo、反転、CRC付き固定8バイト、timeout／出力解除 |
| GFX診断 | 32×32 RGB565、色設定、全画面クリア、点、矩形、1画素読み戻し |
| 画像RAM | FPGA内部の2KiB。DDR3は使用しない |
| ESP-IDF | 独立診断ファームにGPIO転送、全画素比較、Tab5内蔵LCDへの表示要求を実装・ビルド済み |
| Linux／MeOS | 現行フレームを利用可能な設計だが、物理転送backendは未実装。GPIO・待ち処理・表示連携を各ホストで実装する |
| 合成・実機 | OSSの合成・配置配線・packは成功。Gowin EDA、合成後シミュレーション、外部I/Oタイミング、通信とLCDの実機確認は未実施 |
| 将来の機能 | PARLIO DMA、DDR3 READ/WRITE、COPY／BLIT／glyph、三角形統合、NPU実機、RAMdisk、能力問合せv1は未提供 |

照合した要求・実装の版：ESP-IDF `tab5-fpga-gpu d4d89e3`＋今回の診断作業ツリー、
Linux `cfc9a6e`、MeOS `7607793`、外部メモリ研究 `e84b59e`。
照合したREADME、要求資料、Device Treeと実装の所在は[試験手順の参照版一覧](Dockジャンパ_GFXテスト手順.md#参照版と適合性)に記録している。
Linuxの`tools/fpga-link/`はこの参照版に存在しない。旧資料のパスを実装済みbackendとして採用しない。

| ホストリポジトリ | ソフト側の担当と実装上の条件 |
|---|---|
| tab5-fpga-gpu | `bringup/tab5`が診断の実装例。`main/`の通常GPU LABとは別プロジェクト。既存GPU LABのFPGA backendは未実装のまま |
| tab5-meos-fpga | IO ownerを通じてピンを一括確保し、終了時に解放。FreeRTOSなしのためPARLIOは将来HAL/LL＋GDMAとMeOSの待ち処理で実装。ESP-IDFタスクAPIをそのまま移植しない |
| tab5-linux-fpga | Tab5用DTSとGPIOドライバを確認し、他ピンの出力を壊さないことを検証してからGPIO backendを追加。ユーザ空間／カーネルの役割を決め、期限付き待ちとキャンセルを実装する |
| esp32p4-linux-fpga-memory | 外部メモリの要求・評価を扱う。2KiB画像の成功は128MB DDR3、透過RAM拡張や通常swapの成立を示さない |

## 3. ホストドライバの構造

以下は推奨する責務分割。共通の公開transportライブラリや全OS共通関数はまだ提供していない。

```text
アプリ／描画・メモリサービス
    ↓ 排他・機能選択・画像の期待値比較
命令層（COLOR、CLEAR、RECT、READなど）
    ↓ 固定長要求／応答
共通codec（フレーム生成、CRC、sequence、応答データ検査）
    ↓
OS別transport（GPIO、期限付き待ち、方向切替、出力解除）
```

transportは「要求8バイトを渡すと応答8バイトまたは通信失敗を返す」境界にする。
部分応答を成功として返さず、全8バイトを読み終えるまでバッファを保持する。
命令層・アプリにはGPIO番号やDIR操作を持ち込まない。

排他は1トランザクションだけでなく、`COLOR → ORIGIN → RECT`など**共有状態を使う命令列全体**を保護する。
複数タスク／プロセスが色・原点を同時変更しないよう、単一所有サービスまたはセッション単位のmutexを使う。
現行RTLにセッション、キュー、並列ジョブ、重複要求の排除はない。
一枚の画像の整合性が必要な場合は、描画命令列から全画素の読出し完了まで同じ所有権を保ち、途中で別の描画を開始させない。

## 4. 起動・ARM・通信の契約

DockのSW0はFPGA側のARM入力。ESP-IDFコンソールの`arm dock-jumper-v0`は**Tab5側**のGPIO有効化で、別の操作。
ホストの`disarm`はD／CLK／DIRを入力に戻すだけで、SW0を操作せず、FPGAを必ずリセットする命令でもない。
FPGA状態を確実に初期化する場合はSW0 OFFまたはKey_0を使用し、再開時はCLEARからやり直す。

1. 起動時はリンクGPIOを勝手に出力化しない。配線・電圧・pin owner・競合を確認したプロファイルだけを有効にする。
2. 使用開始時にD0〜7、CLK、DIR、READYを入力としてGPIO機能へ切り替える。ESP-IDFの`gpio_set_direction`だけではIO_MUX切替を代替できない。
3. READYは常に入力、CLKはホストだけが駆動。CLK=0／DIR=0を出力ラッチへ設定してからCLK／DIRを出力化する。
4. READY=0を期限付きで確認し、DIR=0で200µs以上待ってからD線を出力化して要求を送る。
5. D線を全て入力へ戻し200µs以上待つ。DIR=1へ切り替え、さらに200µs以上待ってREADY=1を待つ。
6. CLKがLOWの間に1バイトを読み、その後CLKをHIGH→LOWにして次へ進める。8バイト分繰り返す。
7. DIR=0へ戻して200µs以上待ち、応答を検証する。次の要求までD線を入力に保つ。
8. 失敗・キャンセル・終了時は、先にD線を入力へ戻し、CLK／DIRのラッチをLOWにしてから入力へ戻す。

診断時のCLKはHIGH/LOW各100µs以上、送信データは立上がり前100µs以上安定させる。
ホストのREADY待ちは100ms、FPGAの無ストローブtimeoutも27MHzで100ms。
長いタスク停止／プリエンプトでFPGAがtimeoutする場合があるため、成功を仮定して途中バイトから再開しない。
READYは応答が存在する印であり、1画素ごとのIRQや転送FIFOの残容量ではない。

暫定GPIOはD0〜7=18,19,5,3,4,2,48,47、CLK=16、DIR=51、READY=45。
Dock ballと電源・配線条件は[配線表](Dockジャンパ試験_配線とFPGA構成_2026-10-28.md#ジャンパ配線表)を正とする。
GPIO2〜5のpad JTAGとGPIO19のUSB FS機能を同時使用しない。診断ファームのコンソールはUSB Serial/JTAG。
AUXは今回不使用。キャリア基板用のCSTや高速設定をDockへ流用しない。

## 5. codec・命令・エラー

`fpga/host/link_protocol.h`は単独で利用可能なCヘッダーで、OS APIに依存しない。
`link_make_request(q, op, seq, a, b)`が8バイトを生成し、`link_validate_response(r,q)`が成功応答を検査する。
後者はエラーstatusをすべてfalseとするため、詳細を表示したいドライバでは**応答のCRC・magic・長さ・sequenceを確認してからstatusを分類**する。
CRCが合わない応答のstatusを機器エラーとして信用しない。

| op（hex） | 命令 | 引数a,b | 成功結果r0,r1 |
|---|---|---|---|
| 01 | ID | 通常0,0 | ASCII `TP` |
| 02 | ECHO | 2バイト | a,b |
| 03 | INVERT | 2バイト | a XOR ff,b XOR ff |
| 10 | GFX_INFO | 通常0,0 | 幅32,高さ32 |
| 11 | COLOR | RGB565下位,上位 | a,b |
| 12 | CLEAR | 通常0,0 | 0,0 |
| 13 | PIXEL | x,y | a,b |
| 14 | READ | x,y | RGB565下位,上位 |
| 15 | ORIGIN | 矩形左上x,y | a,b |
| 16 | RECT | 幅,高さ | a,b |

フレームは要求`a5 op seq 02 a b crcLo crcHi`、応答`5a status seq 02 r0 r1 crcLo crcHi`。
CRCはCCITT-FALSE、先頭6バイト、末尾little endian。`seq`は0〜255でwrapする相関値。
1要求ずつ処理し、古い応答・異なるseq・不足バイト・余分なバイトを成功扱いしない。

| 結果 | ホストの扱い |
|---|---|
| status0 | 命令固有の結果も検査。READはCRCだけでなく期待画素との比較を呼出側で行う |
| status1 | 要求の形式／CRC不正。送信データと信号品質を調査 |
| status2 | 未知命令。GFX_INFOに対するstatus2はLINK版の可能性。GFXを無効扱いにする |
| status3 | 座標・寸法が範囲外。クリップやwrapを期待せず、呼出側の引数を修正 |
| status5 | 画像が未初期化。COLORとCLEARを実行し、CLEAR成功後に描画／読出しを再開 |
| CRC／seq／magic／長さ不正・timeout | transport失敗として出力解除。届いたか不明な更新命令を自動再送しない |

現行ESP-IDF診断はdevice statusを含めて失敗時にdisarmし、コンソールへ汎用の`link_or_compare_failed`を返す。
ソフト上の詳細分類は今後のドライバの責務で、既存コンソールがすべてのstatusを個別表示するわけではない。
失敗した更新命令が実行されたか不明な場合は、ホストを出力解除した後、SW0 OFFまたはKey_0でFPGAを初期化する。
入力状態を確認してFPGA側とホスト側を再ARMし、ID／GFX_INFOの確認から色・CLEAR・描画列を最初から再構成する。
ホストだけの再ARMでは部分要求・未読応答・処理中命令が消える保証はない。READY=0だけでも、部分要求や処理中命令がないことは証明できない。
リセット操作を使わずに復帰させる現行ESP-IDFの`arm`は、D入力・CLK/DIR LOWで150ms以上待ち、FPGAの100msの無ストローブtimeoutを経過させる。その後READY=0を最大100ms待ち、成功後だけarmedへ移る。HIGHのままなら`ready_stuck_high`として入力へ戻る。時刻・待機処理はホストCテスト済み、物理線とFPGAを接続した復帰は未実機検証。
これは27MHz・既定timeoutを前提とする。別bitstreamでtimeoutやクロックを変えるホストは待機値を再照合し、物理resetを使わない復帰を改めて検証する。待機でFPGAの色や画像が初期状態になるとは限らないので、復帰後の色・CLEAR・描画列の再実行は必要。
FPGAのreset／disarm、描画中timeoutでは色・原点・初期化状態を失う。通信待ちのtimeoutだけで完了済み画像が消えるとは限らないので、復帰処理は保持を仮定しない。

`ID=TP`は版や能力の識別子ではない。GFXは`GFX_INFO=32,32`でも確認するが、これも完全なABI交渉ではない。
採用したbitstream hashと実験プロトコル名をホスト側へ記録する。v1用の未定義命令を推測して送らない。

## 6. 最小描画と内蔵LCDの接続

以下は命令層の呼出順の例。`rpc`は各OSで実装する関数を表す疑似コードで、配布API名ではない。
各呼出しは、通信と命令の成功を確認し、失敗時は後続処理へ進まない。

```text
ID()                      -> "TP"
GFX_INFO()                -> 32,32
COLOR(0x00,0x00)          -> 黒
CLEAR()                   -> 全画素の初期化完了
COLOR(0x00,0xf8)          -> 赤 RGB565=f800
ORIGIN(1,2)
RECT(9,5)                 -> x=1..9、y=2..6を塗る
READ(1,2)                 -> 00,f8
READ(0,0)                 -> 00,00
```

画素は`uint16_t pixel = r0 | ((uint16_t)r1 << 8)`で復元する。
座標原点は左上、x右向き、y下向き、ホストの配列は`pixels[y * 32 + x]`。
COLORは初期白ffff、CLEARは現在色で全画素を塗って原点を0,0へ戻す。
ORIGINはCOLORと独立した保持値。PIXELは原点を変えず、RECTの寸法は1〜32、原点＋寸法が32以下。

内蔵LCDへはFPGA→ホストRAM→既存LCDドライバの経路を使う。
診断ではホストの受信バッファは32×32×2=2,048バイト。LCDドライバ自身のバッファは別に必要。
受信した全画素を比較してから、その**受信バッファ**を表示する。CPUで作った期待画像を表示へ渡して成功扱いしない。
非同期LCD APIでは、ドライバの消費完了前にバッファを書き換えたり解放したりしない。

ESP-IDFの実装例は`bringup/tab5/main/main.c`の`gfx_test()`と`gfx_lcd.c`。
全画素比較後にホスト側をdisarmし、LVGLで16倍の512×512へ表示する。
`readback_pass`は通信・画素比較、`lcd_submitted`はLCDへのソフト上の表示要求を表す。
`gfx_pass:true`には両方の成功が必要だが、パネルを目視確認した実機結果とは区別する。
GPU LABへの統合、640×360、30FPS、PPAによる拡大、double buffer／VSYNCは別作業。

## 7. 移植時の試験と更新手順

まず機器を接続せず、共通codecとPCモデルを使って実装を検証する。
期待値は`fpga/reference/link_protocol.py`、状態付きGFXモデルは`fpga/reference/gfx_bench.py`。

```text
cd <carrier>/fpga
python -m unittest discover -s gfx/tests -p "test_*.py"
python -m unittest discover -s host/tests -p "test_*.py"
python tools/dock_gfx_demo.py --mock
python tools/run_existing_rtl.py --require
```

最後のコマンドはIcarus／vvpが必要。C codec試験にはCコンパイラが必要で、未検出ならskipとなる。
mock成功、RTL成功、ホストbuild成功、実機成功を別々に記録する。
実機ではID→全256値のecho／反転→非対称図形の全画素比較→LCD表示の順で確認する。
異常系にはCRC、seq不一致、範囲外、未初期化、途中要求、部分読出し、キャンセル、timeout、resetを含める。

ESP-IDFでcodecを同期する場合:

```text
cd <tab5-fpga-gpu>
python bringup/sync_carrier_codec.py --carrier <carrier>
python bringup/sync_carrier_codec.py --carrier <carrier> --check
```

同期で更新するのはヘッダーと`bringup/carrier-codec.json`。GPIO／表示実装は自動移植しない。
Linux／MeOS用の自動同期ツールは未提供なので、同じ正本と版を参照し、コピーを使う場合はパス・SHA・変更履歴を残す。
変更の起点はキャリア側とし、フレーム／状態／タイミングを変える際は3ホストの要求を再照合する。
