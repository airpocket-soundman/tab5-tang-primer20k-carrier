# NPU-DOT-v0（Dock診断用、2026-11-06）

GFX/MEMと別のNPU単独ビットストリーム。USERCODE 4E02（修正版、能力値は4E01）、sys_clk27MHz、DDRなし。既存Dockピン・電源・8byte LINK v0フレーム/CRC16/sequence/version2を維持する。通信はまずGPIO低速で検証し、高速DMA対応は別段階。LINK_ID=5054だけでは種別を判断せず、必ず50hへvalue0を送り4E01hを確認する。MEMとopcode領域が重なるがビットストリームと能力値が異なるため混用禁止。タグ付きDMA未評価。

|opcode|操作|value/応答|
|---|---|---|
|50|能力|value0のみ、応答4E01|
|51|設定byte書込み|low=offset0..20、high=byte。全21byteの設定が必要|
|52|内積開始|value0。設定をlatch、length0..1024|
|53|1組投入|low=signed activation、high=signed weight。受理後ACK|
|54|INT8結果を取得・消費|value0。符号拡張16bit。未完了は有限待ち、失敗時結果なし|
|55|中断・リセット|value0。設定済みmaskも破棄|
|56/57|job cycle下位/上位|value0、未消費の正常結果がある時だけ|
|58/59|compute cycle下位/上位|同上。STREAMの入力待ちと結果読出し待ちを除外|
|5A/5B|正常INT32累積の下位/上位|同上。54より先に読む。失敗時の部分和は返さない|

設定byteはlittle endian：0..3 bias INT32、4..7 multiplier非負INT32、8..9 input_zero_point INT16（-128..127のみ）、10 shift（0..62）、11..12 output_zero_point INT16（INT8範囲）、13..14 lower INT16、15..16 upper INT16、17..20 length UINT32。丸めは既存REQUANTIZE.md、INT32加算overflowは失敗。length分のsampleが必要。

statusは0成功、1CRC/フレーム不良、2未対応、3不正設定、4状態不整合、5accumulator overflow、7コマンドwatchdog。コマンド待ちは1024SYS cycleで打切り、dotをresetし設定maskも破棄。LINK idle100ms、DISARM/resetでもjob/configを破棄。正常job_cycleは開始から結果までのhost sample間隔を含む。compute_cycleはハードウェア内の活動cycle集計で、連続供給時のFmaxや単独演算レイテンシの実測値とは区別する。

パケット送受信・整合性異常でhostはDISARMし、暗黙retryやCPU fallbackはしない。正常CPUとFPGAのINT32/INT8を照合する。これでWholeBody全graphや校正済INT8モデルを実行できるわけではない。

## 全ホスト適合レビュー

ESP-IDF a0ef922のREADME/Project_B/通信・表示・推論、Linux cfc9a6eのREADME/DEVELOPMENT_GOALS/DT（FPGA driver未実装）、MeOS78274b4のREADME/FPGA_CARRIER_REQUIREMENTS/通信・CPU NPU参照、研究e84b59eの計画を確認済み。今回のwireはOS依存ポインタ・DMA descriptorを含まず全ホストで実装可能。GPIO/電源はDock仕様のまま。ESP-IDFへ診断APIを追加、Linux/MeOSは対応driver/診断commandの追加が必要で今回未反映。OS横断での実機合格は主張しない。carrier用電気条件の承認をDock試験で代替しない。


開始ACKはjob受理であり最終演算成功ではない。dot内部で不正parameterを検出すると後続操作はstatus3、overflowではstatus5を返す。正常結果が無い時は累積値を公開しない。初版4E01の累積読出しはoverflowをstatus4へ分類する不備があり、4E02で修正した。

ESP-IDF診断JSONは既存USB行上限1024byteに合わせ128pair/1jobまで。回路のlength上限1024と区別する。
