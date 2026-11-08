# FPGA内自律推論 V1（実験的4E30、2026-11-08）

この仕様は新しい隔離topの実装契約であり、4E24を変更しない。実機・全モデル・資源適合の合格は、別の検証結果が出るまで未認定とする。FPGA内RV32IMCソフトコアで非MAC処理を実行し、Conv/MatMulは共通INT8回路を使う。全演算を専用並列回路へ展開した意味ではない。P4はファイル・画像の搬入、操作、結果表示だけを担当する。

## 全ホスト要求との照合

[ホスト調査](NPU_AUTONOMOUS_HOST_REVIEW_2026-11-08.md)とファイルSHA一覧を参照。Linux `cfc9a6e`、MeOS `78274b4`、メモリ研究 `e84b59e`、ESP-IDF `d5eca70`を調査し、dirtyな参照作業木はHEADだけでなく各ファイルを固定した。Linux/MeOSのNPU4E24・自律NPUドライバは未実装。共通の搬入・能力照会・RUN/停止契約は全OSから実装できるが、全OS実機適合済みとはしない。新しいピン・電源・通信周波数は導入しない。DDRはLinuxの透過的なメインRAMではない。

## wire契約

既存v2フレーム、CRC、sequence、session token、epochを使う。`CAPS(0x50)`はこのtopだけ`0x4E30`を返す。4E24の`0x68`と`0x70/71`の意味は保つ。20Kの容量に収めるため、既定4E30には独立した行列積sequencerを搭載せず、`0x78..7D`はUNSUPPORTED（status2）とする。行列積のK/M/NループはFPGA内CPUが同じConv tileへ展開し、積和計算はMAC回路で実行する。RUN中はUNSUPPORTEDよりBUSYを優先し、実行中は演算要求・DDR読書き・再bind・旧clearをBUSYとして拒否する。

- `0x7E CONTROL`は8B、`action:u32, token:u32`。action0は状態照会（token0のみ）、1はSTART、2はABORT、3はCLEAR。変更操作は現在のbind tokenと一致する必要がある。STARTはDDR/両arbiter/MAC/CPUが安全なidleの時だけ受理し、即時応答する。推論完了までwireのREADYを占有しない。
- `0x7F MONITOR`は4Bのselector（0..127）。selectorの下位bitが32bit値のlow/high半分、上位6bitがregister番号。reply valueは16bit。0status、1node、2stage、3app error、4finish、5CPU error、6開始epoch、7run ID、8/9 SYS cycle low/high。未割当registerは0。複数半語にまたがる値は原子的でないため、counterはhigh/low/highで読む。
- statusのbit0はmemory ready、1running、2complete、3error、4quarantine、5trap、6aborted、7start ready。RUN中の照会はsidebandのみで、DDR stagingを使わない。通信が途切れても、空のRX待ちは自律推論を停止しない。
- ABORT応答は停止完了を意味しない。CPUを止め、MACとメモリのcancel/drainが完了するまでrunning/所有権を保持する。quarantineは部分結果を公開せず、ARM/resetによる協調回復が必要。成功FINISHと同時のabort・epoch喪失は成功より優先する。次RUNにはidle CLEARと、プログラム全BIN（変更される.dataを含む）の再upload/readback検証を要する。CLEARだけをwarm restartとして利用しない。

## メモリと実行

モデル定数・arena・MAC scratchは80MiB未満に制限する。programは`0x05000000`、typed metadataは`0x05800000`、RGB8 640×640は`0x05900000`、mailboxは`0x07FF0000`。code/stack/heapの配置はfirmware linkerを正とし、各領域の非重複・128MiB上限を検査する。hostはプログラムをreadback検証し、deviceはmetadata/source/payload CRCとRGB処理を確認してからrun_graphへ入る。

CPUは既存host側DDR master slotを排他的に借りる。host/CPUのheld-toggle要求は既存tagged arbiterで合成し、元のtoggleを直接muxしない。MAC COMMAND storeはCPUを停止させ、data cache flush/invalidate→MAC→最終DDR ACK→invalidateを完了してから応答する。共有stagingはこの間MAC所有。FINISHもmailbox/resultのwriteback完了後だけ公開する。

P4から推論中に中間tensorを読み戻さない。完了後にmailbox・出力tensorだけを読む。許容演算、型、モデル同一性はRQG2/firmware契約による。任意ONNX対応・無期限連続運転・高速化を、この設計記述だけで認定しない。以前のP4/FPGA分担RT-DETRの厳密数値比較FAILも取り消さない。

正規定数は[共通Cヘッダ](../fpga/npu/protocol/npu_autonomous_v1.h)。内部CPU MMIOは[firmware ABI](../fpga/npu/firmware/autonomous/abi.h)であり、wire opcodeとは別物である。ESP-IDF loader実装は本仕様を参照し、Linux/MeOS側への反映版と未実装を検証時に追記する。
