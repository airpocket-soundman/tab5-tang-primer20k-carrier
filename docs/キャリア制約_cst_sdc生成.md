# キャリア基板用 .cst / .sdc の生成と照合

2026-11-04。ブランチ `claude/track-h-carrier-cst`。オフライン作業のみで、実機・基板は未確認。ピン・仕様は変更していない。

## 成果物

| ファイル | 内容 |
|---|---|
| `fpga/tools/generate_carrier_cst.py` | `kicad/core_pin_assignment.csv` から `.cst` を生成する。`--check`で最新性を検査、`--require-verified`は未確認のバンク電圧がある間は拒否 |
| `fpga/tools/kicad_pcb_nets.py` | `.kicad_pcb`からCoreソケットのパッド→ネットを読む（KiCad不要） |
| `fpga/tools/test_generate_carrier_cst.py` | 生成物とKiCadピン表・PCB・チップDBの一致を検査（12件） |
| `fpga/constraints/carrier/tab5_carrier_link.cst` | 生成結果（LINK、AUX、LED、ボタン、EXT、PMOD、GPIO。46信号＋`sys_clk`） |
| `fpga/constraints/carrier/tab5_carrier_link.sdc` | 雛形。有効行は`sys_clk`だけ。外部I/Oの制約は未検証の仮値としてコメントアウト |
| `fpga/constraints/carrier/gw2a18_pg256_ball_table.json` | ボール→IO名・バンク。Apicula（チップDB）から作成、ハッシュ付き |

HDMI（TMDSとHPD/HSCL/HSDA）とDDR3は対象外。Dockのジャンパ試験用`fpga/constraints/dock/`とは別物で、ボールもバンクも異なる（CLKはキャリアK14／DockはT7）。

```powershell
python fpga/tools/generate_carrier_cst.py            # 再生成
python fpga/tools/generate_carrier_cst.py --check    # 最新か検査
python fpga/tools/generate_carrier_cst.py --refresh-ball-table   # apycula が必要（通常は不要）
python -m unittest fpga/tools/test_generate_carrier_cst.py
```

## 導出の経路と照合結果

`信号 → SODIMMピン（KiCadピン表）→ FPGAボール（Sipeedピンマップの第3項）→ IO名・バンク（Apicula）`

| 照合 | 結果 |
|---|---|
| ピン表CSV 57信号 と PCBのCoreソケットのパッドのネット | 57/57一致 |
| ピンマップ中のボールがGW2A-LV18PG256C8/I7に存在 | 全信号で存在 |
| ピンマップのバンク表記 と Apiculaのバンク | 全信号で一致 |
| ピンマップのIO名 と ApiculaのIO名 | SODIMM 50/52/77/79の4件だけ不一致（下記） |
| 生成した`.cst`のボールの重複 | なし |
| K14 | GCLKT_1（Dock資料の記載と一致） |

## 矛盾・要確認事項

1. **バンク0/1/7の電圧が基板では確定しない（最重要）。** キャリアのPCBは、バンク電源のSODIMM 164/166（VCCO0&1）と170/174（VCCO7）に何も接続していない。バンク0/1が3.3Vになるのは**Core上のR5が+3V3側に実装されている場合**、バンク7は**R9が実装されている場合**だけで、Core実物の実装は未確認。Dockは164/166へ+3V3を入れるため、この問題がDockでは出なかった。`.cst`の`IO_TYPE=LVCMOS33`は仮の前提。`--require-verified`はこの確認が済むまで拒否する。確認する場合は、Coreの抵抗実装の実測（または回路図・実物の確認）が必要。PCBが164/166/170/174に接続された場合は、試験が失敗して`BANK_VCCO`の再検討を促す。
2. **データバスがバンク0/1/7にまたがる。** D0〜D2はバンク0、D3・D4はバンク1、D5〜D7とDIRはバンク7。Dock試験は`D0〜D7`をバンク2/1/0、使わないとしたバンク7は含まない。ジャンパ試験でバンク7の信号は未検証。
3. **旧記述との不一致（訂正済み）。** Dock資料の「キャリアではデータはSODIMM 73〜91」は、`kicad/gen/design.py`の`CORE_PINS`リテラル（ピンスワップ前の初期表。39信号が最終と異なる）に基づく。最終は`_apply_pin_swap()`後の`kicad/core_pin_assignment.csv`で、PCBと一致する。F_D0〜F_D7は77/83/85/103/101/109/107/115。該当行を訂正した。`design.py`のリテラル自体は初期表として残る。
4. **Sipeedピンマップのラベル4件でIO名が古い。** SODIMM 50（K15）、52（K14）、77（F13）、79（G12）。ボールとバンクは正しく、生成にはボールのみを使い、IO名はApiculaから取る。試験が、この4件だけが不一致であることを固定している。
5. **Dock専用の資源がキャリアにない。** `reset_n`（Dock Key_0、T10）と`arm_sw`（Dock DIP SW0、C7）。キャリアにはボタン1個（F_BTN0）と、ハードウェアのバスARM（JP1）があるのみで、FPGAのarmピンはない。`.cst`にはTODOコメントだけを置いた。RTLトップの扱い（リセット源、ARM）は、キャリア用トップ設計時に決める。
6. **属性（PULL_MODE、DRIVE）。** `bus_clk`、`dir`、`ready`、`data[*]`はDockの値を流用（キャリアで未検証、行に明記）。AUX、LED、ボタン、EXT、PMOD、GPIOは未決定のためIO_TYPEのみ。LEDの極性はキャリア回路で未確認（Dockは負論理）。
7. **機能ピンの兼用。** F_DIR（C12）はLPLL1_T_IN、F_EXT35／F_D7（A14／B13）はPLLのFB、P1_3（B12）はLPLL1_C_INを兼ねる。このPLLを使う設計では競合する。現行RTLでは問題にならないが、キャリア用トップでPLLを使う場合は割り当てを見直す。
8. **SDCは雛形。** 現行RTLは`bus_clk`をデータとして`sys_clk`で取り込み、クロックとして使わない。ソースシンクロナス前段が実装されるまで、`bus_clk`のクロックと`set_input_delay`は無効のまま。入力遅延2.0／0.5nsは**未検証の仮値**。導出には、P4 PARLIOの出力スキュー、キャリアの配線遅延、Coreの配線長（`Core_3690_Net_Length.xlsx`）が必要。ジャンパで検証済みの最高通信周波数は20MHz（SoC最大は40MHz）。

## ホスト側への反映

ピン・信号・仕様は変更していないため、tab5-fpga-gpu、tab5-meos-fpga、tab5-linux-fpgaへの反映は不要。Dock資料の訂正（上記3）は記載のみで、ホスト側の定義には影響しない。

## 検証

- `python -m unittest fpga/tools/test_generate_carrier_cst.py`：12件合格。
- Gowin EDAやnextpnrでの読み込み・配置配線は未実施（キャリア用トップが存在しないため）。
