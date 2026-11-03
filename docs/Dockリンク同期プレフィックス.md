# Dockリンクの任意同期プレフィックス

2026-11-03。ジャンパ配線の8bitパラレル接続でPARLIO DMA受信を評価したところ、
ESP32-P4の受信開始時に先頭データが欠ける現象を実機で確認した。
ヘッダの欠落をCPUで補う処理は入れず、FPGAが明示的な訓練データを先に送る任意拡張を追加する。
ピン・電源・方向制御・既存の論理コマンド・色/深度の数値規則は変更しない。
本書のPC試験は実機DMA成功や帯域の実証ではなく、実機結果はホストの検証記録へ分ける。

## 能力問合せ

新規LINK_CAPSはopcode4。通常の8byte要求を送り、成功応答のr0=8、r1=1を得る。
r0はプレフィックス8byte、r1はこのフレーミング拡張の版1を表す。
起動時はタグなしIDとタグなしCAPSを先に検証し、対応を確認した場合だけタグを使用する。
旧ビットストリームはCAPSをstatus2で拒否する。DMAを使わないホストは従来のコマンドを
そのまま使用でき、CAPSやタグを送る必要はない。

## タグ付き要求と応答

要求opcodeのbit7を1にするとタグ付き要求になる。FPGAは下位7bitを論理opcodeとして
従来のLINK/GFX/三角形/フラクタル命令へ渡す。要求CRCの計算対象にはbit7を含める。
タグだけを後から付け外ししてCRCを再計算しない要求は不正フレームとなる。

要求magic/length/CRCが正しいタグ付き要求だけ、FPGAは8byteのc3を先に返す。
その後に従来の完全な応答を連続して返す。プレフィックスはヘッダCRCにも行末CRCにも含めない。
タグのない要求は8byte、TRI_ROW成功だけ74byteという既存形式を維持する。
正しいタグ付き要求に対する失敗応答もプレフィックス8byte+失敗応答8byteになる。
要求自体のmagic/length/CRCが不正な場合はタグを信用せず、従来の8byte失敗応答を返す。

| 応答 | タグなし | 正しいタグ付き要求 |
|---|---:|---:|
| 通常成功/デバイスエラー | 8byte | c3×8 + 8byte =16byte |
| TRI_ROW成功 | 74byte | c3×8 + 74byte =82byte |
| 不正な要求フレーム | 8byte | 8byte（タグを採用しない） |

READY/OEはプレフィックスから最後の応答byteまで維持する。
TRI_ROWの画像・深度データの順番、header CRC、行末の連結CRCは従来どおり。
応答途中のtimeout/ARM解除/resetはバスを解放し、次の要求のタグ設定を持ち越さない。
bit7が0の既存命令の応答内容・長さは変更しない。以前未定義だったopcode4とbit7を本拡張に割り当てる。
旧テストのunknown4をCAPSへ、unknown255をタグなしunknown126へ更新し、タグ付きunknown255は新しい試験で検証する。

## DMAキャプチャからの抽出

C正本は`fpga/host/link_sync.h`の`link_sync_unwrap()`。
入力は実際に送ったタグ付き要求8byteと、その要求に対するDMAキャプチャ16/82byte。
要求自身のCRC、応答magic/status/sequence/length、命令ごとの返却値を検証し、
ROWではrow/planeと両CRCも検証する。応答候補の開始位置0..8を調べ、
完全な応答がちょうど1個見つかった場合だけ、その連続した8/74byteを出力へコピーする。
0個または複数個の候補、長さ違い、不正CRC・sequence・ROW metadataは拒否する。
失敗時に出力bufferとoffsetは変更しない。欠けたヘッダや画素を補わず、CPU描画へ切り替えない。

失われてよいのは訓練プレフィックスの先頭0..8byteまで。
ヘッダが1byteでも欠ければ、完全な応答がなく検証に失敗する。
末尾のキャプチャには、FPGAが応答を解放した後の未定義値が含まれ得るため、
検証済みの完全な応答以外を画像やコマンドの結果として扱わない。
FPGAがREADY/OEを解放した後のDIR=1アイドルクロックはFPGAが無視するが、
具体的なDMAのEOF/clock停止手順、内部クロックの初期化と失敗時disarmは各ホストで行う。

## 各ホストの要求と適合性

| 対象 | 確認版 | 適合性・今回の反映 |
|---|---|---|
| ESP-IDF tab5-fpga-gpu | f8e978f3127e15200942305dc6b5f2aa8bc4f937基点、codex/cpu-gpu-demo作業中 | Project B、GPIO/表示・GPU LAB経路と現在のDMA実験を照合。新codec/helperを同期し、タグなしID/CAPSの後にDMA専用のタグ付き要求へ移行する。最終ホスト版はホストのcarrier-codec記録と検証に固定する。 |
| MeOS tab5-meos-fpga | 26c8082961b1152901475fb56bbb2e8be192a4da | README・FPGA_CARRIER_REQUIREMENTS・fpga_link.h/GFX CLIを確認。現在のタグなしLINK/GFX操作は互換。タグ付きDMAとCAPSは未実装、今回ソース反映なし。利用時は新codecと能力判定の追加が必要。 |
| Linux tab5-linux-fpga | cfc9a6ecf7daa4c5e3decbe3885b22c2bd2f4cd1 | README・DEVELOPMENT_GOALS・Tab5 Device Tree/通信実装を確認。物理FPGA/DMA backendは未実装。既存DTと物理ピンの変更は不要。新フレーミングを使う場合だけ能力判定とcodecを実装する。 |
| 外部メモリ研究 esp32p4-linux-fpga-memory | e4aa69d09b2643d6f62fe686ef0f3284b109c541 | READMEと計画書のDDR3明示アクセス・退避/復元要求を照合。今回はリンク受信の任意拡張であり、DDR3や透過Linux RAM増設は実装しない。研究側の確認でLinux本体の確認を代替していない。ソース反映なし。 |

FPGA実装・共通codec・命令仕様の正本はキャリア側。
NPU/MEMとの混載や周波数上限の引上げをこの仕様から推定しない。

## PC検証

タグ付きID/echo/invert/CAPS、三角形、フラクタル、全32行×色/深度を含む178通信を
独立PythonオラクルとDockピン経由RTLで照合した。16/82byteの最終byteまでREADY/OEを保ち、
timeout/disarm/resetと通常フレームへの切替も検証した。
C helperは3,162ケースを確認し、プレフィックスの先頭0..8byte欠落、全応答byteの破損、
不正request CRC・sequence・ROW metadata、短い/長いキャプチャ、複数の有効候補を含む。
複数候補は通常フレーム2個と、重なり合うROWフレーム2個の両方を構成して拒否した。

タグなしのLINK583ベクタ、513パターン/エラー/timeout試験、三角形単画素10,334通信、
ROW410通信、フラクタル523通信、bbox2,432通信も回帰検証する。
ソースハッシュと最終結果は[link-sync-rtl-2026-11-03.json](../fpga/validation/link-sync-rtl-2026-11-03.json)へ記録する。
