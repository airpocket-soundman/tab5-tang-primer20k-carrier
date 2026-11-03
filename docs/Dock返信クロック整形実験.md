# Dock返信クロック整形実験

2026-11-04。隔離ブランチ`codex/clock-filter`、起点`9c314f3`。実機未実施。配線ringingの存在・原因を確定したものではない。既存5b93 bitstream/PNR/CSTを変更せず、新しいRTLとビルド先だけを使用する。

要求受信は元のraw CLKをSYS54の既存3段同期へ入力する。タグ付き返信serializerとTDP read portだけを同じ整形CLKへ接続する。DIR0/offer0の遅いTXクロックも整形CLKへ伝搬し、元のserializer reset/metadataライフサイクルを維持する。offerに新しい非同期resetを加えない。raw ARM/reset/DIRによる即時OE遮断を維持し、PLL lock喪失もplatform resetに含める。

27MHz入力から別rPLL(IDIV0/FBDIV7/ODIV4)で216MHz、VCO864MHzを生成する。元のSYS54 PLLとCORE_CLOCK=54/INFO021fは維持する。2FF samplerの後、同じ値の2サンプルでlevelを更新する。受理riseでclean HIGHを2tick保持、cooldown=4を設定し、事前値が0のときのみ次riseを受理するため最小rise間隔は5tick（約23.15ns）。reply active中に2sample幅のriseが早すぎたらfaultとしてOE/READYを遮断する。短パルスを除く比較であり、データ補完、CRC修復、返信byteの合成は行わない。

Icarusのsample periodは4630ps（216MHzを1ps刻みに量子化）で、90のinteger/fractional-divider・位相条件5..40MHzについて200riseが一致。1ns pulse除去、短間隔の大きいpulseをfault、hostclock停止中の非同期resetを検査した。2FFはメタステーブル解析・MTBF保証ではなく、実padの電圧/波形もモデル化しない。

観測されたデジタル入力→clean rise遅延は13.890..18.519ns。40MHzのlegacy次sampleまで25nsから、この遅延、往復配線、FPGA Tco、host setupを引く必要がある。入力反転の半周期sampleは場合によってOLD/NEW byteのどちらを読むかが変わり、単純に半周期を余裕へ加算しない。完全な元のheader/payload/bound CRCを一意に観測した場合だけfunctional matchとする。training prefix中のheader位置は変わり得る。取得byteの並替え・再構成はしない。

最初のfull TILEモデルは13周波数11..40MHz×3SYS位相×2sample位相×3片道遅延0/2/5ns×2Tco0/2ns=468条件、456条件が完全一致、12条件は失敗として保持。これはaddress-varied color/depth2048byteのデジタルモデルであり、host setup/hold余裕や配置配線の証明ではない。setup/hold apertureとcontrol/abortの追加検証を行う。単体の5/8/10MHzとfullモデルの周波数集合を混同しない。

配置配線はosc27、core54、sampler216、conditioned_reply54（最小間隔43.2MHzに対し保守的54MHz）をSDCで別々に指定する。216MHzを既定54MHzで代用せず、matched-no-objectsやtiming failureを許可しない。配置配線結果は別記録で示すまで未検証。

参照ホスト：ESP実装`18c763b`、周波数診断`e67ffa4`、既存通信・表示、`Project_B_Tab5_FPGA_GPU.md`。Linux`cfc9a6ec`のREADME/DEVELOPMENT_GOALS/既存DTS、MeOS`26c80829`のREADME/FPGA_CARRIER_REQUIREMENTS/driver、メモリ研究`e4aa69d0`の計画も照合した。Linux/MeOSのこの高周波数DMA経路は未実装・未検証。既存3.3V/pin/ABIを保持する隔離試験であり、全OSの電気的適合やキャリア最終仕様を確定しない。DDRを同時搭載せず、ホスト変更を要するコマンド追加もない。
