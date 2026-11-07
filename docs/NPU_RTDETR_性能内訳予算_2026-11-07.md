# RT-DETR：V3分割方針の性能内訳予算とV4 coalescing更新（2026-11-07）

これは実際のRQG2形状とV3 backendのloopから計算した基準値であり、実機時間・帯域・予測FPSではない。FPGA RTL、host production、試験中の機器は変更していない。実機終了後のcounter比較用に、[全122 MAC操作のJSON](validation/rtdetr-performance-budget-2026-11-07/budget.json)、[層別CSV](validation/rtdetr-performance-budget-2026-11-07/per-layer.csv)、[再計算script](validation/rtdetr-performance-budget-2026-11-07/calculate.py)を保存した。入力metadata/backend source SHAも記録している。

## 演算とcommand数

方針はConv OC8/OH16/OW16/IC16、MatMulは静的rank2 Bだけleading AをMへ畳み、M≤256/N≤8のmatrix panelを送る。各matrix内部はIC16。動的attentionの8headは別batchにする。

| 項目 | Conv57操作 | MatMul/Gemm65操作 | MAC全体 |
|---|---:|---:|---:|
| host tile command | 217,280 | 0 | 217,280 |
| host matrix panel command | 0 | 13,067 | 13,067 |
| 内部tile実行 | 217,280 | 183,088 | 400,368 |
| 有効MAC | 25,155,993,600 | 4,976,076,800 | 30,132,070,400 |
| engine cycle予算 | 6,416,947,200 | 1,371,736,576 | 7,788,683,776 |
| cycle÷27MHz | 237.664711秒 | 50.805058秒 | 288.469769秒 |

Convの式は `ceil(OC/8)×OH×OW×(2×IC×KH×KW+3×ceil(IC/16))`。Matrixはbatch数×ceil(N/8)×align16(M)×(2K+3ceil(K/16))。M256 panel境界は16の倍数なので、panelごとのpadding和もalign16(M)になる。これは既存8OC engineの通常FSM cycle式であり、DDR loader/staging、upload、host、非MAC、表示・SDを含めない。STA未認定の条件も変わらない。

## データ量の基準

以下はbackendが要求する論理byte数。raw scratchとgraph page cache経由を区別する。全通信量をこの表の足し算から実測値として扱わない。

| byte項目 | Conv | MM/Gemm | 合計 |
|---|---:|---:|---:|
| INT8 qA/input write | 48,087,040 | 25,979,968 | 74,067,008 |
| qA write API呼出し数（旧V3） | 625,280 | 1,623,748 | 2,249,028 |
| qA write API呼出し数（V4 coalescing） | 625,280 | 121,688 | 746,968 |
| 動的INT8 qB write | 0 | 668,672 | 668,672 |
| A row-scale write | 0 | 413,200 | 413,200 |
| A row-scale read | 0 | 10,846,800 | 10,846,800 |
| 常駐B scale read | 44,288 | 65,168 | 109,456 |
| INT32 C read | 171,008,000 | 86,301,600 | 257,309,600 |
| graph FP32出力write | 171,008,000 | 86,301,600 | 257,309,600 |
| FP32 A source read（max+quant） | 362,905,600 | 207,158,400 | 570,064,000 |
| 動的FP32 B source read | 0 | 5,324,800 | 5,324,800 |

Conv qAはIC×H×align16(W)。MM qAはbatch×K×align16(M)で、M paddingもwriteする。guardとして予約した余白はupload量へ数えない。MM qBは動的Bだけbatch×N×align16(K)、静的weightは既にDDRに常駐する。A row-scaleは1回writeし、N8 panelごとにreadする。bias論理readはConv44,288B、Gemm1,331,200Bである。

Cはscratch直通なのでpage cacheを通らない。16B整列したreply payloadへ丸めたC readも、今回の実形状では257,309,600Bで論理値と一致した。別のM/OWでは増える場合があり、calculatorは両方を別計算する。FP32 graph read/writeは4KiB cacheのfill・writebackへ変換されるため、実transport byte数はlogical countと異なる。その他527操作の通信、page eviction、RMW、MEM packet framing、lease/generation照会、cold payload uploadはこの表に含めない。

MAC command自体だけのrequest+replyは0x68で70B、0x78で54Bとして15,915,218B。MEM転送や補助照会を含むwire総量ではない。

## 支配的な層と小packet

| node | 演算/shape | engineのみ | host演算要求 |
|---:|---|---:|---:|
| 10 | Conv 32×320×320→64×320×320、k3 | 17.658秒 | 6,400 tile |
| 8 | Conv 32×320×320→32×320×320、k3 | 8.829秒 | 3,200 tile |
| 13/16/19/21（各） | Conv 64×160×160、k3 | 8.829秒 | 3,200 tile |
| 28/31/33（各） | Conv 128×80×80、k3 | 8.829秒 | 3,200 tile |
| 41/44/46（各） | Conv 256×40×40、k3 | 8.829秒 | 4,608 tile |

旧V3ではMM node225/226/227/228/269等の各qA2,150,400Bに対して134,400回の16B writeを行った。全MM qAの1,623,748回も16B単位だった。これは保存したbudget.json/per-layer.csvの歴史的基準値であり、V4の現行呼出し数ではない。

V4ではqAのM方向を最大256Bへまとめるpackingを採用し、全MM activation write呼出し数は121,688回へ減る（1,502,060回減、92.51%削減）。Conv側625,280回と合わせると746,968回。byte量25,979,968B、matrix panel13,067、Conv tile217,280、演算cycle予算は変更しない。この値はbackend API呼出しの予算であり、cache writebackを含めたwire request実測や速度倍率ではない。V4ではcache容量/last-hitの変更もあるので、効果の測定scopeを揃える。

旧script/JSON/CSVのSHAは保持し、[V4方針追記](validation/rtdetr-performance-budget-2026-11-07/v4-update.json)に新旧件数と根拠を別保存した。V4実機5MHz試験は進行中であり、成功・性能はここでは未確定。

## 実機counterとの照合方法

完了時にexternal Conv57/MM65、backend Conv tile217,280、matrix panels13,067を比較する。transportのtile_jobsがmatrix内部も加える版では400,368が基準で、Conv-onlyの217,280と混同しない。途中停止・失敗時は完了nodeまでのprefix予算と比較する。

現profileはcycle sampling無効なのでkernel/DDR cycles=0は演算時間ゼロではない。また既存CSRのkernel cycleは最後のtile値で、matrix全体のsumとは限らない。7,788,683,776との直接比較には、別途正しい累積測定が必要になる。

実wire read/write、cache hit/miss/flush、TX/RX/READY時間は端末の最終記録と並べる。初期化・検証・SDupload・input・infer・outputのscopeも揃える。V3は最初のConv中op71 CRC status1で停止し全出力なし。CRC監査は別資料に保存した。V4は5MHzで進行中であり、途中値をterminal実測に読み替えない。
