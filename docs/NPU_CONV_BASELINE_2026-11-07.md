# YOLO全Convの実機基準点（2026-11-07）

USERCODE4E11/cap4E10のNPU単独版をSRAMへ書き込み、Tab5の小型YOLO全186Convを処理した。全661operatorのうち非ConvはP4 FP32で実行。最終[1,29,420]全12180値がCPUの同じdynamic INT8 Conv方式とbit一致。P4のSDに3画像・2解像度モデルを配置し選択UIで表示した。host checkpoint802e169。

本版はBRAMタイルとP4上の小型モデルによる基準点で、DDRresidentの大容量モデル推論ではない。ユーザーの最終目的はPSRAMへ一括loadできないモデルをFPGA128MB DDRで処理すること。次の実装はmetadataのみP4・重み/activation DDR・DDR tile DMA・非Convの固定scratch streamingである。

## 回路と試験

- conv_tile_engine：signedINT8、kernel1/3、stride1/2、IC16 block、OC8、16×16、端数・groupはhost分割。入力のpaddedhaloとOIHWweightをsequentialuploadし、IC block間のINT32を保持。正常finalblock完了まで結果を公開しない。overflow/abort/異常は破棄。
- 2156 blockのRTL oracleに合格。最大形状・真の正負INT32境界越え・不正upload/reset等を含む。
- 6job/101packetのpin-levelCRC試験に合格。2048B upload、256word read、CRC不良時無変更、truncatedpacket、timeout、OE/reset/disarmを含む。
- 実機2454出力selftestが一致。IC17、OC9、group4、DFL幅420などを含む。
- SYS27MHzで配置配線済み。旧4E10はconfigfault分類修正前の候補、実機採用は修正後4E11。実レポート・ソースsnapshotを保存する。GPIO外部setup/holdと高速DMAは本版未認定。

128×160 crew実測はFPGA＋P4推論47.705秒、CPU INT8 7.761秒、CPU FP32 3.892秒。TX22.533秒、RX16.094秒、READY5.298秒。現GPIO版はCPUより遅い。旧GFXのTX20/RX16をこのPHYへ流用せず、単一laneのcorecyclesをend-to-end速度と混同しない。

## LINK（実験版）

既存8byte LINK v2 header（A5,op,seq,2,arg16,CRC16(header6)）を使う。extendedrequestはarg=payloadbyte数、payloadの後にheader6+payloadのboundCRC16を付ける。正常READ返信もheader8+payload+boundCRC。その他は8byte返信のみ。highbitタグは未対応で拒否する。

|op|操作|payload/応答|
|---|---|---|
|01|ID|arg0、5054|
|50|NPU能力|arg0、4E10。MEM/GFXと混用禁止|
|60|tile設定|9byte:IC,OC,OH,OW,k,stride,haloH,haloW,flags(first/final bits)|
|61|stagedupload|kind0input/1weight、address16、data最大2048B。CRC検証後だけengineへ反映|
|62|実行|arg0、block完了後ACK。非finalはpartial非公開|
|63|正常結果read|baseword16,countword16(1..256)。返信value=count、INT32LE payload|
|64|状態|arg0|
|65/66|core cycles low/high|arg0、直近block|
|67|abort/clear|arg0|

status0正常、1frameCRC、2unsupported、3invalidparam、4state、5overflow、timeoutはidle破棄。全cfgはbyte幅のまま範囲検証しport幅への切詰め前に拒否する。失敗時hostはDISARMしretry/fallbackしない。詳細kernel契約はfpga/npu/rtl/CONV_TILE.md。

## ホスト影響

ESP-IDF802e169の通信・表示・推論を実装/実機検証。Linuxcfc9a6eのREADME/goals/DT（FPGA通信driverなし）、MeOS78274b4のREADME/FPGA要求/CPU NPU参照、研究e84b59eの計画を前段から継続照合した。今回pin/電源は変更しない。wireはOS固有pointerを含まないが、Linux/MeOSの新NPU Conv driver追加は未反映・実機未検証。capability4E10を必須にし、既存device仕様との誤用を防ぐ。

[bitstream/実機・RTL原記録](../fpga/validation/yolo-conv-baseline-2026-11-07/)。DDRloader/arbiter/externalgraphは別の未統合段階として管理し、この保存点の合格に含めない。
