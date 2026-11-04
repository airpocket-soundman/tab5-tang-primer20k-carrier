# ホスト共通codec

ソフト実装の入口は[Tab5ホストソフト開発ガイド](../../docs/Tab5ホストソフト開発ガイド.md)。codecが担う範囲と、OS別transport・描画・LCD処理を分けて記載している。

`link_protocol.h`は`dock-gfx-v0`のC参照codecの正本。CRC-16/CCITT-FALSE、固定8バイト、LINK op1〜3とGFX op0x10〜0x16を扱う。

LINK codecは同一所有者の`tab5-fpga-gpu d4d89e3`の`bringup/tab5/main/link_protocol.h`を基に抽出・拡張。元ファイルにライセンス表記なし。ライセンスの付与・変更はしていない。

ESP-IDFホストは`tab5-fpga-gpu/bringup/sync_carrier_codec.py --carrier <このリポジトリ>`で同期し、`--check`で内容とSHA-256を検査する。
OSのGPIO、DMA、LCDコードは各ホスト側に置く。

`link_validate_response`は成功status・CRC・sequence・形式を検査し、ID／echo／反転・GFX応答の既知データを照合する。
READの画素値は呼出側が期待画像と照合する。CRCが正しくても描画結果の正しさを保証しない。

Cコンパイラを使った試験（`fpga/`で実行）:

```text
python -m unittest discover -s host/tests -p "test_*.py"
```

コンパイラがない場合はCのテストだけskipする。擬似シリアルの試験は機器を開かずに実行できる。

`mem_v1.h`は**MEMV1**（DDR3の明示的READ／WRITE／CRC32、opcode 0x60〜0x67）のCコーデック。仕様は[MEMV1プロトコル仕様](../../docs/MEMV1_プロトコル仕様_v1確定案_2026-11-05.md)。確定案で、実機・ホストOS側は未検証。`fpga/mem/tests/memv1_model.py`の独立なPython参照モデルと`fpga/host/tests/test_mem_v1.c`でバイト単位に照合する。
