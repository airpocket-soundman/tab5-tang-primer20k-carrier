# 外部給電のオルタネート主電源改訂 r2

更新：2026-10-26。**回路候補の検討段階。PCB、製造データ、EasyEDA反映、新回路の過渡解析は未完了。発注不可。**

## 確定した要求

押すたびにON/OFFを保持する主電源で、外部給電だけを切る。DC12VとUSB PD12Vのどちらにも有効とし、Tab5 HVINとCore用5V・局所3.3Vを一括制御する。Tab5の内蔵バッテリー動作は停止対象に含めない。既存SW3のBUCK_EN接地によるFPGA専用停止は取り除く。

```
DC12V ─ 保護・D1 ─┐
                  ├─ VIN_OR ─ 主電源スイッチ素子 ─ VIN ─┬─ Tab5 HVIN
PD12V ───── D2 ──┘                                    └─ TPS5430 → Core5V → 局所3.3V
        └─ PD交渉回路（主電源の上流に残す）
```

信号ピン、HDMI、リセット、ユーザーボタン、BUS ARMは維持する。Tab5がバッテリー動作してCoreが無給電となる状態を含め、電源監視・バス分離・側帯信号の逆給電を再確認する。

## 独立した回路候補

[フル版回路図](full/kicad/tab5-fpga-carrier.kicad_sch)と[廉価版A回路図](lite-a/kicad/tab5-fpga-carrier.kicad_sch)を、従来版を保持した別ディレクトリで作成した。KiCad標準TPS22810DRVシンボルの端子はVOUT=1、QOD=2、CT=3、GND=4、EN=5、VIN=6、露出パッドGND=7。旧SW3からBUCK_ENへの接続をなくし、VIN_ORから制御接点・R53を介してMAIN_ENを操作する。R54で未接続時をOFFにする。QODは未使用とし、Tab5側の未知の逆流経路を強制放電しない。

| 候補 | LCSC | 役割と制約 |
|---|---|---|
| XKB5858-Z-TP-75 | C692487 | ラッチ式SMT押しボタン。100mA/30V接点にはEN電流だけを流す。解放時1–2、押下保持時2–3。第二極4–5–6未使用。ランド・機構・向きは未確定で、回路図のフットプリント割当は空欄。 |
| TPS22810DRVT | C2653758 | WSONの3A負荷スイッチ候補。SOT-23版の2Aと混同しない。2.7–18V動作。過電圧・逆流遮断の保証部品ではない。 |
| R53 / R54 | C25804 / C25803 | EN直列10kΩ / プルダウン100kΩ。 |
| C25 / C26 | C15849 / C57112 | 入力1µF/50V / 仮のCT10nF。12Vでの立上り2.085msはデータシートの代表値であり、実負荷・公差での保証ではない。 |

2026-10-26のLCSC取得値ではC2653758は在庫10、C692487は2140、代替検討用C5180135は295。変動するため確保済みとは扱わない。JLCPCBの候補ページはSMT Assembly/Extendedを表示していたが、この基板での実装受理は未確認。

**TPS22810は最終採用を確定していない。** 既存SMBJ15Aのクランプ電圧を18V入力の保護保証として扱えないため、入力過渡と保護協調を解決する必要がある。必要なら高耐圧部品へ変更する。電圧降下・接合温度・突入電流・USB PD起動順序・無給電時逆流を評価してからPCBを確定する。

## 検証の範囲

- 新回路候補のERCエラー検査と、エクスポートしたネットリストと設計モデルの端子照合を実施。結果は各版の`kicad/sim/`に収録。
- ERCのエラー0は動作保証・PCB検証・過渡解析合格を意味しない。警告の全件分類は未完了。
- r2にPCBやGerberをコピーしていない。既存PCBと新回路図が一致するという誤解を避けるため。
- 既存172/187条件の結果は旧設計のもの。新主電源のON/OFF、突入、遮断の検証として転用しない。
- 次の工程は部品・保護協調確定、PCB変更、設計側解析、EasyEDA APIによる反映、EasyEDA内での再計算・照合。公開Spark側にはEasyEDAデータと同環境で実行した結果のみを記録する。

## 要求元との照合

| 要求元・参照コミット | 確認した資料・状態 |
|---|---|
| tab5-linux-fpga `c1cd5e47f9f07a164bc070b8defe36bb05682c6b` | README、DEVELOPMENT_GOALS、Device Tree、fpga-link transport。物理通信はmockで、DMA・実機通信は未実装/未検証。 |
| tab5-fpga-gpu `3b1ace3d91c6305ec0e32378f8819fce208c2aa7` | README、Project_B、board_profile、link_bus_wrapper。VERIFIED=0、物理通信/DDR3の完成・実機性能は未確認。 |
| esp32p4-linux-fpga-memory `e4aa69d09b2643d6f62fe686ef0f3284b109c541` | README、Project_A。明示的なDDR3データ領域の研究であり、透過的なLinux主記憶増設ではない。 |

両用途とも外部給電断による通信中断・電源再投入後の再初期化が必要。別ソフト・別ビットストリームという前提を維持する。GPIO/通信方式の変更はないため関連実装は変更していない。関連リポジトリの仕様コピーへの同期は未実施。

参照：[TI TPS22810](https://www.ti.com/lit/ds/symlink/tps22810.pdf)、[LCSC C2653758](https://www.lcsc.com/product-detail/C2653758.html)、[LCSC C692487](https://www.lcsc.com/product-detail/C692487.html)、[JLCPCB C2653758](https://jlcpcb.com/partdetail/C2653758)、[JLCPCB C692487](https://jlcpcb.com/partdetail/C692487)。
