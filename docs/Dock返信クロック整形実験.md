# Dock返信クロック整形実験

2026-11-04。隔離ブランチ`codex/clock-filter`、起点`9c314f3`。実機未実施。配線ringingの存在・原因を確定したものではない。既存5b93 bitstream/PNR/CSTを変更せず、新しいRTLとビルド先だけを使用する。

要求受信は元のraw CLKをSYS54の既存3段同期へ入力する。タグ付き返信serializerとTDP read portだけを同じ整形CLKへ接続する。DIR0/offer0の遅いTXクロックも整形CLKへ伝搬し、元のserializer reset/metadataライフサイクルを維持する。offerに新しい非同期resetを加えない。raw ARM/reset/DIRによる即時OE遮断を維持し、PLL lock喪失もplatform resetに含める。

27MHz入力から別rPLL(IDIV0/FBDIV7/ODIV4)で216MHz、VCO864MHzを生成する。元のSYS54 PLLとCORE_CLOCK=54/INFO021fは維持する。2FF samplerの後、同じ値の2サンプルでlevelを更新する。受理riseでclean HIGHを2tick保持、cooldown=4を設定し、事前値が0のときのみ次riseを受理するため最小rise間隔は5tick（約23.15ns）。reply active中に2sample幅のriseが早すぎたらfaultとしてOE/READYを遮断する。短パルスを除く比較であり、データ補完、CRC修復、返信byteの合成は行わない。

Icarusのsample periodは4630ps（216MHzを1ps刻みに量子化）で、90のinteger/fractional-divider・位相条件5..40MHzについて200riseが一致。1ns pulse除去、短間隔の大きいpulseをfault、hostclock停止中の非同期resetを検査した。2FFはメタステーブル解析・MTBF保証ではなく、実padの電圧/波形もモデル化しない。

観測されたデジタル入力→clean rise遅延は13.890..18.519ns。40MHzのlegacy次sampleまで25nsから、この遅延、往復配線、FPGA Tco、host setupを引く必要がある。入力反転の半周期sampleは場合によってOLD/NEW byteのどちらを読むかが変わり、単純に半周期を余裕へ加算しない。完全な元のheader/payload/bound CRCを一意に観測した場合だけfunctional matchとする。training prefix中のheader位置は変わり得る。取得byteの並替え・再構成はしない。

最初のfull TILEモデルは13周波数11..40MHz×3SYS位相×2sample位相×3片道遅延0/2/5ns×2Tco0/2ns=468条件、456条件が完全一致、12条件は失敗として保持。これはaddress-varied color/depth2048byteのデジタルモデルであり、host setup/hold余裕や配置配線の証明ではない。setup/hold apertureとcontrol/abortの追加検証を行う。単体の5/8/10MHzとfullモデルの周波数集合を混同しない。

配置配線はosc27、core54、sampler216、conditioned_reply54（最小間隔43.2MHzに対し保守的54MHz）をSDCで別々に指定する。216MHzを既定54MHzで代用せず、matched-no-objectsやtiming failureを許可しない。配置配線結果は別記録で示すまで未検証。

参照ホスト：ESP実装`18c763b`、周波数診断`e67ffa4`、既存通信・表示、`Project_B_Tab5_FPGA_GPU.md`。Linux`cfc9a6ec`のREADME/DEVELOPMENT_GOALS/既存DTS、MeOS`26c80829`のREADME/FPGA_CARRIER_REQUIREMENTS/driver、メモリ研究`e4aa69d0`の計画も照合した。Linux/MeOSのこの高周波数DMA経路は未実装・未検証。既存3.3V/pin/ABIを保持する隔離試験であり、全OSの電気的適合やキャリア最終仕様を確定しない。DDRを同時搭載せず、ホスト変更を要するコマンド追加もない。

## OSS経路のタイミング被覆と公式ツールへの分離

`keep` clock anchorを追加する前のSDCはalias消滅で3clockにmatched-no-objectsが発生したため不合格として保持。anchor追加後のOSS配置配線はcore54/conditioned54が通ったが、sampler216がpost-routeでno-interior-pathsとなった。10FFが実際に216で動くのにdetailed timingから全て消えたため、packされたFS7ca8も実機候補として採用しない。

GFX/RAMを除いた同一samplerの小さいrouted再現では10FF/6追加passthrough LUTに対し216 endpointは1のみ。公式Educationの同一samplerは71path/38endpoint、stage0→stage1・counter・pulseを明示して216MHzに対するFmax397.135MHzを報告する。nextpnr0.11.1の公式ソースではGowin postPlaceでpassthrough LUTを作り、その後のtiming_index初期化が見つからない。未初期化indexはTMG_IGNOREになるため、被覆欠落の説明候補である。ただし修正ビルドとの対照までは実施しておらず、原因確定とはしない。旧イメージの実機で一致した画素・CRCを否定するものではなく、OSS post-route timingの被覆範囲に関する問題である。

参照一次ソース：nextpnr `nextpnr-0.11.1`の[gowin.cc](https://github.com/YosysHQ/nextpnr/blob/nextpnr-0.11.1/himbaechel/uarch/gowin/gowin.cc)、[arch.cc](https://github.com/YosysHQ/nextpnr/blob/nextpnr-0.11.1/himbaechel/arch.cc)、[timing.cc](https://github.com/YosysHQ/nextpnr/blob/nextpnr-0.11.1/common/kernel/timing.cc)。グローバルなツール変更は行っていない。

## 組合せ候補：公式DPBとcoverage pipeline

公式Educationで元RTLのRAM推論が非対応WRITE_MODE0=10となりPA2122で停止した。この出力を手で書き換えず、別の`triangle_tile_vendor.v`と`tile_dpram_vendor.v`を作成した。DPB16、mode00、READ_MODE0/1=0の同期1clock read。A出力はwrite時に保持され、rendererはその周期のA read値を消費しない。Bはread-onlyでA writeと同時enableしない。両clock側のownership assertion、公開`gw2a/prim_sim.v`による2050 native check（全1024wordのA/B read、write時A保持、B無効時保持）がPASS。生成されたベンダーソースや暗号化IPは改変しない。

公式ツールでは旧1stage coverageのparams→multiply→winding mux→multiply→coveredがSYS54を満たさなかったため、親承認の隔離版`triangle_coverage_pipeline.v`を追加。17bit差分、34bit積、35bit edge、winding/top-left/64bit outputの4stageで、元vertex順のedgeを計算後、負winding時に符号を反転する。元のZ対応順と丸め・符号幅を維持する。pixel候補ごとに3cycle増えるが既存READY/BUSYの可変待ちで扱い、同じ性能の実装とは扱わない。元のraw5b93/9c314f3は変更していない。

独立Python oracleと実際のCPU G0 C関数を用いた3328 random/extreme/edge/top-left vectorが一致し、4stageの連続入力・bubble・inflight resetもPASS。公式DPBに置き換えた前後とも991 fractal transaction/24576 color+depth pixel（12 legacy/vivid viewport、DRAW cyclesも一致）と10334 polygon transaction/7 draw/全RGB565+depth16がPASS。公開primitive modelによる結果であり、DDRまたは実機GPU画素の試験ではない。

SYS54から216 counterの非同期reset解除にrecovery違反が残ったため、raw reset/ARM/PLLlockから216専用の2段async-assert/sync-releaseを追加した。SYS54-qualified resetを216へ流用しない。元のraw ARM/reset/DIRによるOE即時遮断は別に維持する。false path、multicycle、clock group、timing-allow-failは追加しない。

## 最終オフライン結果

`build_clock_filter_reset216.tcl`、Education1.9.11.03のfull imageは18063 path/5882 endpoint、setup/recovery違反0、hold/removal違反0。Fmaxはcore54=64.662、conditioned reply54=80.529、sampler216=295.320MHz。sampler meta→sampled、counter/pulse、局所reset release→counterの実パスを記録し、reset recovery最小+2.981ns、removal+0.964ns。これは外部バス周波数の最大値ではない。

最終ソースをsnapshot固定して実施したTILEモデルは576条件（高周波468＋5/8/10MHz108）。564条件で完全な元のheader/payload/boundCRCが一意に一致し、仮定のsetup/hold各2nsを加えた条件付き合格は525条件。失敗した仮定を除去せずJSONに残す。例えばlegacy40MHzは往復配線/Tcoに敏感で、入力反転も一律に改善しない。controlは41 packet、DIR0 reset life、stopped CLK、ARM/reset/DIR/timeout、1ns pulse除去と大きい短間隔pulseのfail-closedを確認した。

公式full候補FS SHA256 `6c5a10f5c298bc78a8c73bd455247e7f1ea9278880ef055fb8e15d867146658e`。bslibによる全frame CRCを検査し、footer0Aは7D1F。実際のprogrammer USER/statusは親担当が独立に確認する。`fpga/validation/clock-filter-qualified-2026-11-04`にFS/STA/実行log/配置配線・pin reportのgzipとSHAを保存する。sampler-onlyのFSはLINK/GFXを持たないため、実機へ書き込まない。

まだ実機合格ではない。親担当は既存イメージへ戻せる状態で、明示されたhost phase/driveと8MHz controlから始め、20/25/26.666/32/40MHzを各点の完全CRC+CPU全画素一致に応じて進める。失敗時は自動再試行や位相切替を行わず停止する。高周波数の実pad波形・配線遅延・bit error rate・絶対的ジャンパ限界は未測定である。

最終RTLソース凍結は`255e5da5a71b551ecb055bdb035dfe0ba433d85d`。独立担当が3328 coverage、同じ3328 CPU C、2050 DPB、41 controlを再実行してPASSし、STAの3clockと最小setup1.031ns/hold0.107ns/recovery2.981ns/removal0.964nsを再確認した。別担当も幅・順序・DPB latency/ownership・raw reset/ARM/PLL lossのOE遮断をソースレビューし、制御試験を妨げる所見はなかった。いずれも実機証明ではない。

追加の長いHIGH側モデル（160MHz dividerのHIGH=ceil(div/2)）は別JSONに468条件を保存し、444完全一致、408条件付きsetup/hold合格。短いHIGH側と低周波の先行576条件と合わせ1044条件、1008完全一致/933条件付き合格だが、同じ条件の重複も含むデジタル試験数であり物理試験標本数ではない。両RX位相・両dutyモデルともlegacy20/25MHzは各18条件すべて合格し、inverted25/32などには追加失敗が出る。実P4 dividerのduty/順序は未測定のままなので、有利な方だけを選んで最高速度を主張しない。この追試でRTL/FSは変更していない。
