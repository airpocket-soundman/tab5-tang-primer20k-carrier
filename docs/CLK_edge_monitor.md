# CLKエッジ数カウンタ v2（トラックJ2、診断専用）

2026-11-05。v1（USERCODE `0x4ABF`）の実機結果を受けた再設計。**RTLシミュレーションとGowin配置配線・STAのみ。v2は実機未検証。** ビルド記録は `fpga/validation/edge-counter-v2-2026-11-05/`。

## v1の実機結果と、なぜ再設計したか

連続RXの実機（85bac224基準、Jイメージ `0x4ABF`）：

| | 20MHz NEG（合格） | 25MHz POS（初フレームで失敗） |
|---|---|---|
| 窓数／異常窓／excess窓／deficit窓 | 720／720／720／0 | 12／12／12／0 |
| reject最大／runt最大 | 0／2 | ―／1 |
| HIGH最短／LOW最短（tick） | 5／3 | 2／2 |

**健全な点でも全窓が excess になった。** 原因：v1の窓は「オファー開始〜DIR下降」で、連続RXのホスト（P4）は応答が終わった後もISRリース／READY低下後のテール取り込みのためにクロックを出し続ける。そのテールの立上りを「受理立上りの総数」に入れて期待長と比べたため、正常でも必ず超過になった。さらに `pre`（serializer done前の受理立上り）は、serializerが期待個数目の受理立上りで終了する構造上、**構成上ほぼ期待長に等しく**、余分なエッジの指標にならない。

## v2の考え方

「応答のデータが有効な区間（VALID）」の内側だけで数え、テールを分ける。

- **窓（WINDOW）**：`fast_offer && dir` の立上り〜 raw DIR の立下り（安全タイムアウト約9.7ms）。ここでスナップショットを閉じる。
- **データ有効区間（VALID）**：窓の開始から、**`expect_edges` 個目の受理立上り**（16バイト応答なら16、タイル応答なら2066。これが serializer の最後のバイト）まで。それより早く serializer が done した（中断・エラー）場合はそこまで。
- **テール（TAIL）**：VALID終了後の窓内の立上り。ホストが出し続けるクロックで、**正常でも起きる。超過に数えない。**
- 応答前の訓練クロック：serializerの先頭8バイト（`c3`）は応答長に含まれ、1対1で数える。オファー前（`fast_offer && dir` 以前）のクロックは窓の外で数えない。

### VALID内で数えるもの（健全な応答は異常系がすべて0になる）

| 量 | 意味 |
|---|---|
| `pre`（accepted） | 受理立上り。serializerが消費したバイト数。VALIDが個数で完了すれば `expect` に一致 |
| `reject` | 5サンプルのクールダウン内に来た立上り（リンギング疑い。faultも立つ） |
| `drop` | fault後の同一窓内で捨てた立上り |
| `runt` | 2サンプル判定で捨てた1サンプルだけの突起 |
| `fall` | 受理した立下り |
| `min_high` / `min_low` | 修飾後信号のHIGH／LOWの最短区間（216MHz tick＝4.63ns） |
| `sp_min` / `sp_max` / `sp_jump` | 受理立上り間隔の最小／最大（tick）と、直前の間隔から4tick以上ずれた回数。**フィルタを通った余分／欠落エッジ**の検出用 |
| `ticks` | 最初の受理立上りからVALID終了までのtick数（平均周波数の確認用） |
| `first_pos` / `first_kind` | 最初の異常が出たときの受理立上り数（＝何バイト目の後か）と種類（1 reject／2 drop／3 runt／4 間隔ずれ）。`0xFFF`＝なし |

### TAILで数えるもの

`post`（テールの受理立上り）、`tail_noise`（テールのreject＋drop＋runt）。テールのノイズは応答データに影響しないので、`bad` や `excess` には入れない。

### 超過・不足の定義（54MHz側で算術）

- **excess（超過）= reject + drop**：VALID内で、フィルタが検出したが serializer が消費しなかった**余分な立上り**。受理立上りは構成上ちょうど期待長なので、受理数との差では余分が見えない。
- **deficit（不足）**：VALIDが個数で完了しなかった窓で、`expect − pre`（abort／fault／欠落エッジ）。完了した窓は 0。
- 履歴：超過のあった窓の数（idx19）、不足のあった窓の数（idx20）、最大超過（idx23）、最も早かった最初の異常位置（idx31）。クリアで消える。

**限界（誤読を避けるため）**：(1) 受理されて serializer が消費した余分なエッジは、reject にならない（間隔が5tick以上あるもの）。これは `sp_jump`／`sp_min`／`sp_max` で見る。ホストの視点では、その場合 FPGAが期待長に早く到達し、ホストの最後のクロックが `post` に入る。(2) 216MHz標本化より細いパルスは見えない／折り返す。アナログ測定ではない。(3) 間隔は255 tickで飽和（約0.85MHz以下）。(4) 端の±1：done同期（2サイクル）ではなくカウントでVALIDを閉じるので、VALID終了の直後（数tick）に来たrejectは TAIL側に入る。

## 構成

`link_bringup_filtered` に `EDGE_MONITOR_ENABLE`（既定0）。0なら従来と同一で、新opcodeは未対応（status 2）。1かつ `FAST_REPLY_ENABLE=1` のときだけ、216MHz側の `reply_edge_monitor` が `reply_clock_filter` の1tickストローブ（accept／reject／drop／runt／fall）と `link_reply_raw` の `done_index` を読む。`clean_clk`・`fault`・serializer入力には影響しない（既存出力は不変）。スナップショットは窓の終了時に確定し、トグル同期（2FF）でSYS側へ渡す。

イメージ：`platform/dock/tab5_dock_triangle54_filtered_edge_top.v`。ビルド：`builds/dock/build_filtered_edge_cdc.tcl`（Gowin Education 1.9.11.03、85bac224のCDC例外SDCを再利用）。

## 問合せ（ホスト）

`opcode 0x4c`（高速プレフィックス形式なのでホストは `0x80|0x4c = 0xCC` で送る）。要求 `a5 CC seq 02 idx 00 crc`。`idx > 33` または5バイト目≠0 は status 3。応答ペイロード（byte12/13）＝16bit値（下位が先）。`0x4d`（`0xCD`、引数 `5a a5`）＝履歴クリア（窓カウンタ・最悪値のみ。直近スナップショットは残る）。

| idx | 内容 |
|---|---|
| 0 | 識別 **`0xED02`**（v1は `0xED01`） |
| 1 | 閉じた窓の総数（飽和） |
| 2 | 異常窓の数（VALID内の reject/drop/runt/間隔ずれ/fault/serializer error/タイムアウト/飽和/VALID未完/done位置不一致） |
| 3 | 窓の通し番号（クリアで消えない） |
| 4 | 直近窓: VALID内の受理立上り（`pre`） |
| 5 | 直近窓: TAILの受理立上り（`post`） |
| 6/7/8 | 直近窓: VALID内の reject／drop／runt |
| 9 | 直近窓: VALID内の受理立下り数 |
| 10/11 | 直近窓: VALID内のHIGH／LOW最短（tick、`0xFF`＝未観測） |
| 12 | 直近窓の期待立上り数（16／82／2066） |
| 13 | serializerがdoneした時点のバイト番号 |
| 14 | フラグ: bit0 serializer done／bit1 serializer error／bit2 fault（VALID内）／bit3 タイムアウト閉じ／bit4 カウンタ飽和／bit5 エッジなし／**bit6 VALIDが個数で完了**／bit7 有効スナップショット |
| 15/16 | クリア以降の reject／runt の最大（VALID内） |
| 17/18 | クリア以降のHIGH／LOW最短 |
| 19 | クリア以降: 超過（reject+drop>0）のあった窓の数 |
| 20 | クリア以降: 不足（VALID未完）の窓の数 |
| **21** | 直近窓の超過数（reject+drop） |
| **22** | 直近窓の不足数（期待−受理、VALID未完のとき） |
| **23** | クリア以降の最大超過 |
| **24** | 直近窓の最初の異常位置（受理立上り数。`0xFFFF`＝なし） |
| **25** | 直近窓の最初の異常の種類（0なし／1 reject／2 drop／3 runt／4 間隔ずれ） |
| **26/27** | 直近窓: 受理立上り間隔の最小／最大（tick） |
| **28/29** | 直近窓: VALIDのtick数の下位16bit／上位8bit |
| **30** | 直近窓: 間隔ずれの回数 |
| **31** | クリア以降の最も早い最初の異常位置（`0xFFFF`＝なし） |
| **32** | 直近窓: TAILのnoise（reject+drop+runt） |
| **33** | クリア以降: serializerのdone位置と期待長が食い違った窓の数 |

太字はv2で追加。idx4〜14と6〜9、21〜30、32は「問合せの直前に閉じた窓」の値で、問合せ自体も16エッジの窓になる。**窓単位の値は調べたい窓の直後の1回しか意味がない。実験では集計（idx1, 2, 15〜20, 23, 31, 33）を使う。**

### 判定の流れ（実機）

1. `0xCD` でクリア → 同条件で描画（N枚）→ idx1（窓数）、2（異常窓）、19（超過窓）、20（不足窓）、23（最大超過）、31（最初の異常位置）、33。
2. **idx19＞0 または idx15＞0** → VALID内に近接／余分な立上りがある（仮説B：リンギング・クロストーク）。idx31が応答中の位置を示す。
3. **idx2＞0 だが idx19=0、idx20=0** → 間隔異常（受理された余分／欠落エッジ）か、runt。直近窓のidx30/26/27/25を直後に1回読む。
4. **idx19=0、idx20=0、idx2=0 で、本体CRCだけ外れる** → FPGAが見るクロックは健全。受信窓（P4側のサンプリング位相）の問題（仮説A）。
5. 健全点の対照（20MHz NEG等）で idx2/19/20 が0であることを先に確認する。テールは excess にならないので、v1のように「全窓が異常」にはならない。

## シミュレーション結果（`python fpga/link/tests/run_edge_monitor.py --iverilog <exe> --vvp <exe>`）

実機ではない。Icarus（sampler 216MHz、SYS 54MHz、ホストCLK 40MHz／10MHz）。

| シナリオ | 結果 |
|---|---|
| 正常16エッジ＋40本のアイドルクロック | `pre=16`、`post=40`、reject/drop/runt/tail=0、excess=0、deficit=0、フラグ `0xC1`、`first_pos=0xFFF`、間隔 5〜6 tick、history 0 |
| 正常タイル2066エッジ＋300本のアイドルクロック | `pre=2066`、`post=300`、done位置2065、ticks=11150、間隔 5〜6、`sp_jump=0`、異常0 |
| 近接する余分な立上り（6エッジ後） | `rej=1`、`excess=1`、`deficit=9`、`first_pos=7`、`first_kind=1`、fault旗、履歴に反映 |
| フィルタを通る余分なエッジ（10MHz、短い余分な1周期） | reject=0のまま `sp_jump=2`、`first_kind=4`、間隔 11〜22 tick、`pre=16`／`post=1` |
| 欠落エッジ（2倍長のギャップ） | `pre=15`、VALID未完、`deficit=1`、`sp_max=43`、`sp_jump=2`、`first_kind=4` |
| opcode経由の読出し（idx 0/2/19/20/21/22/23/31）、引数エラー、クリア、モニタ有無でのデータ経路 | 一致 |
| EDGE=0（既定） | 0x4c/0x4dはstatus 2（未対応）、通常通信は不変 |

既存RTL試験10スイート（bringup、dock_gfx、triangle_tile、triangle_rows、coverage、depth、fragment、mac、requant、dot）と、EDGE=0 の `tb_fastreply_control`（`PASS RAW control packets=41`）も合格。Gowin `LUT1` はシミュレーションでは `link/tests/lut1_model.v` の挙動モデルに置換（実機ビルドは本物のプリミティブ）。

## 未検証・リスク

- **実機未検証**：v2のカウンタが実機の信号で期待どおり動くかは未確認。まず合格点（20MHz NEG）で「異常窓0、超過0、不足0、`post`が数十〜数百」を確認すること（確認できなければ25MHzの結果は解釈しない）。
- **STA**：Gowin Education 1.9.11.03、85bac224のCDC例外SDC再利用で、setup違反0・hold違反0。**最小setup余裕は +0.048ns と薄い**（sampler216のFmax 218.3MHz）。USERCODE `0x0000D535`、FS SHA-256 `79d143a9fac5…7073`（全文は `fpga/validation/edge-counter-v2-2026-11-05/README.md`）。過去の試行はSTA違反（−0.104ns／−0.342ns）で、記録を残している。書込みには、記録のSHA-256と一致するFSを使うこと。
- CDC例外SDCは85bac224のものを再利用（`reply_edge_monitor` からSYS側への新しいトグル同期の経路は例外に入れていない。スナップショットは窓終了時に一度だけ書かれ、次の窓終了まで不変）。**ソース固定の証明は再実行していない。**
- 間隔ずれの閾値（4tick）は固定。分数分周（12.5MHz等）で健全でも間隔が交互に変わり得るが、標準の整数分周（5/8/10/16/20MHz）では健全時 `sp_jump=0`（シミュレーションは10MHz／40MHzで確認）。

## ホスト側の変更案（`tab5-fpga-gpu`、このブランチでは変更しない）

1. `link action=edge_read index=N` の許容範囲を `0..20` から **`0..33`** に広げる（応答は16bit、statusが3なら範囲外）。`edge_clear` は変更なし。
2. 判定ツールは識別 `0xED02` を確認し、idx0が `0xED01`（v1）ならv1の意味で扱う（互換）。
3. 比較スクリプトは、各条件の前に `edge_clear`、描画N枚、集計として idx1/2/19/20/23/31/33 を保存する（窓単位の idx21/22/24〜30/32 は直後の1回だけ）。25MHz失敗時の最初のフレームでは、失敗した窓の直後に idx24/25/26/27/30 を1回ずつ読むため、同じ失敗条件を項目数だけ繰り返す。
4. ホストが保持する「実際に出したクロック数」と `post`／`pre` を突き合わせる（ホストが `expect` 個の有効クロックのあとに出したテール本数＝`post` のはず。ずれは余分／欠落）。
