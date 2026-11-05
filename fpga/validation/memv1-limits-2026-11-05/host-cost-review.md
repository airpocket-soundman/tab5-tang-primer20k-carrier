# Tab5側固定費・次候補の読取り分析（2026-11-05）

対象はhost a72b75e、同一firmware/8MHz TX=RX/NEG+preamble1/POS、2slot、retained/full APB restore、compact/fastpack/RXowned/RAMCRC/fixed DATA有効。実装・実機変更なし。基準記録は下記2件で各10000 WR/RD組、20000要求すべてPASS。

- [期待値copy OFF（数学パターン再生成ON）記録](../memv1-dma-stage-cost-2026-11-05/a72-fixed-expected-0-wrrd10000.json)
- [期待値copy全byte照合ON記録](../memv1-dma-stage-cost-2026-11-05/a72-fixed-expected-1-wrrd10000.json)

表の1要求はWR/RD混在平均。phase/transactionはnestedで、waitも他phaseと重なるため全欄を加算しない。worker CPUはproducer/consumerのFreeRTOS実行時間差分の合計で、whole-chip CPU使用率ではない。host USB時間は含まない。完全jobにはARM/準備/全CRC・全byte検証/後処理が含まれる。

|項目|期待値copy OFF（数学パターン再生成ON）|期待値copy ON|単位|
|---|---:|---:|---|
|job全体|1253.048|1183.337|us/要求|
|job throughput|3.268830|3.461397|decimal MB/s|
|同期WR呼出し全体|1116.821|1116.510|us/WR|
|同期RD呼出し全体|998.215|998.321|us/RD|
|producer準備wall|234.174|291.638|us/要求|
|consumer検証wall|148.117|78.570|us/要求|
|worker CPU合計|985.092|973.526|us/要求|

copy ONのjob短縮は69.711us/要求、CPU実時間削減は11.566us/要求。同期転送時間自体はほぼ不変。検証処理をproducer側copyへ移しDMA待ちと重ねた効果と、CPU総量削減を分けて解釈する。

## 同期要求とwire下限

|要求|同期呼出し実測|現在の宣言clock数/8MHz|差分|
|---|---:|---:|---:|
|WR4KiB|1116.510us|517.375us (4115+24 clocks)|599.135us|
|RD4KiB|998.321us|517.625us (19+4122 clocks)|480.696us|

この差分は純粋なCPU時間ではなく、設定・確認・copy・RTOS wake・timer等を含むnon-wire残差。RXはEOF後software stopまでclockが続くため上記clock数は現capture設定に対する下限であり、実測pad波形時間ではない。setupゼロの同条件モデルは平均517.500us/4KiB=7.914976MB/s。実測job3.461397MB/sの上限モデルであり達成保証ではない。8MHz自体の成立は本機/FPGAの資格試験条件に限定される。

## 残るphase（copy ON、混在1要求平均）

|区間|us/要求|解釈|
|---|---:|---|
|TX全体|469.184|以下TX部分を含む|
|TX pack+debug snapshot|35.445|pack純時間ではない|
|TX attach/enable/restore bus|33.139|固定DATA route後もCLK/OE/確認は残る|
|TX submit|33.284|GDMA mount/C2M/Core-FIFO reset/FIFO-ready待ち等|
|TX wait phase|266.784|完了後debug snapshot/phase確認も含む|
|RX configure/end|33.625|保持unitの長さ設定/idle確認等|
|RX flush|76.104|full APB+TX再設定+Core/FIFO等、必須経路|
|RX enable/soft-start/receive/stop|96.279|public lifecycle/queue/cache/IRQ準備を含む|
|RX wait phase|275.868|DMA完了waitのwall|
|RX M2C/copy区間|21.055|同期とcopyは未分離|
|unwrap/copy|12.254|header候補CRC/seq確認を含む|

WR/RD別のphase配列は現JSONに無い。上表を個別WR又はRDの内訳として流用しない。短RD要求TXだけの効果を絞るには同firmwareのread-only workload等で追加phase分離が必要。

## full APBを維持する近接候補

各上限は現在の包含区間を丸ごと消した場合の粗い天井で、実現予測や加算可能な値ではない。必須cache同期・CRC・state確認が残るため実利は必ず区間全体未満。

|優先|候補|混在要求あたり効果上限|主な制約/リスク|wire変更|
|---|---|---|---|---|
|1|producerでpreamble込みDMA payloadを先行準備し中間wire copy/consumer packを外す|約91.2us (=pack35.445 + TX内未分解55.784)|2つのaligned DMA slotと完了までの不変寿命。仕事をproducerへ移すだけならCPU総量は減らない。cache/IRQ/slot所有権維持|不要|
|2|RX configure/endの重複state/mutex確認をscope内だけ統合|33.6us (=両call全体)|確認自体は残す。次要求へidle boolを無条件cacheしない。既存CANCEL/stop失敗/queue残留を拒否|不要|
|3|停止後owned viewをCRC/比較まで保持しpool→raw→replyの成功copyを削減|33.3us (=M2C/copy21.055 + unwrap12.254)|M2Cとheader/body CRCは維持するため実利はこれ未満。次DMA前にview失効、failure raw範囲を厳密化|不要|
|4|RX有限開始/停止をSDK内部で一括化し重複mutex/queue操作を減らす|96.3us区間、configure/end込みでは129.9us区間が天井|mount/cache/Core-FIFO/stop/IRQ等は必須で全削除不可。SDK内部state/PM/error伝播を変えるため中リスク|不要|
|計測先行|定常時のdebug snapshot/詳細phase計測を独立OFF化|現記録からusは分離不能。TX snapshotは4回×7read等|実際の位相/EOF/CRC安全確認は残し、診断履歴だけ分離。上位job時間・CPU実時間・失敗件数を維持|不要|
|低優先|FIFO-ready待ちの分離計測・deadline化|TX submit33.284us全体未満、spin単独は未測定|READY前START不可。IRQ置換で速くなる保証なし。まずhang防止と計測、削除ではない|不要|

公式TX APIは送信完了までpayloadを再利用/変更しない契約。producer/DMA slot案もこの契約を維持する。public queue/ISR/GDMAを再実装する必要はない。[公式TX API説明](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32p4/api-reference/peripherals/parlio/parlio_tx.html)。pinned v5.5.2は実際にGDMA開始後FIFO-readyを待ってからTX_START/clockを開始する。[公式pinned TX source](https://github.com/espressif/esp-idf/blob/30aaf64524299d3bde422ca9a2848090d1bc5d0f/components/esp_driver_parlio/src/parlio_tx.c#L559-L565)。これはspin削除の根拠にはならない。

## 別研究とする候補

- 短RD要求だけGPIO送信：byte formatは維持できるが既存低速GPIO fallbackの単純利用は遅い。8MHz位相/preamble/CLK edge/OE所有権を保つ新transportの波形資格試験が必要。現在の混在phaseから短TXだけのus上限は分離できない。全TX non-wire平均210.8usは非常に緩い包含上限に過ぎない。
- payloadを4KiBより大きくする：FPGA memv1_sys/adapterはMAX_BEATS256、ホストにもbuffer/frame上限がある。コマンド/RTL/buffer/CRC/CANCELと全host要求の変更が必要。既存protocolの単なるパラメータ変更と扱わない。
- 複数TX frameをそのままqueueへ積む：このhalf-duplex MEMは各要求のREADY/DIR切替と応答完了を要する。SDK TX queue深度を増やすだけではrequest/replyの所有権を満たさない。
- persistent RX/level gate/ring：SDKに機能はあるが今回MEMの有限RXでAPBを省くと残counter/短いEOFが実測された。full APB省略を近接案に含めない。新受信mode/VALID gate/descriptor/parser設計と再資格試験が必要で、wire追加信号が要るかも設計依存。[公式RX API](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32p4/api-reference/peripherals/parlio/parlio_rx.html)。

根拠の限界：P4 chip-revision v1.3 TRM §56.5.2はstartup APB→GDMA→Coreとinter-frame Core/FIFO、両clock同期を扱い、§56.7.1はclockOFF→config→UPDATE→START→clockON、§56.7.2はTX ready順序を規定する。『MEMでAPB毎要求が必須』はTRM一般要件ではなく本project実測に基づく現在の制約。Core/FIFO resetやREADY確認を省けばよいとの保証はない。[公式P4 v1.3 TRM](https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_technical_reference_manual_en.pdf)（ローカル D:/tools/espressif-docs/esp32p4-v1.3-trm-en.pdf）。

次の計測では成功したframeだけを選別せず、同firmware OFF/ONの完全jobを比較する。CPU実時間とlatencyを分け、full CRC/全byte照合を弱めて速度改善としない。同期API transfer時間はproducer準備と完全body CRC検証を含まないため、それだけをcomplete-validated MB/sと呼ばない。
