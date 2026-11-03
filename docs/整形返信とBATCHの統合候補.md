# 整形返信とBATCHの統合候補

2026-11-04、独立branch `codex/filtered-batch`。baseは整形返信source `255e5da5a71b551ecb055bdb035dfe0ba433d85d`、BATCH移植元はcanonical `9dee0af`。既存255e/6c5a、raw返信/944、hostバイナリは変更しない。プログラム操作は行っていない。

変更はcanonical BATCH OP40/41、count1..64、640word staging RAM、全payload/trailer CRC確認後の実行開始を、既存vendor DPB/coverage pipeline/local216resetのfiltered coreへ統合するもの。serializerとDPB portBは同じclean clockを維持する。TILE/fractal/vivid/CORE54は維持し、TXcaptureは追加しない。

通常route0の最初の公式ビルドはmetadata first-stageのhold違反31本（最小−0.188ns）で不合格だった。RTL/SDCを変えず、公式 `route_option=1` を使う別buildはactual core54/conditioned54/sampler216のsetup/hold違反0となった。Fmaxはそれぞれ64.518/83.813/329.931MHz。false-path/multicycle/clock-group等のwaiverは追加しない。初回失敗を削除しない。

オフライン確認:

- BATCH48 pin-level vectors: count1/2/63/64のcolor/depth全画素、各record/trailer破損でatomic no-execute。
- filtered control41: prefix/CRC、DIR/ARM/reset/timeout、停止CLK、反復plane/seq。
- native polygon10334 wire transactions、7draw、RGB565/depth16一致。
- native fractal991 transactions、24576 color/depth pixels、12 legacy/vivid viewport、DRAW cycle一致。
- C BATCH codec/Python oracleテスト1件合格。

この統合はまだ実機検証していない。baseの整形返信候補は8MHz CRC失敗、GPIO/1MHzは一致という独立実測結果がある。公式内部STA合格はpad間の往復・P4 capture位相・ケーブル性能を保証しない。BATCHの追加をもって高周波動作を合格としない。

再現: `fpga/builds/dock/build_filtered_batch_route1.tcl` を公式Gowin Education V1.9.11.03のgw_shで実行する。出力は新規 `fpga/build/filtered-batch-route1`。全ソース/CST/SDCは既存buildと分離し、flashはrootの独立レビュー後のみ。
