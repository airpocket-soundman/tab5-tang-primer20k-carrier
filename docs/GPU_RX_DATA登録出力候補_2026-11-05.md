# GPU RX DATA登録出力候補（2026-11-05）

## 変更と独立条件

`link_reply_raw` に `REGISTER_OUTPUT=0`、LINK wrapperに
`REPLY_REGISTER_OUTPUT=0` を追加した。既定0は従来の組合せ出力を維持する。
新しい `tab5_dock_registered_reply_top` だけを1にし、selected_byteを
返信CLKの立上りでDATA用FFへ取り込む。CRC計算には遅れたdata_oを使わず、
同じ内部selected_byteを使う。

候補は `FAST_FILTER_SYNC=0`、`REPLY_RAW_BYPASS=0`、`FRAME_TIMING_ENABLE=0`。
v5の要求データpipeline・REGISTER_INPUT・全8シーン・ピンと、従来の216MHz filterを維持し、
filter短縮候補やframe cycle計測の変更と混ぜない。新ホスト命令やフレーム形式変更はない。

## 1byte pipelineの整列

単純なDATA FF追加ではprefixが1byte増えるため、REGISTER_OUTPUT=1に限り以下を行う。

| 実際の返信CLK立上り | masterが取るDATA | 内部indexと処理 |
|---|---|---|
| 1回目 | 初期値C3（prefix0） | index0のC3をFFへ、indexを2へ進める |
| 2回目 | prefix1 | index2のC3をFFへ |
| 3回目 | prefix2 | index3でRAM word0をprime。実3rd edgeである点は従来と同じ |
| 最後の1回前 | CRC_LO | CRC_HIをFFへ、retiringを立てindex固定 |
| 最後 | CRC_HI | masterの取得後にdoneを立てる |

prefixは従来通り8byte。タグ付き通常応答16byte、ROW82byte、TILE2066byteの
総wire byte数を維持する。retiring edgeではCRC・progress・prefetchを重ねて処理しない。
offer解除、reset、DIR中断、RAM tag errorでは登録値C3・retiring0へ戻し、
RAM tag errorによる即時abortとwrapperのOE/READY停止も維持する。

## 最終候補v2

- ビルド：`fpga/builds/dock/build_registered_reply.tcl`
- FS：`fpga/build/registered-reply-v2/registered_reply/impl/pnr/registered_reply.fs`
- UserCode：`0xC512`
- SHA256：`01d0d6e3a00da405411fda726d6f3e0950e8db065b89537cb12efbfa402201a6`
- 公式Education版、既存core54／sampler216／conditioned_reply54制約でsetup/hold違反各0。
- 最悪slack：setup +2.050ns、hold +0.074ns、recovery +3.236ns、removal +0.829ns。
- Fmax：core54 60.723MHz、sampler216 390.575MHz、conditioned_reply54 66.146MHz。
- 限定metadata第一段30組のみを例外とし、mapped source→stage0→同bit stage1 sole fanoutを監査。
- serializer FFと両DPB Port Bの150 clock endpointsが同じ返信CLKを使用することを監査。
- ビルド前に全ソースと制約をfresh出力内のsource_snapshotへ保存。最終ソースとのbyte一致を確認。

registered_byteのFF CLK→DATA padのSDF structural maxは、bitごとに6.67～8.34ns。
これは特定信号を起点にした構造上の極値で、外部配線・P4の入力余裕やsensitized pathの
実測ではない。wrapperにはlegacy分岐を含む他の構造経路も存在する。
物理IOレジスタへの配置やジャンパ線での速度向上を、この解析だけから主張しない。

## 検証範囲

- 単体18packetsでshort／ROW／TILE、color／depth、header/body CRC、prefix8、
  最終CRC_HIの退役を全byte確認。
- metadataをoffer直前・停止CLK中に更新し、2段同期後の実3rd edgeのRAM primeを確認。
- 既定0は固定旧版72724adと、DATA・done・started・error・progress・row index・RAM address・enableの波形が一致。
- RAM tag error、offer解除、DIR中断、停止CLK中resetを確認。v2はtag error時C3も明示的にassert。
- 既存golden264取引をREGISTER0／1で各合格。全ROW32行のcolor/depth、TILE、
  triangle/fractal、tagged/untagged/error/timeout/resetを含む。
- 公式DPBを使ったfiltered control41packetsに合格。metadata保持・settleのassertは
  prefix316／settled41646 edgesで非空を確認し、DIR/ARM/reset/timeoutと停止CLKからの復旧も確認。
- v2 full LINKはenabled42／disabled27 vectorsに合格。最大batch、UPLOAD、
  CRC破損時の非実行、全タイル画素とCRC、中断・再開を含む。
- v2実post-PnR netlistでもnative Wire先頭5 recordsと全1024画素・CRCに一致。
  このgate試験は理想PLL出力・8MHz bus・SDF無しの機能確認であり、実機タイミング証明ではない。

v1（User12F9）は最初の保存点。v2ではRAM tag error時のDATA登録値C3を追加して再検証した。
正常転送の内容・byte数・latencyは同じ。各ビルド・失敗を上書きせず保存した。

オフライン記録：`fpga/build/registered-reply-unit-v2-tests`、`registered-reply-v2-link-tests`、
`registered-reply-v2-gate-tests`、`registered-reply-control.json`、
`registered-reply-{golden0,golden1,control}.log`、最終候補内の`audit.json`・`metadata-proof.json`。
実機試験はrootが別の結果記録として実施し、ここで実機合格を先取りしない。
