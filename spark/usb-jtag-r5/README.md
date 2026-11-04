# USB–JTAG対応 r5：手動ジャンパ方式（KiCad）

2026-11-03。現行r4 Full/Liteと応募公開データは保持し、Full125×78mmを基に次版を独立設計する。ユーザー指定により、初期の自動切り替え案を取りやめ、**3個のジャンパでRUN／PROGRAMを切り替える安価な構成**へ変更した。KiCad回路図・PCBが設計の正。製造リリース・実機検証は未完了。

## モード切り替え

**USB・バレルを両方とも抜き、残留電圧が下がってから、JP2・JP3・JP4の3個を必ず同じ位置へ動かす。通電中に切り替えない。混在設定ではCoreに12Vが入る組合せがある。** ショートプラグは3個付属させ、初期はRUN位置。ジャンパ設定の誤りを自動保護するICは搭載しない。

| モード | JP2・JP3・JP4 | PD要求 | Coreとデバッガ | Tab5 HVIN |
|---|---|---|---|---|
| RUN 通常給電 | 全て1–2 | 12V | 既存TPS5430の5V | 接続 |
| PROGRAM 書き込み | 全て2–3 | 5V | USB VBUSの5V | 切断 |

3本の1×3ヘッダは並べて配置し、3個のプラグを同じ側へ移動させる。JP1は既存のバスARMで、モード選択には含めない。

| ヘッダ | pin1：RUN側 | pin2：共通 | pin3：PROGRAM側 |
|---|---|---|---|
| JP2 POWER | BUCK_5V | Core／周辺／デバッガの+5V | USB VBUS |
| JP3 TAB5 | VIN（保護・OR後） | Tab5 HVIN | NC（プラグ保管位置） |
| JP4 PD | GND | CH224K CFG1 | PD_VDD |

CH224KのCFG2=Low、CFG3=Highを維持し、CFG1=Lowで12V、Highで5Vを要求する。旧R3のCFG1固定GNDを撤去し、R73=100kΩでCFG1をPD_VDDへプルアップする。JP4のプラグがない場合も5V要求が既定となる。参照：保存済みCH224K手冊V2.1 p9のI/O設定表。PDの設定は電源投入前に確定する。

## 使用条件

Tab5にはバッテリーを装着できず、外部給電のみ。PROGRAMではTab5を停止し、CoreをUSBから動かして書き込む。RUNではPD12Vまたは安定化バレル12Vで全体へ給電できる。

| 接続 | 設定と動作 |
|---|---|
| PCのUSB-C5V | PROGRAM。Coreとデバッガに給電し、Tab5は停止 |
| PD電源 | RUN。12V交渉後、Tab5とCoreへ給電 |
| バレル12V | RUN。Tab5とCoreへ給電 |
| PC USB＋バレル12V | RUNでもUSB–JTAGを使用可能。Core／Tab5の電力は12V側から供給 |
| PROGRAMでバレルのみ | Coreには給電されない。USB接続が必要 |

**PCの5V供給電流は別途必要。** Sipeed公式Core仕様は5V±10%、0.5A。デバッガと周辺の電力が加わるため、USB2.0標準の500mA合計では保証できない。PROGRAMは1.5A以上を広告するPCのUSB-C Source＋C-Cデータケーブルを対象とし、Core端で4.5～5.5Vを確認する。CC電流広告の自動検出は搭載しない。USB-A変換／広告不明のポートではバレル併用RUNを使う。USB descriptorの500mA指定だけで追加電流を得られるとは扱わない。

## 電源の変更

r4のTPS5430、インダクタ、整流・保護・OR回路、5V帰還／補償部品を継承する。降圧出力だけをBUCK_5Vへ分離し、JP2でCoreの+5Vにつなぐ。Tab5への分岐はJP3で物理的に切り離す。USBをCoreへ直結するPROGRAM設定では、JP4でPD要求を5Vに固定する。

eFuse3個、新規昇降圧、電源選択MUX、USB認識に連動するCore電源スイッチ、AND／OR／反転ロジック、電流選択回路、デバッガEEPROMは採用しない。自動案の191部品から151部品へ減らした（DNP／機構を含む設計モデルの数で、見積価格やPCBA点数ではない）。旧自動案は `archive/automatic-power-study/` に参考として保存し、製造に使用しない。

M5-Busの5V/BAT出力は接続しない。既存のTAB_3V3／CORE_PGOOD／ARMによるバス分離を維持する。PROGRAMでTab5無給電の際にGPIOから給電されないことは、既存回路の設計照合に加え実機で確認する。

## USB–JTAG

J2をUSB2データ対応の16接点Type-Cへ変更。CC1/CC2はCH224K、D+/D−はFT232HLへ接続する。CH224KのDP/DMは未接続のまま。Nexperia PESD5V0U1BL（SOD882）でデータ線をGND基準に保護し、12V VBUSへクランプしない。

FT232HLのADBUS0/1/2/3をTCK/TDI/TDO/TMSとして使う。SN74LVC125Aと33Ω抵抗を介してSODIMMの専用JTAGへ直接配線する。バッファは周辺3.3V側のIoff対策であり、Core内部の全電源シーケンスを保証するものではない。2個の安価な2N7002はVBUSがないとFT232HをRESETへ保持するための回路で、システム電源の自動選択はしない。

93LC56BやデバッガMCUのファーム書き込みは不要。FT232Hの既定VID/PID0403:6014を使い、PCソフトがMPSSEを選択する。書き込み時は対象デバイスを特定する。複数の同種FT232Hを同時接続する運用は別途識別手順が必要。

公式SOM-3961回路図p1の金端子ブロックを拡大照合し、r4ではNCだった4本をJTAGへ割り当てた。**CoreをSODIMMへ装着すればUSB書き込みできる構成で、追加JTAGコネクタ／ケーブルは不要。** 保存した参照画像は `reference/core-jtag-goldfinger.png`。

| Core SODIMM端子 | 信号 | FPGAボール |
|---|---|---|
| 143 | TMS | B8 |
| 147 | TDO | C6 |
| 149 | TCK | A7 |
| 153 | TDI | A6 |

これら4本は通常GPIOに再利用せず、各ビットストリームで専用JTAGを維持する。Core上の外部ライター用コネクタとの同時駆動は禁止。実物Coreの版、ピン1／嵌合方向と銀行2の3.3V条件は実装前に確認する。

openFPGALoaderのFT232Hケーブル設定を使用する。FT2232用`tangprimer20k`プリセットを無条件に流用しない。初回は1MHz以下でID検出、SRAM書き込み、フラッシュ書き込みの順に検証する。今回USB機器やフラッシュへ書き込みは行っていない。

## ホスト照合

`host-review.json` に参照コミット／要求資料SHAを記録。Linux本体のREADME・DEVELOPMENT_GOALS・Device Treeを確認した。ローカルLinuxの `tools/fpga-link/transport.py` とFPGAドライバは存在せず、未実装として扱う。MeOSのGPIO／LINK／GFX、ESP-IDFの通信・表示実装、Linux外部メモリ研究計画も照合する。

ホスト通信ピン／デバイスコマンドはr4から変更せず、FPGA専用のNC4本のみをJTAGへ予約するため、ESP-IDF・MeOS・Linuxのプロトコル変更は不要という設計判断。PROGRAMではホストOSを停止する。給電／ジャンパ／書き込み手順は各ホストへ反映が必要だが、r5未リリースのため各ホストリポジトリは未更新。既存DDR3／NPU等の未検証事項を解消したものではない。

## ファイルと検証

- `full/design/kicad/tab5-fpga-carrier-r5.kicad_pro`：KiCadプロジェクト。
- 同名 `.kicad_sch`／`.kicad_pcb`：現行の手動ジャンパ設計。
- `bom-r5.csv`／`circuit-contract.json`：部品表・接続モデル。
- `full/design/kicad/sim/`：実行ログ／ERC／DRC／電気接続照合。
- `preserved-r4.json`：現行r4の1234ファイルの保全ハッシュ。

正規再生成入口は `gen/build_r5.py`（回路図）、`gen/derive_pcb.py --place-only`（r4配線継承と配置）。KiCadからSpecctraへ書き出す `gen/export_routing.py` とローカルFreeroutingの結果をKiCadへ戻し、`gen/finalize_manual.py` と `gen/route_core_jtag.py` を適用してDRCを行う。基板の正はKiCadで、EasyEDAへの移植／公開更新は行わない。旧r4用の製造スクリプトをr5へ適用しない。

**今回の設計検証：** PCB DRC違反0・未配線0、ERCエラー0。ERC警告208件はライブラリシンボル差分205件と未使用状態ラベル3件で、警告0とはしていない。回路図とPCBの607本の接続ピン照合、誤接続3種の検出、r4保全ハッシュ一致を確認。これらは実機試験ではない。

**製造前の残件：** USB差動配線・ESDスタブ・長さ差・参照面の確認、クリスタル配置と負荷容量、コネクタ／Coreの嵌合、モードシルク／プラグ付属、LCSC部品確定、電源投入電流・残留電圧・逆流・熱・USB列挙・SRAM／Flash書き込み・全ホストの実機試験。r4のDRC0／EasyEDA計算をr5へ転用しない。Gerber・CPL・発注ZIPは作成しない。

## 一次資料

- [Sipeed Primer20K](https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html)、本リポジトリのSOM-3961回路図／Coreデータシートp3。
- 本リポジトリ `docs/reference/parts/CH224K_datasheet_lcsc.pdf` V2.1 p9：CFG1=1で5V、0/0/1で12V。
- [FTDI FT232H v2.2](https://ftdichip.cn/Support/Documents/DataSheets/ICs/DS_FT232H.pdf)：5Vモード、MPSSE、既定設定、RESET。
- [Nexperia PESD5V0U1BL](https://www.nexperia.com/product/PESD5V0U1BL)：低容量ESD。

R4のDNPパッド付近のGND復帰に0.5/0.3mmビアを追加し、近傍のCC1／CFG3配線を0.06mmずつ逃がしてドリル対銅箔の0.25mm規則を満たした。R4は恒久DNP。製造時はこの近接ランドのマスク／ペーストを確認する。
