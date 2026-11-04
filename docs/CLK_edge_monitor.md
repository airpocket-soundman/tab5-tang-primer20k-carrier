# CLKエッジ数カウンタ（トラックJ、診断専用）

2026-11-04。実機に触れないオフライン作業の成果。**RTLシミュレーションと `yosys synth_gowin` の通過のみ。Gowin配置配線・タイミング解析・実機書込みは未実施で、実機での動作は未検証。**

## 目的

25MHz以上のDMA RX失敗が「受信窓のずれ（仮説A）」か「FPGAが数える余分なCLKエッジ（仮説B）」かを、FPGA側で応答ごとに数えて切り分ける（ホスト側 `tab5-fpga-gpu` track-c `docs/dma-25mhz-isolation-plan.md` の実験4）。

- 期待値（16バイト応答なら16、2066バイトのタイル応答なら2066）より多く受理されていれば仮説B。
- 期待値と一致し、本体だけ誤るなら仮説A。
- 注意: 216MHz（周期4.63ns）の標本化なので、これより短いパルスは見えない／折り返す。アナログ測定ではない。**CLKの余分なエッジ**が標本化に載る程度の幅で来た場合のみ数えられる。

## 構成

`link_bringup_filtered` に `EDGE_MONITOR_ENABLE`（既定0）を追加。0なら従来と同一（新opcodeは未対応＝status 2）。1かつ `FAST_REPLY_ENABLE=1` のときだけ、診断用の `reply_edge_monitor`（216MHz側）が `reply_clock_filter` の1tickストローブを数える。`clean_clk`・`fault`・シリアライザ入力には一切影響しない（既存出力は不変）。

イメージ: `platform/dock/tab5_dock_triangle54_filtered_edge_top.v`（`filtered_top` と同ピン・同構成にEDGE=1を足しただけ）。ビルド: `builds/dock/build_filtered_edge.tcl`（Gowin IDE。**未実行**）。

## 問合せ

`opcode 0x4c`（応答は通常の高速プレフィックス形式なので、ホストは `0x80 | 0x4c = 0xCC` で送る。他の高速応答opcodeと同じ規則）。

- 要求 `a5 CC seq 02 idx 00 crc`。`idx > 18` または 5バイト目≠0 は status 3。
- 応答のペイロード（byte12/13）= 16bit値（下位が先）。

`opcode 0x4d` = 履歴クリア（`0xCD`、引数 `5a a5` 以外は status 3）。窓カウンタ・最悪値のみクリア。直近スナップショットは残る。

| idx | 内容 |
|---|---|
| 0 | 識別 `0xED01` |
| 1 | 閉じた応答窓の総数（飽和） |
| 2 | 異常窓の数（reject/drop/runt/fault/タイムアウト/飽和/doneなしのいずれか） |
| 3 | 窓の通し番号（クリアでは消えない、窓が閉じるたび+1） |
| 4 | 直近窓: serializer done より前に受理されたCLK立上り数（pre） |
| 5 | 直近窓: done以降に受理された立上り数（post） |
| 6 | 直近窓: reject（5サンプル未満の間隔で来た立上り＝リンギング疑い。faultも立つ） |
| 7 | 直近窓: drop（fault後に捨てた立上り） |
| 8 | 直近窓: runt（1サンプルだけの突起） |
| 9 | 直近窓: 受理した立下り数 |
| 10/11 | 直近窓: HIGH／LOWの最短区間（216MHz tick、0xFF=未観測） |
| 12 | 直近窓の期待エッジ数（16／82／2066） |
| 13 | serializerがdoneした時点のバイト番号 |
| 14 | フラグ: bit0 done / bit1 serializer error / bit2 filter fault / bit3 タイムアウト閉じ / bit4 カウンタ飽和 / bit5 エッジ無し / bit7 有効スナップショット |
| 15/16 | クリア以降のreject／runtの最大値 |
| 17/18 | クリア以降のHIGH／LOW最短区間 |

**読み方の注意:** 値は「問合せの直前に閉じた窓」の結果。問合せ自体も16エッジの応答窓なので、調べたい窓の直後に1回だけ問い合わせる（連続で複数idxを読むと2回目以降は問合せ窓の値になる。長い窓の複数項目を見たいときは、同じ負荷を繰り返して項目ごとに1回ずつ読む）。

判定: `pre+post == idx12` かつ reject/drop/runt==0 かつ bit0=1 → CLKは健全。`pre+post > idx12`、または reject>0 → 仮説B（余分／近接エッジ）。`pre+post == idx12` なのに本体CRCだけ外れる → 仮説A（受信窓）。

## シミュレーション結果

`python fpga/link/tests/run_edge_monitor.py --iverilog <iverilog.exe> --vvp <vvp.exe>`（OSS CAD Suiteの `bin` と `lib` をPATHに入れる。`vvp` が DLL 不足で終了コード0xC0000135になる場合は `lib` が必要）。

- EDGE=0: 0x4c/0x4d が status 2、通常通信は不変。
- EDGE=1: 16エッジ応答と2066エッジのタイル応答がそれぞれ正確に数えられる（pre+post=16／2066、reject=0、done_index=2065）、引数エラー、クリア、近接エッジ注入でfaultとreject、1nsの突起が立上りにならないこと、DIR中断時のdoneなし、モニタ有無でデータ経路が変わらないこと。
- 既存 `tb_filteredreply_control`（EDGE=0）も合格。シミュレーションでは Gowin の `LUT1` を `link/tests/lut1_model.v` の挙動モデルに置換している（実機ビルドは本物のプリミティブ）。

## 未検証・リスク

- 配置配線・STAは未実施。モニタは216MHz側のカウンタ（約100レジスタ）を足すので、タイミング余裕と収容は実ビルドで要確認。
- SYS（54MHz）側へのスナップショット渡しはトグル同期で、スナップショットは次の窓終了まで不変だが、CDC例外制約（`.sdc`）は追加していない。ビルド時に監査が必要。
- 実機試験はメインセッションが1変数ずつ行う（末尾の手順案）。

## 実機での試験手順案（メインセッション用、1変数ずつ）

前提: 各ステップの前に FPGAを書込んだイメージのSHA-256とUSERCODEを記録。最初の失敗で止める。再送・自動fallbackなし。

1. `filtered_edge` イメージをSRAMへ書込み（`programmer_cli`）。Tab5は基準の20MHz連続RX構成のまま（周波数・位相・駆動強度は変更しない）。
2. 20MHz（合格点）で通常描画→`0xCD`でクリア→タイル1回→`0xCC idx=12,4,5,6,14` を各1回（その都度タイルを繰り返す）。期待: pre+post=2066、reject=0、bit0=1。これでモニタ自体が実機で正しく動くことを確認（未確認なら25MHzの結果は解釈しない）。
3. 周波数のみ25MHzに変更（NEG／POSを別々に）。タイルごとに上の項目を読み、判定（上記）を記録。
4. 結果が「pre+post==2066でCRC失敗」→トラックN（応答位相）へ。「>2066またはreject>0」→track-m（駆動強度）、直列抵抗の変更へ。
