# Request FIFO 1byte/SYS候補（2026-11-06）

従来FIFO read側はfetch/consumeで2SYS/byte、理想27MB/s。PIPELINED_READ=1でconsumeと次byteのregistered RAM readを同じSYS edgeに重ね、定常1SYS/byte、理想54MB/sを目指す。空からの初回fetchとデータ不足時のbubbleは残る。default0は従来動作を維持し、5762のsnapshotとbyte_valid/byte_data/overflowを比較して一致を確認した。

## 所有権と安全性

holding出力のbyte_ready消費時だけread_binary/read_grayを1進める。次slotがwrite_gray_sampledに対して存在する場合だけbyte_dataへprefetchしholdingを継続する。prefetchだけでreadptrを追加公開しないので、未消費byteのslotはwriterから保護される。stall中は出力data/validとreadptrを維持する。empty/full、Gray2段、overflow sticky、DIR/ARM/reset、failclosedは従来通り。

Gowinは現在/次slotの2readportを複製メモリへ割当て、RAM16SDP4が2→4個となる。論理FIFO容量16byteは変えず、物理上は16byteの写しを2組持つ。byte_dataへの読出しはSYS FFで登録される。BSRAM同期latencyを仮定した実装ではなく、実mapped RAM16SDP4の非同期DO＋FF構成を監査した。

## 独立候補

- top `tab5_dock_request_fifo_pipe_top`、FIFO216 capture/CORE54/FAST1/timerON、PIPELINED_READだけ1。
- build `fpga/builds/dock/build_request_fifo_pipe.tcl`、fresh `request-fifo-pipe-v2`。v1は宣言順修正前として保存、実機にはv2を使用。
- FS `fpga/build/request-fifo-pipe-v2/request_fifo_pipe/impl/pnr/request_fifo_pipe.fs`、UserDF72。
- SHA256 `2d5bc90796a959df2fdfe4ccf9a4a9efd44b1148b0d00083a63feff72b28e512`。
- STA min ns: setup1.391、hold0.074、recovery0.695、removal0.327、違反0。216/54は同27入力のrelated clock。新falsepath/clockgroup/multicycleなし、既存metadata30のみ。
- DATA16+CLK3/Gray20 DFFC、各meta solefanout、共有reply/DPBclockを監査。storage4LUTRAMを明示期待する独立引数をauditへ追加、既定期待2は維持。

## 論理検証

- TX32MHz（period31.25ns/HIGH12.5ns/LOW18.75ns）と40MHz（25ns/12.5ns/12.5ns）、各10SYS位相×scalar/TRI64/R2-64/upload64＝40ケース全一致。最大1290byteと全640 staging wordsを比較。
- 同条件default0対照は各2位相、短scalar2/2通過、長batch6/6不一致。従来27MB/s受信処理では32/40MHz長burstを処理できないことと整合する。
- 単体は32/40それぞれ32位相×2skew×5packet、412800byte一致。stall、header→body待ち、停止HIGH、DIR、ARM/reset、overflowsticky/再ARMを含む。
- LINK有効42/無効27vector合格。mapped gateはTX32/TX40、RX8で各15vector合格。timerABI、実Wire5recordsと画像、最大TRI/R2/uploadを含む。理想PLL・SDFなしなので実機入力信号品質の証拠ではない。

## 短い入力保持時間の失敗を保存

単体benchはDATAをt0で変更しLOW後にraw CLKを上げ、そのCLKだけ仮想skewで遅らせる。40MHz skew+10nsならDATA=t0、received rise=t22.5ns、次DATA=t25nsで、setup22.5ns、hold2.5ns。32MHzもHIGH12.5nsなのでskew+10ns時hold2.5nsとなる。216MHzのサンプル間隔約4.63nsより短く、位相によって次byteを捕捉する失敗を確認した。これはprefetch FIFO処理量とは別の入力窓条件である。

skew0/+5nsではhold12.5/7.5ns、各32位相で一致。最初の連絡で2.5nsをsetupと記述したのは誤りであり、上記イベント時刻に基づくholdが正しい。仮想skewは実ケーブルの測定値ではない。

## 保存と実機の境界

`fpga/validation/request-fifo-pipe-2026-11-06/candidate.zip` とmanifestにsource snapshot/FS/SDF/STA/proof/参照vector/log/失敗skew記録を保存。ZIP CRCと展開全byte一致を確認。実機未試験、速度達成未認定。5166/5762とは独立候補で、物理ARMによるoverflow復旧、末尾CRC2us保持、DIRguardの既存前提を継承する。ピン/コマンドABI変更なし、Linux/MeOSへの新仕様反映は不要だが当候補の実機適合は未検証。
