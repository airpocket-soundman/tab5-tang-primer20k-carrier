# NPU DDR Matrix V1：4E24実験仕様

状態：新しい隔離候補。4E23を変更しない。ピン・電源・LINKv2 CRC framing・MEM70/71の意味は維持する。FPGA MatMulだけの候補で、FP32 epilogueや全NNの融合は未搭載。

## 能力と要求

USERCODE00004E24、CAPS4E24を明示照合する。4E20/4E23対応hostから自動選択・fallbackしてはいけない。共通定数は `fpga/npu/protocol/npu_matrix_v1.h`。既存0x75でcaller生成tokenをbindするsession/generation契約を先行し、全DDR領域とcaller leaseを維持する。tokenは各packetへ追加せず既存bound状態を使う。

新0x78 RUN：標準8B headerのarg=36、payload36B、header先頭6BからpayloadまでのCRC16 trailer。全payload CRC確認前に副作用を起こさない。payloadは下表の9個のunsigned32 little endianで、native structのmemcpyをwire形式としない。

| byte offset | フィールド |
|---:|---|
| 0 | M |
| 4 | K |
| 8 | N |
| 12 | A base |
| 16 | A channel pitch |
| 20 | B base |
| 24 | B output-column pitch |
| 28 | C base |
| 32 | C output-column pitch |

M/K/Nは32bitのまま受け取り、1..65535を検査する。high bitsを捨てて小さなjobに変換しない。AはINT8[K,align16(M)]、BはINT8[N,align16(K)]、CはINT32[N,align16(M)]。base/pitch16B整列、A pitch≥align16(M)、B pitch≥align16(K)、C pitch≥align16(M)×4。予約領域pitch×channelを64bitで検査し128MiB内、相互非重複。AのM末尾からalign16(M)はcallerがzero初期化し、Cの同paddingはjob所有。FP32 scale・bias・alphaは含まない。出力はINT32のみ。

RUNは受理後READYが上がるまで待ち、全matrix完了時に標準8B replyを返す。status0/R16=0のみ成功。status1=CRC不正、2=未対応opcode、3=packet長等不正、4=未準備/他owner/busy、5=sequencer失敗（R16=下記code）、7=arbiter/sequence quarantine、8=校正/generation喪失、9=未bind。watchdog失効は既存と同じくpacketを破棄・abort/cancelし、成功replyを返さない。

sequencer codeは1=dimension、2=整列/pitch/容量/count overflow、3=領域重複、4=loader error、5=abort、6=tile timeout、7=memory_ready喪失、8=quarantine、9=最終result/count不整合。C prefixが書かれていてもjob失敗時は全Cを無効とする。seq fault後の0x67はstatus7を返し、DISARMと協調operation resetでのみ再利用する。片側toggleをresetして未完了DDR要求を再生しない。

0x79 STATUS（arg0、payloadなし）のR16：bit0 ready、1 busy、2 error、3 quarantine、4 result_valid、bits8..11 sequencer error code。0x7a/bはaccepted countのlow/high16、0x7c/dはcompleted countのlow/high16。countはjob受理で0へ戻る。完了成功数であり、失敗タイルを成功数へ加えない。STATUS/counter照会もRUN中は受信できない同期endpointなので、別のasync監視チャネルとは扱わない。

## watchdog・所有権

1job=1batchで、N8→M256→K16を自律進行する。受理/完了counterが実際に進んだ時だけMATRIXWAITの1秒watchdogを更新する。busy/ready/doneがhighのままでは更新しない。loader1tileのtimeout/drain/quarantineを残す。matrix jobとlegacy0x68 Conv/MEM requestは同時実行せず、shared stagingとtagged arbiterを既存契約のまま使う。成功reply前に全accepted/completed/expected一致と最終result_validを検査する。

現DeiTの74 MatMulは122batchesなので、この版なら122 RUNとなる。51,468tile commandを削減する設計だが、実測高速化・既存host対応は別途確認する。各RUNに指定したN全体のB/C予約が必要になる。元graphの全Nを1RUNへ渡すなら従来の8列B slab/8192B C scratchは不足する。一方、hostがN≤8・M≤256のpanelごとにRUNを発行し、Kだけ全体をFPGA内部で回す段階的backendも可能で、その場合はjob局所Nに応じた既存slab/C scratchを使える。122jobsへ減ったと主張せずpanel job数と内部tile数を分けて記録する。

## 参照とhost影響（2026-11-07）

Linux cfc9a6e：README、DEVELOPMENT_GOALS、tab5-overrides.dtsi、fpga_link.cを確認。parallel batch/streamのPC試験はあるが新NPU matrix API・PARLIO/GDMA物理動作は未実装/未認定。MeOS78274b4：README、FPGA_CARRIER_REQUIREMENTS、fpga_parallel_app.c/fpga_npu_app.cを確認。NPUはCPU arithmetic referenceで、carrier NPU jumper command未実装と明記される。研究e84b59e：Project_Aの外部DDRは明示管理アクセラレータでありLinux RAM増設ではないことを照合した。

ESP-IDF ca12308：README/Project_B、npu_ddr_transport.cppを確認。既存はCAPS4E20/op68固定で、新4E24用backendは主担当が別途明示実装する。Linux/MeOSの既存binaryで本bitstreamが動くとは扱わない。能力不一致を明示失敗にし、OS共通のwire/範囲/lease仕様とする。GFX/MEM機能の仕様やpinは変更しない。新host backendの反映commitと実機証跡は試験完了後に追記する。
