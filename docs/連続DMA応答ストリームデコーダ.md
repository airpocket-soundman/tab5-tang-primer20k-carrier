# 既存応答の連続byteストリーム検証器

2026-11-03。`fpga/host/link_stream.h`は既存LINK/ROW/TILE応答を観測済みbyte列から探す、portable C/C++共通ヘルパー。FPGA RTL、GPIO、CRC、コマンド、prefixは変更しない。連続DMAそのものや、実機のFIFO問題を解決したという意味ではない。

## インターフェース

```c
link_stream stream;
uint8_t window[4096];
link_stream_begin(&stream, request, body_bytes, previous_accepted_end,
                  sizeof window, window, sizeof window);
link_stream_feed(&stream, actual_absolute_offset, actual_bytes, actual_count);
/* 呼出側が決めて記録した有界tailまで観測してから閉じる */
if (link_stream_finalize(&stream) == LINK_STREAM_UNIQUE) {
    const uint8_t *body = link_stream_body(&stream);
    /* 必要なら既存出力bufferへbody_bytesだけcopyする */
}
```

bodyは成功応答の8/74/2058byteを指定し、要求opcodeとの一致を検証する。beginは要求のmagic/length/CRCを検証してコピーする。prefixやidleを補わず、入力windowには実際に渡されたbyteだけを保持する。エラーstatusの応答は成功候補にならず、NO_MATCH等で失敗する。エラー応答の別デコードは本ヘルパーの範囲外。

呼出側が所有するwindowを使い、heap確保や内部の巨大byte配列はない。最大window長はbeginの引数で明示し、capacity超過は拒否。初回feedのabsolute offsetはfenceの前後どちらでもよい。以後は各chunkが重複も欠落もなく連続することを要求する。fenceより前のbyteだけを捨て、その後の保持byteがwindow上限を超えればOVERFLOW。offset加算の64bit overflowも拒否する。

| 結果 | 意味 |
|---|---|
| NEED_MORE | まだ完全な成功bodyが見つからない |
| CANDIDATE | 現在1候補だが、windowが閉じるまでは採用不可 |
| UNIQUE | finalize後、観測した有界window内に完全な成功bodyが一つだけ |
| NO_MATCH | finalize後、完全な候補なし |
| AMBIGUOUS | 異なる開始位置に完全な候補が二つ。最初を選ばない |
| OVERFLOW | byte数・capacity・absolute offsetの上限超過 |
| GAP | chunkの欠落、再送、重複、逆行 |
| INVALID | 不正要求・body長・引数、または閉じたwindowへの追記 |

feedはUNIQUEを返さない。後続chunkに二つ目の有効bodyが来る可能性があるため、CANDIDATEを画像に使わない。finalizeは呼出側が定義した観測区間だけを閉じる。将来の無限ストリーム全体での一意性を主張しない。body pointerはUNIQUE後のみ取得でき、window再利用まで有効。matched_offset/matched_endは、header先頭から末尾CRC直後までのabsolute offsetを返す。

## DMA側の契約

- ヘルパーはtask側で一つの所有者から呼ぶ。ISRは完了descriptorを、寿命の保証されたstashへコピーしてから公開する。DMA ring pointerを後で読む前提にしない。
- 同時に一要求だけを待ち、次のwindowのfenceを少なくとも直前に採用したbodyのendへ進める。descriptor途中に残った古いidle/sampleが次のcallbackに現れても、以前のbody開始位置を再採用しない。8bit seqが周回して同じ値になってもfenceを維持する。
- DMAのbyte-stream absolute offsetはセッション内で単調増加。unitを破棄して新しいセッションを始める時は、offset/fenceの世代も明示的に初期化する。古いfenceを新しいoffset0へ流用しない。
- 要求seq/op、成功header CRC、ROW/TILEのmetadataと全payloadを束ねるCRCが一致する、完全で連続したbodyだけを候補にする。欠けたbyteの復元、CPU画像への置換、CRCの作り直しは行わない。
- 観測windowの閉じ方（READY低下、候補後の最大1descriptor tail、最大raw byte数、deadline等）はtransport側が決めて記録する。追加sampleはprotocol byteに数えない。stash overrun、FIFO overflow、timeoutは失敗であり、parserにゼロ埋めして渡さない。

## 検証

`test_link_stream.py`は独立Python参照モデルが作ったID、非一様な色/ZのROWとTILE両planeを使う。C11とC++17それぞれ80002 assertion合格。全byte境界での2分割、chunk長1/2/3/7/8/31/127/128/129/255/256/257/512/1024、全body byteの破損・削除、CRCを再計算した不正seq/plane、重複・重なった二候補、fence前の古い同一seq応答、255→0周回、gap・offset逆行・上限超過を検証する。実機・DMA driverの成功を示す試験ではない。
