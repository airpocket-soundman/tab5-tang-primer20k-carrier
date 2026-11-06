# r5s: スライドスイッチ(B案)版 USB-JTAG基板

現行 r5(`spark/usb-jtag-r5/`)のコピーから、RUN/PROGRAM切替の **JP2 と JP4 を1個のDP3Tスライドスイッチ SW4 に置き換えた** 新バリアント。
現行r5とC案(`spark/usb-jtag-r5-ovp/`)は変更していない(読み取りのみ)。設計・机上検証の段階で、実機検証・製造データは無い。

## 目的

r5 で危険な組合せは「JP2=PROGRAM(2-3) かつ JP4=RUN(1-2)」(PD充電器の VBUS=12V が Core の 5V に入る)。
JP2 と JP4 を1個のスイッチの2極で動かし、この組合せを構造上なくす。

## 変更点(r5 との差)

| 項目 | r5 | r5s |
|---|---|---|
| JP2(BUCK_5V / +5V / VBUS_PD) | 1x3ピンヘッダ | 削除(SW4 極Aに統合) |
| JP4(GND / PD_CFG1 / PD_VDD) | 1x3ピンヘッダ | 削除(SW4 極Bに統合) |
| SW4 | なし | G-Switch SS-23D03-G080(LCSC C2848921, DP3T, 1A/24V, THT, JLCPCB extended, 手はんだ/波はんだ) |
| JP3(VIN / TAB_HVIN) | 1x3ピンヘッダ | そのまま(SW4 とは**連動しない**) |
| 他の部品・配線 | - | 変更なし(r4/r5確定内容は維持) |

BOM: `full/design/kicad/bom-r5s.csv`(150部品。r5 から JP2/JP4 を除き SW4 を追加した差分のみ。LCSC番号は r5 のBOMから引き継ぎ)。

## 機能割当て(位置1=RUN、位置2=中央=安全位置、位置3=PROGRAM)

| スイッチのパッド | 極 | 役割 | ネット |
|---|---|---|---|
| pad4 | A 共通 | | +5V |
| pad1 | A throw1 | RUN | BUCK_5V |
| pad2 | A throw2 | 中央(どこにも接続しない) | NC |
| pad3 | A throw3 | PROGRAM | VBUS_PD |
| pad5 | B 共通 | | PD_CFG1 |
| pad8 | B throw1 | RUN | GND |
| pad7 | B throw2 | 中央(どこにも接続しない) | NC |
| pad6 | B throw3 | PROGRAM | PD_VDD |
| pad9 / pad10(各2個) | 取付 | シールド | GND |

| 位置 | +5V につながるもの | PD_CFG1 につながるもの | 意味 |
|---|---|---|---|
| 1 (RUN) | BUCK_5V | GND | 12V要求(CH224K)、Core は降圧 5V |
| 2 (中央) | なし | なし | 全開放。PDは5V要求(CFG1開放)、Core 5V は無給電 |
| 3 (PROGRAM) | VBUS_PD | PD_VDD | 5V要求、USBのVBUSからCoreへ |

JP2 と JP4 が同じスライダで動くので、「VBUS_PD→+5V かつ PD_CFG1→GND」は成立しない(`verify_design.py` で位置モデルを検査)。

## 実物確認が必要な項目(未確認)

- **pad1/8、pad2/7、pad3/6 が同じスライダ位置で揃って動く**という前提は、EasyEDA の記号図からの推定。部品実物で導通確認が必要。
  またスライダのどの端が「位置1」かも実物で確認する(基板のシルクは `RUN`(下)/`OFF`/`PGM`(上) だが推定位置)。
- 共通 pad4/pad5 が、3つの位置で pad1-3 / pad8-6 のどれと導通するか(ショートする順序、中央位置が本当に全開放か)。
  切替時に一瞬 2 つの throw が同時に閉じる(make-before-break)品種だと、BUCK_5V と VBUS_PD が瞬間的につながり得る。必ず確認。
- 定格 1A/24V に対し、+5V 経路(Core 0.5A+デバッガ)の電流余裕。接触抵抗による電圧降下。
- 取付パッドの穴径(1.4mm)と本体寸法(16.0 x 6.7mm)は EasyEDA 公開データ。メーカー図面での再照合が未了(SS-23D03 のデータシート PDF との突合せは未実施)。

## 配置(SW4)

- 座標 **(43.2, 11.0) mm、回転 90 度**(縦置き)、表面(F.Cu)。
- 理由: 本体 16.0 x 6.7mm(取付パッド込み 17.5 x 8.2mm)は、JP2(x=39)〜JP4(x=47)の位置(y=26..31)には収まらない。
  横置きでも縦置きでも R88-R90、Q7、JP3、R41、+5V 幅広配線(x=49.38)などと干渉する。
  基板全体を 0.5mm 刻みでパッド(穴を含む全層)対銅箔クリアランス走査した結果、**縦置き(90度)で (43〜44.5, 10.5〜11.5) 付近だけが既存銅箔と干渉しない**唯一の領域。
  H3(M3取付穴, (51.06, 3.95))のコートヤードとも干渉しない位置として (43.2, 11.0) を採用。
- 干渉する主な既存物(他の位置・向きの場合): B.Cu の F_BTN0(y=9.0 の横配線), In2 の TAB_RST(対角線 (36.4,11.2)→(49.3,24.1)), +5V(F.Cu x=49.38), JP3 パッド, R41。
- 旧JP2/JP4位置との距離: 旧パッドのあった y=26..31 まで約 12〜20mm の再配線が必要(下記)。

## 配線変更

- 旧 JP2/JP4 のパッドは F.Cu/B.Cu/In2 の乗換点でもあったため、同位置にビアを追加: +5V (39.0, 28.54)、PD_CFG1 (47.0, 28.54)、PD_VDD (47.0, 31.08)。VBUS_PD は In2 の既存対角線の交点 (39.0, 31.08) に新規配線を接続。
- 削除した既存銅箔: BUCK_5V の F.Cu 0.25 の行き止まり1本 (39,26)-(38.15,26.85) のみ。その他の既存配線は変更なし。
- 追加した銅箔: SW4 の5ネット(BUCK_5V, +5V, VBUS_PD, PD_CFG1, PD_VDD)の配線とビア(`gen/add_sw.py`, `gen/sw_routes.py`、A*ルーター `gen/maze.py`)。
  電源系は 0.5mm、PD_CFG1/PD_VDD は 0.25mm。In2 の GND 面を分断しないよう、VBUS_PD 以外は F.Cu/B.Cu のみ使用。
- 取付パッドとpad8(GND)は各層の GND ゾーンに接続。
- `gen/diff_nets.py` で r5 との差を確認: 削除/ネット変更された既存銅箔は上記1本のみ、再ネットされたパッドは JP2/JP4 の6パッド(削除分)のみ。

## 検証結果(`full/design/kicad/sim/` 内、同一環境で実行)

| 項目 | 結果 |
|---|---|
| ERC (`kicad-cli sch erc --severity-all`) | エラー 0 / 警告 210(lib_symbol_mismatch 207, isolated_pin_label 3)。r5 基準は 205+3。差の +2 は電源シンボルの個数の違い |
| netlist (`sch export netlist --format kicadxml`) | r5 との差は JP2/JP4 のピンが SW4 の pad に置き換わっただけ(+5V=pad4, BUCK_5V=pad1, VBUS_PD=pad3, PD_CFG1=pad5, PD_VDD=pad6, GND=pad8/9/10, pad2/7 は NC) |
| DRC (`pcb drc --severity-all --schematic-parity`) | 違反 0 / 未配線 0 |
| schematic-parity | 466 件(footprint_symbol_mismatch 152 / footprint_symbol_field_mismatch 115 / net_conflict 199)。r5 基準(実測)は 469 件(154 / 116 / 199)。**増加なし**(SW4 の FPID は `carrier:SW_SLIDE_DP3T_SS-23D03-G080` に設定済みで footprint_symbol_mismatch は出ない) |
| r4 保存ファイル | `../usb-jtag-r5/preserved-r4.json` の 1234 件のハッシュ一致(変更なし) |
| `verify_design.py` | 配線契約 PASS、位置モデルで危険な組合せ不成立を確認 |

## 未確認事項・限界

- JP3(VIN/TAB_HVIN)は SW4 に連動しない。JP3 を手動で RUN(1-2)/PROGRAM(2-3) に合わせる必要があり、JP3 の誤設定はこのスイッチでは防げない(JP3 の誤設定が 12V 混入になるかは r5 の解析のまま)。
- 切替は全入力を外した状態で行う(r5 と同じ。電圧検出や自動切替はない)。
- フットプリントの元データは「嘉立創EDA/EasyEDA官方库」(https://lceda.cn/ , https://easyeda.com)の公開データ。
- 12V混入などの実機試験は行っていない。GPIO・電源・実装性・シルクは机上のみ。製造データ(Gerber 等)は作成していない。
- `sim/` 内の `pin-audit.json`、`core-jtag-route.json`、`manual-finalize.json`、`development/` は r5 からのコピーで、r5s では再生成していない(参考値)。
- 3D モデルは未作成。
- SW4 の周辺ではぎりぎりの配置(取付パッドとH3コートヤードの隙間が小さい)。実物のスイッチ外形図での再確認が必要。

## 再生成手順

1. `gen/` で `python build_r5.py`(スキーマティック・BOM・契約JSONを再生成。**`gen/make_sch.py` を自己書き換えする**ので、この `usb-jtag-r5-switch` 側で実行)。
2. `gen/` で KiCad 付属 Python `"C:/Program Files/KiCad/10.0/bin/python.exe" add_sw.py`(r5 の PCB から r5s の PCB を生成)。
3. `kicad-cli` で ERC / netlist / DRC、`python verify_design.py`。


## 更新（2026-11-06 後段）：発注用データ、JP1、シルク、BOM

- **発注用データ**を `order/` に作成した（ガーバー、ドリル、PCBA用BOM・CPL、LCSC別途注文リスト、補正記録）。使い方と未解決事項は [order/README.md](order/README.md)。注文はしていない。
- **JP1（バスARM）を1×3ピンに変更した。** ピン1=`TAB_PGOOD`、ピン2=`BUS_ARM`、ピン3=未接続（プラグの保管位置）。1–2に挿すと許可、2–3は許可しない。部品はJP3と同じ（C49257）。
- **シルクを整理した。** `SW4 MODE`／`PGM OFF RUN`／`POWER OFF FIRST`、`JP3 TAB5 PWR`／`1-2 ON`／`2-3 OFF`／`SW4+JP3 SAME MODE`、`JP1 BUS ARM`／`1-2 ON`／`2-3 OFF`。実装図は `review/`。
- **BOMのLCSC番号を記入した**（空欄はDNPと取付穴のみ）。水晶は、SMT実装できるYXC X322512MSB4SI（C9002、20pF）に変更し、C86・C87を33pFにした。
- 検証: ERCエラー0、PCB DRC違反0・未配線0、`verify_design.py` 合格、`gen/check_order.py` 合格。
