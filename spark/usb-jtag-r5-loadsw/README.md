# r5l：SW4を信号専用にして、+5VをPMOSのロードスイッチで通す変種（PoC・発注候補）

2026-11-06。**実機未検証。リリースではありません。** r5s（`../usb-jtag-r5-switch/`）の派生で、r5s、r5、r5c、r4 のファイルは変更していません。

## 何を変えたか

- r5sでは、SW4（G-Switch SS-23D03-G080）が+5Vレールの電流を通していた。この部品の電流定格は、メーカーのデータシートで **0.3A・50V DC**（LCSCの掲載値1Aと食い違う）。
- r5lでは、SW4は**信号だけ**（ゲート駆動とCFG1）。+5Vの電流は、背中合わせのPMOS（AO3401A）が通す。
  - RUN経路 Q11・Q12（BUCK_5V → +5V）、PGM経路 Q13・Q14（VBUS_PD → +5V）。
  - PGM経路の過電圧ガード Q15・D12・R95（VBUS_PDが約7Vを超えたら、PGM経路をオフにする）。
- 追加11部品（Q11〜Q15、D12、R91〜R95）。基板の部品位置・配線の他の部分は、r5sのまま。

詳しい検討・SPICE結果・未確認事項は `../../docs/r5s_SW4ロードスイッチ式の検討_2026-11-06.md`。

## 中身

| 場所 | 内容 |
|---|---|
| `full/design/kicad/` | KiCadの回路図・基板・BOM・回路契約（`circuit-contract.json`）。`gen/` に生成スクリプト |
| `full/design/kicad/gen/add_loadsw.py` | r5sの基板から、r5lの基板を作る（部品の配置探索＋配線）。`loadsw_routes.py` が配線の指定 |
| `sim-spice/` | ロードスイッチのngspice検証（`run_all.py`、結果は `results.json`）。汎用モデル |
| `verify_design.py` | 回路図のネットリスト検査（SW4の位置モデル、ロードスイッチの接続、SW4が電源を通さないこと、ERC・DRC） |
| `order/` | JLCPCB向けの発注候補データ（ガーバー、BOM、CPL）と、`README.md`（未解決事項） |
| `review/` | 確認用の画像（3D） |

## 検証したこと

- ERCエラー0、PCB DRC違反0、未配線0（`full/design/kicad/sim/`）。
- 回路図と基板のネット照合: 761ピン、不一致0。r5sとの基板の差分は、SW4の電源配線の削除24点と、SW4の3ピンのネット変更だけ。
- `verify_design.py`: PASS（SW4のスライダ位置モデル、ロードスイッチの接続、危険な組合せなし）。
- SPICE（汎用モデル）: RUN／PGM／OFF、DCのみ、VBUS 12V誤使用（+5V＝0V）、5.5V給電で誤遮断なし。+5Vのピークは、ランプで5.5〜7.7V。

## 再現

```
"C:/Program Files/KiCad/10.0/bin/python.exe" full/design/kicad/gen/add_loadsw.py      # r5s基板 -> r5l基板
python full/design/kicad/gen/build_r5.py                                               # 回路図・BOM（r5lのコピー内でだけ実行）
python verify_design.py
python sim-spice/run_all.py
```

発注データの再生成は、`order/README.md` の「再生成」を参照。
