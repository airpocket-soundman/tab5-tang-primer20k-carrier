# dock-gfx-v0 実験プロトコル

2026-10-28。GPIOの低速8bitパラレルで動作させる診断用。将来のDDR3／DMA用v1とは別。
既存bringup-v0のop1=ID、2=echo、3=反転を維持し、`GFX_ENABLE=1`のビットストリームだけ以下を実装する。
LINK版（GFX_ENABLE=0）でこれらを送ると未知opcodeのstatus2を返す。

## フレームとバス

要求8バイトは`a5 op seq 02 a b crcLo crcHi`、応答は`5a status seq 02 r0 r1 crcLo crcHi`。
CRC対象は先頭6バイト、CRC-16/CCITT-FALSE（poly1021、initffff、refin/out=false、xorout0）、CRC末尾はlittle endian。
RGB565はR[15:11]、G[10:5]、B[4:0]、転送は下位バイトが先。画像原点は左上、x右向き、y下向き。

CLKは常にホストが駆動し、最大5kHz（HIGH/LOW各100µs以上）。送信データはCLK立上がりより100µs前に確定させる。
FPGAは27MHzのsys_clkでCLK／DIRを同期し、立上がりを検出してデータを取る。データ8本は一括同期しないため、この安定時間を必須とする。

1. DIR=0／CLK=0、READY=0で要求を8バイト送る。
2. ホストはD線を全て入力にして200µs待ち、DIR=1へ切り替え、さらに200µs待つ。
3. READY=1（有効な応答の存在。FIFO creditではない）を待つ。
4. CLK=0中にD線を読み、その後CLKをパルスして次バイトへ進める。8バイト後READYとOEが下がる。
5. DIR=0へ戻し200µs待つ。次の要求までD線を駆動しない。

READYが1になるまでは、GFX処理が続いている場合がある。ホストは100msの期限内で待つ。
FPGAも27MHz×2,700,000サイクルの無ストローブで要求／応答を破棄する。
描画の途中で期限切れになった場合は描画状態もリセットし、CLEARのやり直しを必要にする。
応答待ち／部分送信の通信期限切れだけでは完了済み画像の内容は変えない。

## 命令

| op（hex） | 命令 | a,b | 成功時r0,r1 |
|---|---|---|---|
| 10 | INFO | 任意（通常0,0） | 幅32、高さ32 |
| 11 | COLOR | RGB565下位、上位 | a,b |
| 12 | CLEAR | 任意（通常0,0） | 0,0 |
| 13 | PIXEL | x,y | a,b |
| 14 | READ | x,y | 画素の下位、上位 |
| 15 | ORIGIN | 矩形左上x,y | a,b |
| 16 | RECT | 幅、高さ | a,b |

COLORの初期値は白ffff。CLEARは現在色で全1,024画素を埋め、ORIGINを0,0へ戻す。
ORIGINはCOLORと別に保持し、RECTは保存した原点から幅×高さを現在色で塗る。
PIXELはORIGINを変更しない。矩形のクリップは行わず、はみ出す要求を拒否する。
同時実行や要求のパイプライン投入はなく、1要求ずつ応答を読み終えてから次を送る。
再送を自動実行しない。seqはuint8の相関値で、重複排除やexactly-onceは提供しない。

statusは0=成功、1=形式／CRC不正、2=未知命令、3=範囲外、5=未初期化。
範囲チェックはx,y<32、幅／高さ1〜32、原点+寸法<=32。範囲不正は未初期化より先に判定する。
エラー応答のr0,r1は0,0で、操作による色・原点・画像への変更は行わない。

RAMには電源投入値の保証がないため、完了したCLEARより前のPIXEL／READ／RECTはstatus5。
ORIGINとCOLORはCLEAR前でも指定できる。reset／disarmと描画中断で初期状態に戻る。
タイムアウト・disarm中断後の途中画像は使わず、再ARM後にCLEARする。
成功応答は書込みが終わってから返る。状態を変更する命令もCRC検査が通るまで実行しない。

## ホスト適合

フレームはESP-IDF、Linux、MeOSから共用可能。OS固有のタイマ／GPIO／DMA処理は別実装。
今回はESP-IDF診断ファームとPC oracle、RTL試験を追加した。Linux／MeOS物理通信、PARLIO、DDR3の実装は含めない。
`fpga/host/link_protocol.h`がC codecの正本、`reference/gfx_bench.py`は期待値用の状態モデル。
