# Dock三角形タイル試験

## 行単位転送の実機結果（2026-11-03）

同一FPGA/Tab5ファーム、同じ5 DRAW・2段階の全色/深度照合で、単画素方式と行単位方式を各1回実行した。
両方とも色・深度各1,024画素を各段階で照合成功、`lcd_submitted:true`。実機のクロック設定は従来の最大5kHzのまま。

| 方式 | 読み戻し・照合時間 | DRAW往復合計 |
|---|---:|---:|
| 単画素 | 23,689,843µs | 29,523µs |
| 行32word | 3,829,592µs | 29,531µs |

読み戻し区間は約6.19倍短縮した。CPU照合とスケジューリングも含み、純粋な転送帯域やFPGA計算の高速化倍率ではない。
反復測定・ばらつき・GPU LAB全画面のFPS比較は未実施。終了後の`status`で`armed:false`を確認した。
FPGA UserCode `0x00009137`、Status `0x00006020`。内部27MHzで配置配線合格（推定Fmax47.17MHz）。
ROW pin-level410通信と従来単画素10,334通信が一致。CRC破損・途中切断・timeout・disarm/resetもPC試験済み。
[比較の生ログ・ハッシュ](../fpga/validation/triangle-row-2026-11-03.json)を参照。

2026-11-03。既存の整数ポリゴン描画と比較するため、32×32画素の色・深度タイルをFPGAの内部RAMに置く診断構成を追加する。
既存の三角形内外判定、整数深度補間、Z比較RTLを接続し、一度に1画素を処理する。
これは高速化の測定前に数値と転送を照合する段階であり、GPU LAB全体の高速化を示すものではない。

## 構成と範囲

- FPGA管理元は本リポジトリ。`fpga/platform/dock/tab5_dock_triangle_top.v`をtopとし、`tab5_dock_top`の`GFX_ENABLE=2`で構成する。
- `triangle_tile.v`が32×32のRGB565色RAMと16bit深度RAMを持つ。RAMはリセットせず、CLEAR完了までは読出しとDRAWを拒否する。
- 各DRAWはタイルの全1,024画素を走査する。バウンディングボックス走査、複数画素の並列処理、DDR3、HDMI、PARLIO DMAは含まない。
- 既存LINK（`GFX_ENABLE=0`）と矩形GFX診断（`GFX_ENABLE=1`）は別イメージのまま。三角形命令を未対応のイメージへ送った場合はstatus 2。
- Tab5側ではCPUの整数参照と全画素の色・深度を比較し、照合したFPGA読戻し画像を表示する。表示画像をCPU生成画像へ置き換えない。

## 数値規則

画面座標はsigned 16bitの12.4固定小数点raw値。画素中心は`(16*x+8,16*y+8)`。
三角形の向きを正規化し、top-left規則で辺上の画素を採用する。退化三角形は書込みなしで成功する。
画面外の頂点を受け付け、実際の書込みだけをタイル範囲に制限する。

深度はuint16で、大きい値ほど手前。重心座標の整数加重和を正の面積で除算し、floorした値を使用する。
新しい深度が既存深度より**厳密に大きい**場合だけ色・深度を書き込む。同じ深度では先に描いた色が残る。
CPU参照は`fpga/reference/game_gpu_reference.py`の`Frame.triangle()`、Tab5用の整数規則は`tab5-fpga-gpu/reference/cpp/integer_raster.hpp`を参照する。
従来floatポリゴンとの画素一致は要件にしない。

## 診断プロトコル

既存v0の8バイトフレーム、CRC-16/CCITT-FALSE、sequence照合、方向切替、ARMを維持する。
要求payloadは2バイト`a,b`。16bit値は`a`が下位、`b`が上位。全ホストOSから同じバイト列で使用できる。
通信速度は既存の低速条件（CLK最大5kHz）を維持する。新たなピンや電源は追加しない。

| opcode | 命令 | payload | 成功時の結果 |
|---|---|---|---|
| `0x20` | INFO | 予約（0,0） | `0x2020`（幅32、高さ32） |
| `0x21`〜`0x26` | 頂点座標設定 | 順にax, ay, bx, by, cx, cy | 設定した16bit raw値 |
| `0x27`〜`0x29` | 頂点深度設定 | 順にza, zb, zc | 設定したuint16値 |
| `0x2a` | 色設定 | RGB565 | 設定した色 |
| `0x2b` | CLEAR | 背景RGB565 | 0（色全画素を背景色、深度を0にする） |
| `0x2c` | DRAW | 必ず0,0 | Z比較を通過して書き込んだ画素数 |
| `0x2d` | READ_COLOR | x,y（各0〜31） | RGB565 |
| `0x2e` | READ_DEPTH | x,y（各0〜31） | uint16深度 |
| `0x2f` | TRI_ROW | 行番号0〜31, plane（0=色、1=深度） | 成功時だけ74バイトの行応答（下記） |

既存op1〜3のID、echo、反転は三角形イメージでも使用できる。
全10個のパラメータを一度ずつ設定し、CLEARを完了してからDRAWする。CLEARは設定パラメータを保持する。
設定不足またはCLEAR未完了はstatus 5、範囲外読出しまたはDRAWの予約payload違反はstatus 3。
CRC・フレーム不正は既存status 1、未対応命令はstatus 2。

リセット、ARM解除、実行中のリンクtimeoutで処理を破棄する。部分結果は利用できず、再開にはパラメータ再設定とCLEARが必要。
timeoutは100ms。描画完了前にはREADYを返さず、応答待ちの間もTab5はD線を入力に維持する。

## 試験順序

1. 独立CPU参照とRTLを照合する。最初は三角形1枚、次に逆向き・画面外頂点・退化形状・重なる三角形を扱う。
2. 色と深度を全1,024画素ずつ読み、CPU期待値と一致することを確認する。等深度では上書きしないことも確認する。
3. 不正CRC、未初期化、範囲外、実行中timeout、ARM解除と、その後の復帰を検証する。
4. Tang Primer 20K向けの合成・配置配線・packを行い、資源と内部27MHzのタイミング結果を保存する。
5. 実機へSRAM転送し、同じ試験をTab5から行う。通信・描画・読戻し・表示時間を混同しない。

ビルド入口は`fpga/builds/dock/build_oss.py triangle`。既存OSSツールのパスを指定して使用する。
PC試験成功、合成成功、SRAM書込み成功、実機全画素一致、LCD目視確認は別々の事実として記録する。
本書作成時点では統合作業中。最終的な実機結果は検証記録へ追記する。

## 2026-11-03 実機結果

三角形用イメージをSRAMへ、ESP-IDF診断ファームをTab5へ書き込み、`triangle`を実行した。
三角形1枚の段階と5 DRAW後の重なりシーンの段階で、それぞれ全1,024色画素・1,024深度がCPU整数参照と一致した。
`triangle_pass:true`、`lcd_submitted:true`。LCDはST7123として初期化成功。画面のユーザー目視確認は別途。
終了後`armed:false`。FPGAのDIP位置1はユーザー操作でON、ホストはdisarmしている。

CPU参照合計2,593µs、設定通信286,080µs、DRAW往復29,525µs、読み戻し・照合23,689,908µs。
各区間の範囲・処理内容が異なるため、これらからFPGAの演算速度やCPU比の高速化を主張しない。
特に5kHzの小さいフレームによる全画素読戻しが支配的であり、一括転送とリンク速度の改善が次の課題となる。

RTL9スイート成功。三角形統合のpin-level試験は10,334通信一致、C codec3テスト成功。
FPGAはMULT18X18 14/48、BSRAM 2/46。内部27MHz要求で配置配線合格（推定Fmax50.27MHz、外部I/O実測ではない）。
coverageの乗算を、signed16座標の差分signed17・積signed34・差signed35へ正確に制限し、DSP過剰使用を解消した。
[生ログ・ハッシュ・範囲を含む検証記録](../fpga/validation/triangle-tile-2026-11-03.json)を参照。

## ホスト要求・参照版

| 対象 | 確認HEAD | 今回の適合性と反映 |
|---|---|---|
| ESP-IDF `tab5-fpga-gpu` | `c7f3a8534fed1b38e8e1fdb8d532d73daf7dbff0` | CPU整数ラスタと既存GPIO診断を基に、三角形の設定・実行・全画素照合・LCD表示を追加中。変更は未コミットのため最終反映版は検証時に記録する。 |
| MeOS `tab5-meos-fpga` | `26c8082961b1152901475fb56bbb2e8be192a4da` | 既存LINK実通信は成功。三角形診断のホスト操作は未対応。同じv0転送を利用できるが、新命令の数値照合・CLI追加が別途必要。 |
| Linux `tab5-linux-fpga` | `c8d4b5689735ae9fc5c1401a9699c49ab2343a04` | mockのみ。三角形ABIはOS非依存だが、物理backendと三角形操作は未実装。 |
| 外部メモリ研究 `esp32p4-linux-fpga-memory` | `e84b59e8bf462ab1e2023f9e28f7915c152cbbdb` | 研究計画を照合。今回は内部RAMの診断であり、DDR3の明示アクセス要求やLinux透過RAM増設を実装するものではない。 |

新命令の管理元は本リポジトリの`fpga/host/link_protocol.h`と本書。
MeOS/Linuxへの反映は未実施。ホスト側で別のopcodeや数値規則を割り当てない。
ピン・電源・リンクの電気条件は変更しない。

## C codecのPC検証

`fpga/host/tests/test_codec.py`で、独立`TriangleTile`参照が生成した三角形の色・深度2,048読出しをC codecへ通す。
パラメータ設定、未初期化・範囲外・未知opcode、CLEAR後・重複描画、CRC不正、CRCを再計算した不正magic/status/sequence/length、DRAW書込数の上限も照合する。
DRAWの返却値は0〜1,024を受け付け、1,025と65,535は拒否する。READ_COLOR/READ_DEPTHの画素値そのものはcodecではなくホストの期待画像・深度と比較する。

2026-11-03に既存Zig C compiler（`D:/tmp/tab5-test-tools/ziglang/zig.exe cc`）で3テスト成功。
これはCのフレーム生成・応答受理の検証であり、FPGAの実機通信成功や描画速度の実測ではない。

## 行単位読戻しの追加（TRI_ROW）

2026-11-03。実機初回試験で支配的だった画素ごとの往復を減らすため、行単位の読戻しを追加する。
既存の8バイト要求を維持し、opcode `0x2f`、payload `a=row`、`b=plane`を送る。
成功応答だけ長さを74バイトとし、既存の全命令とTRI_ROWの失敗応答は8バイトを維持する。

| 位置 | 長さ | 内容 |
|---|---|---|
| 0〜5 | 6バイト | `5a 00 sequence 02 row plane` |
| 6〜7 | 2バイト | 上記6バイトのCRC-16/CCITT-FALSE、下位→上位 |
| 8〜71 | 64バイト | 対象行のx=0〜31の32word、各word下位→上位 |
| 72〜73 | 2バイト | 位置0〜5と8〜71を連結した70バイトのCRC、下位→上位 |

両CRCはpoly `0x1021`、init `0xffff`、非反転、xorout 0。末尾CRCはheader CRC（位置6〜7）を対象に含めない。
sequence・行番号・planeも末尾CRCへ含めるため、別の行やplaneのpayloadを有効なheaderに付け替えて受理しない。
FPGAは32wordを一度スナップショットしてからREADYを上げ、転送中のpayloadを固定する。
74バイト目を読み終えた後のCLKパルスでREADY/OEが下がる。

行番号32以上またはplane 2以上はstatus 3、CLEAR前はstatus 5、CRC不正はstatus 1の8バイト応答。
ホストは先に8バイトheaderを受け、status・sequence・row・plane・header CRCを確認してから成功時だけ残り66バイトを受ける。
失敗応答に対して66バイトを待たない。短い／途中で切れた成功応答は破棄し、74バイト未満の配列を固定長C validatorへ渡さない。

転送中のtimeoutまたはARM解除・リセットでリンク出力を停止する。
応答転送中timeoutではtileの内容自体を保持し、新しい要求で読み直せる。
スナップショット作成中timeout、ARM解除、リセットでレンダラがabortされた場合は初期化状態も失い、パラメータ再設定とCLEARが必要。

色・深度の全タイル読出しは、画素別の2,048要求から64要求へ減る。
要求と応答のバイト数合計は32,768から5,248へ減るが、これは通信形式上の値であり実測時間や演算高速化率ではない。
本追加はPC検証段階で、行単位転送の実機成功・所要時間は最終検証後に別途記録する。

### 行応答C codec検証

`fpga/host/tests/test_triangle_rows_codec.py`で、独立`TriangleTile`参照の全32行×2planeをCのheader/full-response validatorと照合した。
各成功応答の全74バイトを1バイトずつ改変して拒否を確認し、CRCを再計算したheaderのsequence・row・planeを変更しても、古い末尾CRCのままでは受理しないことを確認した。
未知opcode、範囲外、未初期化、要求CRC不正、途中で切れた成功応答も確認した。
固定長`link_validate_row_response()`には74バイトが揃った場合だけ渡し、8バイトの失敗応答や短い応答では呼ばない。

既存Zig C compilerで本テスト1件成功。これはC codecと独立参照の照合であり、実機試験結果ではない。
