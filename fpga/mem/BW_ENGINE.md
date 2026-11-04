# DDR3 帯域測定エンジン `mem_bw`（シミュレーションのみ）

設計元：`docs/DDR3_冷起動_複数seed_soak手順_2026-11-04.md` のB章。
**状態：RTLとシミュレーションのみ。`mem_top` には未接続、ホストABI未定義、合成・実機の結果なし。実機の帯域性能は何も主張しない。**

## ファイル
- `fpga/mem/rtl/mem_bw.v`（`mem_bw`、補助 `mem_bw_cnt` / `mem_bw_agen` / `mem_bw_ck`）
- `fpga/mem/tests/tb_mem_bw.v`、`fpga/mem/tests/run_bw_tests.py`

## 前提インターフェース（`mem_bist` と同じネイティブ面）
USERクロック領域、1:4・BL8、1コマンド＝128ビット1ビート、`cmd_ready` と `wr_data_rdy` は独立、読出しは順序どおりの `rd_data_valid`/`rd_data_end`、27ビットアプリアドレス（`APP_ROW_PAD` で行14ビットIPの配置）。書込みコマンドとデータの発行は `PAIRED_WRITE`（1：両readyが高いときだけ同時発行、0：独立・ずれ最大1ビート。回帰比較用）。

## パラメータ
| 名前 | 既定 | 意味 |
|---|---|---|
| TIMEOUT_CYCLES | 8100000 | 進行なし打切り（mem_bistと同じ） |
| TOTAL_TIMEOUT_CYCLES | 4860000000 | ジョブ総時間 |
| PAIRED_WRITE | 1 | 上記。混在モードは1のみ |
| CALIBRATION_SETTLE_CYCLES | 256 | 校正完了後の待ち |
| APP_ROW_PAD | 0 | mem_bistと同じアドレス配置 |
| MIX_LAG | 8 | 混在時、読出しコマンドは書込み発行数が読出し発行数よりこの値以上先行（または書込み完了）してから |

## 入力（CFG。startの前後数サイクル安定させる）
- `mode`：0 write_stream、1 read_stream、2 mixed（`mix_w` 書込み・`mix_r` 読出しの繰返し、各1以上）
- `pattern`：0 seq、1 bank_interleave、2 row_miss、3 lfsr、4 scatter
- `region_log2`（1..23、pattern 3/4のみ）、`beat_count`（1..2^23）、`base_byte`（16B整列、128MiB未満）、`seed`、`job_id`、`start`、`cancel`
- アドレス＝(p(i)×16＋base) mod 128MiB（128MiB末尾を越えると先頭へ折返す）。
  - seq：p=i。bank_interleave：bank=i[2:0]、列=i[9:3]、行=i[22:10]。row_miss：行=i[12:0]（16KiB刻み）、残り=i[22:13]。
  - lfsr：xorshift32の上位23ビットを region マスク（同一アドレスが重なりうる）。scatter：i×0x4F1BBD mod 2^23 を region マスク（奇数乗数のため beat_count ≤ 2^region_log2 なら重複なし。超過はerror 2）。
- 書込みデータ：seedから4レーンのxorshift32、1ビート/サイクル。ホットループ内の比較なし。

## 出力・カウンタ（すべてUSERクロック。ジョブ受理でクリア）
- `cnt_cycles`：最初のコマンド受理サイクルから最後のデータ受理（書込みデータ受理または読出しデータ受信）サイクルまで（両端含む）。
- `cnt_cmds`、`cnt_wbeats`、`cnt_rbeats`：受理コマンド数、書込みデータ受理ビート数、読出しデータ受信ビート数。
- `cnt_cmd_stall`、`cnt_wd_stall`：測定窓内で、エンジンがコマンド（書込みデータ）を出したいのに `cmd_ready`（`wr_data_rdy`）が低かったサイクル数（要求のないサイクルは数えない）。
- `lat_sum`、`lat_samples`、`lat_max`（32bit）：読出しレイテンシ（コマンド受理サイクルからデータ有効サイクルまで）。同時に1コマンドだけ計時するサンプリング。平均＝sum/samples。
- `ck_wr`、`ck_rd`、`ck_exp`（各128bit）：fold＝上位64^下位64、a＋=fold、b＝rotl1(b)^fold。`ck_exp` は同じ生成器から別途計算した期待値。`ck_wr_match`＝ck_wr==ck_exp、`ck_rd_match`＝ck_rd==ck_exp（読出し/混在ジョブでのみ意味あり）。検証は「write_streamの後に同一cfg・seedでread_stream」して `ck_rd_match` を見る。重複アドレスのある設定（lfsr等）ではmismatchになりうる。
- `error_code`：0正常、1未校正、2設定不正、3進行なし（コマンド/書込み側）、4読出し待ちで進行なし、5想定外/不正な読出しデータ、7cancel、8校正喪失、9総時間超過。`faulted` は mem_bist と同じくリセットまで保持。チェックサム不一致はエラーにしない（match旗で判定）。

## 帯域の計算
bytes＝(cnt_wbeats＋cnt_rbeats)×16、秒＝cnt_cycles÷99,562,500、帯域＝bytes÷秒。（理論上限は16B×99.5625MHz≈1.593GB/s。実測値ではない。）混在では往復の合計ビートで計算する。

## タイミング上の配慮
残量カウンタは ge1/ge2 を登録済みフラグで持ち、enableは「IPのreadyフロップ＆登録済みwant＆!cancel」の少数入力ANDのみ。アドレスは3段パイプ（パターン→base加算→出力）でコマンド受理ごとに進める。読出しデータ→チェックサムは入力捕捉・fold・累積の3段。タイムアウト比較は1サイクル前に登録。**合成・STAは未実施**で、ready→128bit書込みデータ更新（fanout）が最も怪しい箇所と見込むが未確認。

## 制約・未解決
- `mem_top` 未接続、ホストABI（コマンド番号、結果バンク、別signature）未定義。
- 混在モードはコマンドごとに1サイクルの空き（約2サイクル/コマンド）。ストリームのみ1ビート/サイクルを狙う設計。
- リフレッシュ模擬、行切替の遅延、`app_burst_number` の切替は未実装（シムは理想または単純なstall＋ジッタ）。
- 書込み後に時間をおく保持試験は未実装。
- 読出しレイテンシのサンプルは全体の一部。最大値は取りこぼしうる。
- region外へ折返すseq/他パターンは128MiBで折返す仕様（重複なし）。

## 実行したコマンドと結果（2026-11-04、シミュレーションのみ）
```
cd fpga/mem/tests
python run_bw_tests.py --iverilog /d/tools/oss-cad-suite/bin/iverilog.exe --vvp /d/tools/oss-cad-suite/bin/vvp.exe
```
iverilog `-g2012 -Wall`（timescale未指定の警告のみ）で、(PAIRED,ROWPAD)＝(1,0)、(0,0)、(1,1) の3構成を実行し、3つともPASS：
- `PASS mem_bw paired 20 scenario groups`、`PASS mem_bw unpaired 18 ...`、`PASS mem_bw paired rowpad 20 ...`
- 理想シム（全ready、読出しレイテンシ6）：write_stream N=4096 は cnt_cycles＝4096（1ビート/サイクル、オーバーヘッド0）、read_stream は 4102（N＋レイテンシ）、lat_max＝6、サンプル586。混在 N=200組（400コマンド）は805サイクル。
- stallシム（cmd_ready 4/5、wr_ready 3/7、読出し遅延ジッタ）：書込み1024ビートが2985サイクル（cmd_stall 597、wd_stall 1704）。stallカウンタはTB独立カウントと一致（PAIRED=1）。
- 検査項目：全パターンのアドレス列を独立関数と照合、シムのメモリ内容を独立データモデルと照合、チェックサム往復・1ビット破損検出・重複アドレス検出、混在での読出しが書込みに後続すること、エラー分類（1,2,3,4,5,7,8,9、リセット直後の出力停止）。
これらはRTLシミュレーションの結果であり、DDR3実機・合成後の性能を示さない。

## 2026-11-05 追記：配線・バースト・ストライド
状態更新：`mem_top` に `BW_ENABLE`（既定0、FS本体は従来とビット同一）で配線（`mem_bw_port.v`、LINK 0x60..0x6F）。パターン5（run_len/stride）と burst_log2（app_burst_number＝L-1、旧IPのみ・実機未検証）を追加。詳細・STA・実機手順は `docs/DDR3_帯域測定_実機手順_2026-11-05.md`。t4_bwイメージはSTA未達（-1.256ns）。
