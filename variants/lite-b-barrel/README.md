# 廉価版B：99×78mm、HDMIあり、12Vバレル入力

> **2026-10-25 追加シミュレーション反映版**：15本の直列抵抗は680Ω／Basic C23228。HDMI専用部は低背化し、HPD反転・100nFフィルタ・Core手前10kΩを反映（Cは全DNP）。初期1MHz、DATA setup/hold各250ns以上、DIR待ち500ns以上、弱い駆動／SLOW、規定12V・Core通常0.5A・局所3V3通常10mA以下の条件付きPoC製造候補です。実通信・DDR3／GPUの実機動作は未確認です。
>
> [最新の個別評価・全BoM・PCBA実装区分](../../site/lite-b-evaluation.html)、[親の独立レビュー](../simulation/independent-dynamic-review.json)、[電源](../simulation/power/final-summary.json)、[パラレル](../simulation/parallel/final-summary.json)、[HDMI](../simulation/hdmi/final-summary.json)。以下は初回設計検証時の記録も含み、最新の値・条件は上記評価を優先します。


2026年10月25日。指定方法1・2・5・6・7とソケット変更を反映した、現行版とは別の回路図・PCB。現行の125×78mm版は変更していない。

## 設計と実装

| 項目 | 案B |
| --- | --- |
| 外形／層数 | 99×78mm、4層。M5-BusとCore位置を維持し、4か所のM3取付穴を残す |
| 電源入力 | 安定化12V、センタープラスのバレルのみ。F1・D1・TVS・バルク容量・降圧回路を維持 |
| USB PD | J2・U1・C2・R1〜R5・D2とPD専用9ネットの銅配線を除去 |
| Coreソケット | XDAP-4042044-20401、C22471982。204P、標準方向、5.2mm高。**PCBA対象**。Core本体はユーザー支給で購入BOMに含めない |
| L1 | COILMX MS1040-150M、C380054。15µH、Irms4.5A、Isat6A、DCR最大45mΩ。メーカー推奨ランドへ変更 |
| U3 | TOREX XC6206P332MR-G、C5446。3.3V局所回路用。外部給電なし、通常総負荷10mA以下がPoC条件。50mA急変は追加感度で目標外れあり |
| 帰還抵抗 | R7=3.3kΩと、R49＋R50=100kΩ＋100kΩを並列。合成3246.4338Ω、5V降圧の公称設定4.982V |
| HDMIバイアス | 元の単一499ΩをBasic単一510Ωへ変更。8個の短い分岐形状を維持し、二並列化は採用しない。元値との差は+2.2%、別途感度評価済み |
| 必須通信 | 8bitデータ、CLK、RDY、DIR、AUXを含む15信号、680Ω直列抵抗、2個のIoffバススイッチ、両電源監視と手動ARMを維持 |

HDMI端子は保持。J1・J3・J5・SW1〜SW3・JP1は元版と同様に手実装対象で、PCBA納品後に必要な組立を行う。J4の204ピンソケットを手はんだへ回す構成ではない。JP1は初期開放とし、Tab5／FPGAのGPIO駆動方向を確認してからARMする。

ソケットは公式図面の0.6mmピッチ、行間8.2mm、キー、非対称の位置決め穴、金属固定ランドを反映する。新ソケットで高さが変わるため、メーカーの実装プレビュー、治具要否、筐体への収まりは製作前に確認する。Coreカード下の空間をソケット本体の占有面積と混同しないU字形のcourtyardを使う。

## 配線方法と検査結果

初期の独自配置では自作A*ルーターでHDMI差動配線は成功したが、電源と一般信号の混雑が残った。失敗ログを`kicad/sim/route-attempt-1.log`と`route-completion.log`へ記録した。その後、同じ99mm外形で配線・検査を完了したAの共通配置をBへ継承し、PD専用枝だけ除去する方法へ切り替えた。完成した共通配線を再利用し、無関係な接続の再配線を減らす。

PD除去で末端になったVIN配線6本をDRCの指摘に従って順に剪定し、各段階で残す回路の未接続が増えないことを確認した。

- PCB DRC：**全項目0、未接続0**。`kicad/sim/drc_r3.json`
- 必須パラレル通信・電源の実PCB接続チェック：**34項目通過**。`parallel_power_check.json`
- ERC：エラー0。149件の埋込シンボルとライブラリの差分警告、4件の孤立ピンラベル警告は、生成回路図の既存方式による残存警告として記録。実PCBと回路図の独立照合は共通レビューでも確認する
- HDMI：銅配線連続性、role分類、D1の0.585mm短分岐、ESDランドの検査を通過。新PCBから形状を抽出し、`R_BIAS=510Ω`の4ポートモデルを再実行した。`tmds_sparam.json`等を参照
- PCBA：86部品、34 BOM行。BOM/CPLの部品集合一致。ソケットJ4を含み、Coreモジュールは含まない

4ポートモデルは公式Core配線を加味した近似で、変更ソケットの実測SパラメータやHDMI適合試験の代わりではない。HDMIは追加成功条件であり、パラレル通信とCore上DDR3の利用を最優先にする。

5Vの抵抗網とTI全温度Vref範囲、抵抗各±1%から計算する設定範囲は約4.807〜5.157V。20℃の銅配線モデルでは、0.5Aを各Core端子への最悪の単独経路へ集中させた電圧降下は最大約68mV、2Aなら約273mV。並列経路の寄与、接点、帰路、温度、リップル、負荷過渡を含む実測値ではない。Coreの公式0.5A条件をピーク電流上限とは解釈しない。実機ではCore端子の5Vを観測しながらDDR3初期化と負荷試験を行う。

## ファイルと再生成

- 回路図：`kicad/tab5-fpga-carrier.kicad_sch`
- PCB：`kicad/tab5-fpga-carrier.kicad_pcb`
- 製造レビュー用：`manufacturing/poc-2026-10-25/`（Gerber ZIP、穴データ、JLC BOM/CPL、手実装一覧、DNP一覧、実装図）
- 派生記録：`kicad/sim/common-layout-derivation.json`、`pd-stub-pruning.json`

再生成は、検証済みAの状態からKiCad Pythonで`derive_from_a.py`を実行し、通常Pythonで`kicad/gen/make_sch.py`と`make_bom.py --offline`、KiCad Pythonで`trim_removed_pd_stubs.py`を実行する。続けてBの各検査と製造エクスポートを行う。Aを変更した場合、Bも新しい派生元ハッシュで再検証する。旧独自配置の未合格製造データは採用していない。

参照要求はLinux `c1cd5e47f9f07a164bc070b8defe36bb05682c6b`、GPU `3b1ace3d91c6305ec0e32378f8819fce208c2aa7`、メモリ研究 `e4aa69d09b2643d6f62fe686ef0f3284b109c541`。LinuxのREADME／開発目的／Device Tree／通信準備実装、GPUの計画・board profile・通信RTLを照合した。物理PARLIO・DMA・DDR3アクセスは未検証で、LinuxとGPUは別ソフトウェア・別ビットストリームとして使用する。DDR3はLinuxメインRAMの透過的増設ではない。

これはCAD検査を通過したPoC製造候補。ソケット在庫、治具費用、JLCの部品回転・積層・実装可否を再見積もりとプレビューで確認する。発注、購入、実機動作の完了を意味しない。
