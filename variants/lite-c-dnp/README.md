# 案C：125×78mm、HDMI／USB PDは回路を残して未実装

> **秋月ボタン対応**：SW1/SW2をTS-06104（秋月115969）用にランド・配置・局所配線変更。手実装は各1個。HDMI/PDは回路を残して全DNPを維持。[購入リスト](manual-parts-procurement.json)。SW3はDigiKey、J1の秋月候補は無加工互換未確定のためバレル使用前に選定が必要。


> **2026-10-25 追加シミュレーション反映版**：15本の直列抵抗は680Ω／Basic C23228。HDMI専用部は低背化し、HPD反転・100nFフィルタ・Core手前10kΩを反映（Cは全DNP）。初期1MHz、DATA setup/hold各250ns以上、DIR待ち500ns以上、弱い駆動／SLOW、規定12V・Core通常0.5A・局所3V3通常10mA以下の条件付きPoC製造候補です。実通信・DDR3／GPUの実機動作は未確認です。
>
> [最新の個別評価・全BoM・PCBA実装区分](../../site/lite-c-evaluation.html)、[親の独立レビュー](../simulation/independent-dynamic-review.json)、[電源](../simulation/power/final-summary.json)、[パラレル](../simulation/parallel/final-summary.json)、[HDMI](../simulation/hdmi/final-summary.json)。以下は初回設計検証時の記録も含み、最新の値・条件は上記評価を優先します。


2026年10月25日の追加指定。方法1・2・3・5・7とソケット変更を採用する。方法6は含まないため、現行の125×78mm外形を維持する。現行版とA／B案とは別フォルダで管理する。

方法1・2・3・5・7とソケット変更を反映した回路図・配線済みPCB・製造候補を作成した。KiCadの全severity DRCで違反0・未接続0、実PCBのパラレル通信／電源検査36項目を通過した。実機動作済みではない。新ソケットの在庫・PCBA実装／治具・向きの最終プレビューと、5.2mm高さ方向の干渉は発注先で確認する。現行版は変更していない。

製造候補は [manufacturing/poc-lite-c-2026-10-25/](manufacturing/poc-lite-c-2026-10-25/) の `gerbers.zip`、`jlc-bom.csv`、`jlc-cpl.csv`。PCBAは58部品・27BOM行。J4ソケットは含み、Core本体は含まない。回路図・PCBは `kicad/tab5-fpga-carrier.kicad_sch`／`.kicad_pcb`。

## 実装範囲

- HDMI：回路、配線、ランドを保持する。J5、C12〜C19、R28〜R41、U4〜U6、Q1・Q2、F2は未実装。J5も後付け必須とはしない。HDMI機能は出荷構成では使用しない。
- USB PD：J2、U1、C2、R1〜R5、D2を未実装にする。R4は元々DNP。PD入力回路と配線は残す。
- バレル電源：J1、F1、D1、D3、C1と降圧回路、3.3V回路を残す。安定化12V、センタープラスを使う。J1は従来と同じ手実装対象なので、納品PCBAだけでは電源を挿せない。組立手順にJ1実装を含める。
- J4は受け側ソケットとしてPCBA必須。Tang Primer 20K Core本体はユーザー支給でBOM対象外。
- U7・U8のバススイッチ、U9・U10の両電源監視、Q3・Q4、OE抵抗、JP1の安全回路と15本の直列抵抗は実装する。JP1はGPIO設定確認後にARMする。

## 機能成立の確認条件

回路の接続関係では、バレル→F1→D1→VIN→TPS5430→L1→Core 5Vと、5V→U3→バススイッチ用3.3Vは、HDMI／PD専用部品を通らない。HDMI／PDの未実装自体は必須電源経路を切断しない。M5-BusのHVINへはVINを供給し、Tab5の5V出力・VBAT_OUTとCore 5Vを直結しない。

HDMI未実装時はHPD、DDC、TMDS端子をHDMI送信用に駆動しないFPGA構成を使う。外部への3.3V給電は行わず、廉価版LDOの低負荷条件を守る。Core上のDDR3電源はCore自身の回路が生成する。

部品実装設定を適用した実PCBで、必須電源経路、15信号のスイッチと直列抵抗、ソケットの端子番号、誤った5V／VBAT接続がないことを検査した。新ランドと新配線のDRCも通過した。Core DDR3アクセスとTab5実通信、起動・負荷過渡の実機試験は別途必要であり、CAD検査だけで実機動作済みとはしない。

初期のDNP単独検査（30項目／8故障）は[population-topology-check.json](population-topology-check.json)に履歴として保持する。現在の設計判定には下記の実PCB検査を使用する。具体的な実装除外一覧は[population-policy.csv](population-policy.csv)。

## 費用の扱い

方法3でHDMI部品を未実装にするため、方法1の499Ω抵抗のBasic化による節約は二重に加算しない。方法6を含まないので小型化の割引も加算しない。PD／HDMIを将来実装する場合は、完成した回路一式と電源条件を再確認し、一部だけの実装は行わない。

## 採用変更と図面照合

| 対象 | 案Cでの変更 |
| --- | --- |
| J4 | XDAP-4042044-20401、C22471982、204P DDR3 STD、5.2mm高。専用ランドを作成。受け側ソケットでありCore本体ではない |
| R7・R49・R50 | Basic 3.3kΩ C22978 と、100kΩ C25803を2個直列にした200kΩを並列。合成3.2464kΩ、設定公称4.98205V |
| U3 | TOREX XC6206P332MR-G、Basic C5446、SOT-23。1=GND、2=3.3V出力、3=5V入力。C10・C11も入出力端子から約2〜3mmへ近接移設した |
| L1 | COILMX MS1040-150M、C380054、15µH、Irms4.5A、Isat6A、DCR最大45mΩ。安価なExtendedへの変更であり追加料金廃止ではない |

ソケットは `variants/reference/socket-XDAP.pdf` の標準タイプ推奨ランド（T-11-0081 Rev.B、2ページ目）に従う。上下列の各0.6mmピッチ、列中心±4.1mm、1番x=-31.65・y=+4.1mm、2番x=-31.35・y=-4.1mm。72番までの36接点列の後にキー間隔を入れる。全204端子を元PCBの番号と信号へ照合し、座標差は0.003mm未満。位置決め穴はx=±33.4mm、左径1.6・右径1.1mm。固定金具ランドはx=±32.5・y=-12.1mm、4.5×4.6mm、GND接続。占有域をU形で定義し金具ランドにも組立余裕を確保した。開ラッチ幅76mmと新しい高さ5.2mmについて、Tab5ケースを含む実物照合は未実施なので筐体適合を保証しない。

L1は `variants/reference/MS1040-current.pdf` の推奨パターンから中心±4.75mm、4.1×4.95mmのランドを作成した。最大本体11.5×10.3mmとランドの和集合へ0.25mmを加えた段付きcourtyardを使用。空の角まで全体長方形とすることによるC4／D2の偽の重なりを避けつつ、実本体・ランドの余裕を保持した。

## 電源余裕と立ち上げ条件

TI SN74CB3Q3245のICC最大各2mA、OE抵抗、制御入力、リーク余裕から、内部3.3V負荷は約4.28mA。初回静的予算50mA（過渡目標外れあり、現在のPoC条件は通常10mA以下）、外部PMOD／GPIO給電予算はゼロ。CoreのFPGA／DDR3電源はCore内部で5Vから生成されるため、この小型LDOへ大電流を流さない。

TPS5430の全温度Vref 1.196〜1.245Vと帰還抵抗各±1%による静的設定範囲は4.807〜5.157V。Coreまでの5V銅配線の最大単一路抵抗は約0.1242Ω、0.5Aを一経路に流す保守的計算でも銅のみの下限は約4.745V。接点、GND帰路、発熱、リップル、負荷過渡を含めた保証ではない。公式のCore電流要求0.5Aは全ビットストリームのピーク上限ではなく、TPS5430の3Aも基板全体の連続3A保証ではない。

最小L=12µH・最小f=400kHzで、2Aを感度ケースとして `(Vout_max+0.55)/(Lmin*fmin)` の保守的リップル上限を使ってもピーク約2.595Aとなり、TPS5430最小電流制限4AとL1飽和6Aを下回る。定常時の数値照合であり、起動・短絡・熱・制御ループの実証ではない。元のC7 220µF POSCAPと補償方針を保持し、全MLCCへ変更していない。[電源予算](kicad/sim/lite_c_budget.json)と[配線抵抗](kicad/sim/power_dc_check.json)に条件を記録した。

初回は電流制限可能な12V 3A級の安定化電源を用い、Coreを挿す前に0.5A電子負荷で5Vの起動・リップル・負荷変動・温度を確認する。その後Coreを挿し、GPIOの所有権と方向切替を確認してからJP1をARMし、低速CRC照合・DDR3段階試験へ進む。新LDOの50mA予算は全温度範囲の実測保証ではない。通常室温の初期PoCを前提とし、温度と起動波形を測定する。

## 実行した検査

| 検査 | 結果 |
| --- | --- |
| KiCad DRC、全severity | 違反0・未接続0：[drc_r3.json](kicad/sim/drc_r3.json) |
| 実PCBの15信号・電源・ARM・DNP | 36項目通過：[parallel_power_check.json](kicad/sim/parallel_power_check.json) |
| 故障注入 | 正常系を含む17ケース通過。CLK誤配線、列反転、GND／電源欠落、誤LDO、帰還断線、必須部品の誤DNP、PD／HDMI部分実装を検出：[regression_parallel_power.json](kicad/sim/regression_parallel_power.json) |
| XML・生成モデル・実PCB、204端子、近接デカップリング、取付穴余裕、BOM/CPL | 12項目通過：[lite_c_check.json](kicad/sim/lite_c_check.json) |
| ERC | 電気エラー0：[erc_errors.json](kicad/sim/erc_errors.json)。全severityでは埋め込みシンボル比較警告157件と単独ラベルPD_PG/TAB_SDA/TAB_SCLの3件。元版の同環境再実行も比較警告156件＋単独ラベル3件で、差はR50に追加したGND記号1個だけ：[元版比較](kicad/sim/erc_baseline_comparison.json)。警告を隠す設定は追加していない |

新ソケットを含むCore全体の3D電磁界解析は実施していない。HDMIは未実装なのでHDMI動作の合格を主張しない。既存HDMI・パラレル信号の銅配線は全て保持したことを比較検査した。DDR3とTab5の物理通信・PARLIO DMAは未検証。

## 再生成と要求参照版

KiCad 10同梱Pythonで `kicad/gen/make_sch.py`、通常Pythonで `make_bom.py --offline`、KiCad Pythonで `make_pcb.py` を実行する。Cの標準PCB生成は元の検証済みPCBをハッシュ照合して局所更新する。実験的な全体A*配線は新LDO周辺等で再配線待ちとなり採用せず、`--experimental-full-route` へ分離した。最終DRC通過版は局所更新版。

要求参照版：Linux `c1cd5e47f9f07a164bc070b8defe36bb05682c6b`、GPU `3b1ace3d91c6305ec0e32378f8819fce208c2aa7`、メモリ研究 `e4aa69d09b2643d6f62fe686ef0f3284b109c541`。Linuxの物理PARLIO/DMAドライバとGPUの検証済みボードプロファイルは未実装／未検証。基板だけでGPU機能や透過的LinuxメインRAM増設が完成するとは扱わない。Linux用とGPU用は別ソフトウェア・別ビットストリームで使用する。
