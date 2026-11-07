# RT-DETR V3 request CRC1 読み取り監査（2026-11-07）

V3は最初のConv中、409 tile後にop71のdevice status1で停止した。応答header CRCは正常という主担当の記録に基づく。全モデル成功ではない。RTL、host production、機器は変更していない。

## 独立fixture

[結果](validation/rtdetr-v3-crc-audit-2026-11-07/result.json)は実際の`conv_exchange_bounded` frame生成文、`link_protocol.h`、bytewise `dma_tx_pack.hpp`を使用する。2032/2032/32、16B連続GPIO、256/128Bを混在させた264,000 frame、120,720,000 wire bytesを、別のPython `binascii.crc_hqx`で全件検査しPASS。96,000 DMA選択、168,000 GPIO選択、sequence wrap 1,031回。guard、trailer、packed低byte一致/上byte0も検査した。巨大な生成vectorは保存せず、script、fixture source、commandとsource SHAを残した。

これはソフト上のframe/packing破損を当fixture範囲で再現しなかった証拠であり、PARLIO/GDMA/FIFO、GPIO matrix切替、電気波形を検証したものではない。

## 失敗経路を断定しない理由

backendはConvの全qinputを先にuploadし、その後tileを走らせる。409 tileが最初のConvのcounterなら、op71はqinput256B uploadよりもgraph出力page-cache writebackの可能性がある。4096B pageは2032B DMA +2032B DMA +32B GPIOに分割される。失敗packetのdata長/DMA選択を記録していないため、DMA失敗とは断定できない。累積DMA58553回/fault=falseは当該packetを特定しない。`npu_write`のfaultは送信driver/completionについてのもので、その後届くFPGA CRC status1を表さない。

| data bytes | payload bytes | frame bytes | 現min_payload256での経路 |
|---:|---:|---:|---|
| 16 | 24 | 34 | GPIO |
| 32 | 40 | 50 | GPIO |
| 256 | 264 | 274 | DMA |
| 2032 | 2040 | 2050 | DMA |

2032Bは16bit packing後4100BとなりGDMA descriptor境界を跨ぐ。この長さとCRC生成はfixtureでは正常だが、実機descriptor/FIFO動作の証明にはならない。payload bufferは内部DMAメモリ・128B alignment、完了まで保持、末尾CRC byteを2us保持、CLK0/mux復元、data入力化、callerの方向切替guardという処理がある。読み取りでは具体的な欠落を見つけていない。

## 10MHz条件

4E24は4E22と同じCLK27MHz・CLK同期2段と整合DATA2段入力。理想10MHzのhalf50nsに対しSYS周期37.037nsで、理想edge幅の余裕は12.963ns。既存digital phase sweepのaligned positive5/8/10/12MHz各333/333はPASS、14MHz以上はalias。27MHz/2=13.5MHzは理想sampling上限であり、実基板の保証値ではない。duty、jitter、setup/hold、metastability、配線をdigital試験では評価していない。既存full-chip STAもunqualifiedのまま。

SDK `D:/espbuild/rtdetr/sdkconfig`ではPM disabled、CPU360MHz。動的CPU周波数変更を今回の原因とする根拠はない。

次の明確な比較は同一source/入力で5MHzと10MHzの長時間試験、および失敗op71のdata長・DMA選択・address・sequenceを記録すること。CRCは緩めず自動fallbackもしない。現時点では高rate margin、DMA境界/切替の未再現問題を区別できず、ジャンパ線限界とは判断しない。

再現はhost repositoryをcwdにして、先にuild/npu-v3-crc-fixtureを作成し、保存した
再現はhost repositoryをcwdにして、先に build/npu-v3-crc-fixture を作成し、保存した run.py をPythonで実行する。scriptは実行時host sourceからframerを抽出するため、結果のsource SHAと今回保存SHAの一致を確認する。巨大な frames.bin は再生成されるがarchive対象には含めない。
