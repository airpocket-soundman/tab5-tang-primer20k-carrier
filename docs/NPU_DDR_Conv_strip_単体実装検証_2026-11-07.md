# DDR Conv strip sequencer：独立RTL実装（2026-11-07）

状態：**単体実装・RTL試験済み、top/protocol/bitstream/実機は未統合**。既存4E24、op68/78、ピン、能力値を変更しない。[次段提案](NPU_RTDETR_Conv_strip集約案_2026-11-07.md)のX/IC loopだけを、汎用Conv tile loader向けcontrollerとして実装した。NN graph全体・FP32 epilogue・P4中間値往復解消は未実装。

## APIと計算配置

`fpga/npu/rtl/npu_ddr_conv_strip_sequencer.v`。SYS単一clock、job ready/valid、完了out_valid/out_ready、result_valid/error/code/quarantined、accepted/completed/expected tile数、loader descriptor ready/validと既存52B descriptorを持つ。jobは18個の32bit word（IC, OC, OH, OW, kernel, stride, IH, IW, signed originY/X, A base/row/channel pitch, B base/OC pitch, C base/row/channel pitch）。これは内部RTL interfaceでありwire ABIではない。

OC1..8、OH1..16、OW/IC/IH/IW1..65535、kernel1/3、stride1/2。X16 outer、IC16 inner。各Xについてfirst/最終ICを連続実行し、INT32累積を既存engine内で保持する。CはOC×OH×全OWのstrip。output_base=C+x*4、row/channel pitchはjob値を維持する。halo/paddingは既存loaderが担当する。tail所有bitはtrue固定、callerはCのaligned paddingを専有する。

jobを全幅で検証した後だけdescriptorを出す。base/pitch16B alignment、最低row/channel/weight pitch、64bitのspan/端点/128MiB範囲、A/B/C非重複、signed origin進行のoverflowを検査。全tile数も64bitで検査する。7種の積は単一32cycle shift-add multiplierを再利用し、BRAM/DSPを要求しない記述。ただし**合成資源・timingは未測定**。既存chipへfitするとは未認定。

## cancel/reset契約

abortはjob受理・descriptor発行・結果handshakeより優先する。exportするout_valid/result_validは内部registerから !abort && memory_ready && reset_n で組合せgateし、同じedgeでout_readyが立つconsumerにも古い成功を渡さない。cal-lossの内部invalid化はgate前registerを見る。descriptor_validもabort/memory_readyでgateする。loaderが動作中ならtile_abortを保持し、有限drain待ち、期限超過はquarantine。issue待ち/実行待ちはそれぞれ有限timeout。done/busyのlevelだけでdeadlineを延長しない。error後は新jobを拒否し、clearは安全なidleでのみ許可。quarantineはclearで解除せず、controller/loader/DDR adapterを**同じ所有者管理下でcoordinated reset**する。通常clearもloaderのabort faultと協調する。単一pulseではheld tile_abortによる再faultが起き得るため、両方cleanになるまでcoordinated clearを保持するかjoint resetし、tile_done/errorが解消してから新jobを発行する。abortを保持している間は結果を公開しない。既にDDRへ書いたprefixはrollbackしないがresult_validは全strip完了まで立てないので、失敗Cを使ってはいけない。

## proof

[結果とcommand/source SHA](../fpga/validation/npu-conv-strip-standalone-2026-11-07/result.json)・[manifest](../fpga/validation/npu-conv-strip-standalone-2026-11-07/SHA256SUMS.json)。再現：repository rootから `python fpga/npu/tests/run_ddr_conv_strip_sequencer.py`。生成した巨大DDR vector/binaryはbuild下だけで、archiveにはscript/RTL、job、descriptor trace、TBと小さな結果を保存する。

- fake loader試験67job、4,299 accepted descriptor。OW65535、IC768、IC17/33/65、幅端数、k1/3、stride1/2、負origin、descriptor backpressure、sticky tile_done、結果backpressure、abort同時受理/結果、calibration loss、timeout、quarantine、bad final result、高位field/範囲/pitch/overlap拒否を検証。
- 実RTL descriptorを解釈する独立fake engineと、分割しないwhole-Conv INT64 oracleを比較し8,404 INT32値一致。この試験だけを実MAC検証とは呼ばない。
- 追加4jobは**既存8OC MACとDDR loaderを実際にinstantiate**。IC17/33継続、OC8、X19/33端数、padding、stride2、k1/3、計16tile・1,057 INT32値が独立whole-Conv oracleとbit一致。256KiB fakeDDR全域を比較し入力/重み/gap/guard不変、output paddingのみ所有通り更新。DDR PHY・CDC bridge・pin-level commandは対象外。

独立reviewで、当初registerのままexportしたvalidはabort/cal-lossとout_readyが同edgeのconsumerで古い成功を受理できる問題を指摘された。上記の組合せgateに修正し、private consumer gateなしのposedge valid&&ready observerを追加した。gateだけを除去したbuild-copyは当observerで意図通り失敗し、修正版ではabortとcal-lossの両方がPASS。

最初のTBはabortを保持しながらout_valid保持まで要求して失敗した。abort優先契約に合わせ、完了観測時にabortを解除してbackpressure確認するTBへ修正した。数値不一致を許容した変更ではない。

## 全host参照と次の判断

[参照版とfile SHA](../fpga/validation/npu-conv-strip-standalone-2026-11-07/host-references.json)。Linux `cfc9a6e`のREADME/DEVELOPMENT_GOALS/DT/portable driver、MeOS `78274b4`のREADME/要求/driver、Linux memory研究 `e84b59e`の計画、ESP-IDF README/Project B/通信/backend/表示を確認した。Linux/MeOSはMEM/能力照合を持つが本strip commandは全hostで未実装。研究計画は透過RAM増設ではない。今回はcommand/pin/電源を決めないためhost反映は不要。将来のcapability/opcode/CRC/session/generation/排他/timeoutを別reviewで確定し、各hostの未対応を明示する。

次は主担当による内部interface review後、exclusive loader mux・SYS commandを新candidateへ接続し、pin-level fakeDDR/lease/CRC regression、合成とunwaived STAを確認する。既存4E24資源45/46BSRAMとSTA未認定を維持し、新bitstreamの実機評価までは速度・ジャンパ限界・全NN融合の達成を主張しない。
