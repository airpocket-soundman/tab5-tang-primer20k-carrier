# FIFO＋FAST_FILTER＋RX登録出力統合候補

2026-11-06。DF72（216MHz request capture、1byte/SYS FIFO、FAST_FILTER_SYNC1、frame timing ON）へREPLY_REGISTER_OUTPUT1だけを加えた独立候補。共通RTLは変更せず、新top/buildでパラメータを選択する。C512の登録出力はFAST_FILTER0だったため、この組合せを独立検証した。入力captureとSYS54描画は維持し、RX DATAのserializer combinational pathを出力FFで分離して余裕改善を狙う。RX20実機成立は未確認。

## 保存点

- top `fpga/platform/dock/tab5_dock_duplex_register_top.v`
- build `fpga/builds/dock/build_duplex_register.tcl`、公式Education1.9.11.03、fresh `duplex-register-v1`。
- FS `fpga/build/duplex-register-v1/duplex_register/impl/pnr/duplex_register.fs`、User7375。
- SHA256 `4aaac60cf35ec9effa1eb48aec657c8d29c9ea18655eca7c0d20a0667af8427b`。
- STA最小slack ns: setup0.890/hold0.074/recovery1.300/removal0.323、4種違反0。既存metadata30例外のみ、追加waiver0。
- serializer/DPB共通clock、DATA16+CLK3/Gray20 DFFC solefanout、storage4LUTRAMを監査。
- registered_byte8bitすべて実DFFで同じserializer clock、各bitの対応FFからpadへのSDF経路を監査。構造的FF CLK→pad min3.478..max8.470nsは実測値でも経路sensitization保証でもない。

## byte契約と検証

登録出力のprefix index1 skip、実3rd edgeでRAMword0 prime、最終CRC_HIをregistered出力して次edgeでretireする実装はC512と同じ。prefix8byte、全wire長、CRC最終byteを維持する。CRCは遅れたdata_oではなくselected_byteから計算する。

- serializer18packet: ROW/TILE両color/depth全byte、prefix8/CRC/末尾retirement、late metadata、RAMtag、offer/DIR/reset、default0 legacy波形一致。
- combinedcontrol41packet、CDC prefix 316 edge / settled-stage1 41,646 edge。FAST1/REG1/FIFO1/PIPE1/timer1、vendorDPBで停止HIGH、timeout、DIR/ARM/reset、noise/fault、ownershipを確認。
- combinedLINK有効42/無効27vector全一致。
- mapped gate TX32/40、RX8で各15vector。timerABI、実Wire5recordsと画像、最大TRI/R2/upload64を確認。理想PLL・SDFなし。
- 全ROW/TILE color/depthを含む264golden wire transactionsを、SYS54＋filter216＋FAST1/REG1/FIFO1/PIPE1/timer1のtemporary fixtureで確認。最後のtimeout/disarm/resetまで合格。これはportable tile RAMを使うbyte oracleで、vendorDPBは上記control/gateで別途検証。

264fixture作成時、元runnerのbench-last仮定による重複module、coverage二重指定、top timescale未指定、元SYS100MHz用timeout6.001ms残存を順に修正した。最終SYS54では600000cycleに対応して11.12ms待つ。これらの失敗logもハーネス不具合として保存し、候補RTLの成功に混ぜていない。

`fpga/validation/duplex-register-2026-11-06/candidate.zip` とmanifestにFS/STA/SDF/source snapshot/proof/temporary drivers/log/vectorを保存し、ZIP CRCと全展開byte一致を確認。

実機操作なし。親担当がDF72のTX32/40評価後、この7375で両方向の最大と全画素一致を確認する。物理ARMによるoverflow復旧、末尾CRC2us保持、DIRguard等は前候補の前提を継承する。ピン、コマンドABI、ホスト要求の変更なし。
