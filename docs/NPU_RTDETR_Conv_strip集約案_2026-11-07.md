# RT-DETR Conv要求のstrip集約案（2026-11-07、未実装）

V4の最初のConv終了は主担当の途中記録で約99.17秒。これは演算・host変換・DDR・通信を含むscopeであり、batch化による短縮可能時間ではない。本資料は既存4E24を変更せず読んだ実装案。機器、production source、protocolは変更していない。

## 現在の要求経路

host `npu_ddr_transport.cpp::tile`は52B descriptorをop68で送る。request62B+response8B=70B/IC tile。`conv_exchange_bounded`はDIR/入力出力切替とguard、GPIO TX、READY待ち、8B reply CRC、DIR戻しを毎回行う。op68はDMA TX対象ではない（現在DMAはop71のみ）。READY確認はGPIO level pollingであり、追加status packetではない。counter sampling Disabledならtile後のstatus/cycle packetもない。Full samplingの0x65/66/6b/6c照会は現V4条件の費用へ加えない。

FPGAはCONVWAITでloader完了を待ってreplyする。現hostはOC8→Y16→X16→IC16をループし、IC最終blockで8KiB tileをDDRへ出し、P4がINT32 read/FP32 dequant/bias/writeする。集約しても現時点のP4変換は残る。

## 推奨する最小の有効段階

[全57層の件数](validation/rtdetr-conv-strip-proposal-2026-11-07/counts.json)は保存済み層別shapeから独立計算した。

| 案 | RT-DETR全Conv要求 | 最初のConv要求 | 特徴 |
|---|---:|---:|---|
| 現IC16 tile | 217,280 | 1,600 | 現4E24 |
| IC loopだけFPGA | 23,648 | 1,600 | IC3の初層には効果なし |
| OC≤8/OH≤16/fullOW strip | 4,656 | 80 | XとICをFPGAへ、推奨する狭い次段 |
| 全層Conv sequencer | 57 | 1 | OC/Y/X/IC全部、host出力処理も広い変更 |

stripはlegacy比97.86%要求削減。処理するMAC/内部217,280 tileは変わらず、速度倍率の予測ではない。初層では有効演算cycle予算0.8647秒に対して実際の約99秒はscopeが広く、差分すべてをcommand overheadとは解釈できない。初層INT32出力13,107,200BをP4へ読み、同量のFP32を書き戻す費用も残る。

## 既存loaderで可能な形

jobごとにOC≤8、OH≤16、出力全OWを指定。内部はX16の各tileについてIC16を全て走らせ、first/finalフラグと既存INT32累積を保つ。最終ICのoutput_baseだけ `strip_base+x*4`、output_row_pitch=`align16(OW*4)`、output_channel_pitch=`OH*row_pitch` とする。input origin Xはjob origin X+x*stride、input_baseはIC block分、weight_baseはIC block×k²分だけ進める。OC blockのweight/input各baseはhostが選択する。k1/3、stride1/2、paddingは既存loaderが担当し、新MACは不要。

P4はstrip完了後に同じ論理位置のINT32を読み、既存と同じFP32式で出力する。最大strip DDR scratchは現RT-DETRで163,840B（8×16×320×4）。現8,192Bから155,648B増えるがBRAM追加は不要。scratchは現在の61.8MB空き内へ専用割当し、graph arena/weights/qAと非重複検証する。出力paddingはcaller所有、各row16B alignmentを守り、未所有tailを書かない。全層出力を別に確保する必要がない。

## wire/資源/安全性のreview事項

新command・capabilityが必要。既存4E24/op68/op78の意味を変えず、新candidateのみで明示選択しfallbackしない。未確定payload案は18×u32=72B（IC/OC/OH/OW、kernel/stride、IH/IW、signed originY/X、input base/row/channel pitch、weight base/OC pitch、output base/row/channel pitch）。これは提案でありopcode・ABIはまだ確定していない。最小field幅へtruncateする前に全幅を検証する。request+replyはこの案なら90B/strip、全4,656stripで419,040B対legacy15,209,600B。ただしMEM/guard/READY時間を含むwire総量ではない。

SYSと同じclockのFSMを既存matrix sequencerと排他のloader ownerへ接続。4E24 Logic14,193/20,736、BSRAM45/46なのでpacket storageを共有し追加RAMを避ける。既存matrix sequencer単体2,381Logicは参考で、Conv追加FSMの実測値ではない。独立controllerを単純加算した16,574Logicもfit保証ではなく、FP32 epilogue等との同時搭載は再合成/PNRが必要。現在STA未認定を継承する。

必須proofは64bitの全span/積/128MiB範囲/非重複、kernel/stride/形状妥当性、signed origin overflow、部分OC/IC/X/Y、retained accumulation、padding ownership、既存CMDの排他、CRC不正時無発火、session/generation、DISARM/abort/drain/quarantine。timeoutは実accepted/completed tile eventのみ進捗として延長し、busy/done sticky levelで無限延長しない。1tile timeoutと全strip host上限を別々に定義する。既存60秒bounded交換はop78専用なので、新commandに無断流用しない。

実装順は独立sequencerのdescriptor+INT64 oracle→実loader/DDR mock pin proof→新capability/topの合成・STA→主担当の明示実機選択。RTL・protocol変更前に全host参照版と未実装対応を既存参照ルールに従って記録する。最終目標のFPGA epilogue/隣接演算連結は別段階であり、このstrip案だけで全NN中間値のP4往復は消えない。
