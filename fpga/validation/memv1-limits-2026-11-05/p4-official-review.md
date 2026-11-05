# ESP32-P4 rev1.3 PARLIO 上限の一次資料レビュー（2026-11-05、調査のみ）

実装・ビルド・実機変更なし。実機版は保存済みflash logでrev1.3。最新rev3.xのTRM/datasheetを代用していない。

## 確定事実：資料と該当箇所

| 資料 | 版・頁 | 確認事項 |
|---|---|---|
| [rev1.3専用TRM](https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_technical_reference_manual_en.pdf) | pre-release v0.4、§56.2 p2815 | PARLIO IO clockの公称最大は40MHz。RX/TX両unitを含むcontroller featureで、TXのみ/RXのみ40MHz超を許す記載はない |
| [rev1.3専用datasheet](https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_datasheet_en.pdf) | v1.2、§4.2.2.18 p74 | 同じ40MHz上限、1/2/4/8/16bit bus、GPIO matrix経由で任意GPIOへ割当て可能 |
| 同datasheet | §4.1.4.1 p43、§5.4 p80 | GPIO matrixの配線機能、3.3V/25℃のDC VIH/VIL/VOH/VOL/電流条件。PARLIO専用のpad setup/hold、Tco、基板負荷別最大clockのAC表は該当節では示されていない |
| 同TRM | §9.4.2–9.4.4 pp516–517、register p571 | GPIO入力には選択式2段同期とfilter。同期は既定無効、GPIO filter有効時は2clockを超えるpulse幅条件。matrixを使えば自動的に常に2段同期されると解釈しない |
| 同TRM | §9.5 pp521–524 | peripheral出力matrix経路とGPIO OE制御。GPIO registerアクセスのソフト費用とpad信号伝搬時間は別 |
| 同TRM | §56.5.1 pp2816–2817 | RX/TXは独立source/divider。XTAL40、PLL_F160Mなどから生成し入出力反転を設定可能。SoCのAXI/APB clockは別領域 |
| 同TRM | §56.5.2 pp2817–2818 | FIFO resetはAXI/Core双方のclock同期、非連続clock時の制約。START変更はCoreclockOFF→START→ON。interframe Core/FIFO reset要件があり、根拠なく全resetを削除できない |
| 同TRM | §56.5.8–56.5.9 pp2822–2823 | TX gateはTXD最上位を利用、内部VALID生成はTXD15を使用。VALID pinはbus width設定を変えず、最大15data pinsを残す。今回の物理8bitとは両立 |
| 同TRM | §56.7.2 pp2825–2826 | TX_READY確認後START/clock開始。FIFOready待ちを無条件に削除する根拠なし |
| [公式errata summary](https://docs.espressif.com/projects/esp-chip-errata/en/latest/esp32p4/02-errata-summary/index.html) | latest取得時表、rev1.3欄 | PARLIO専用clock上限を引き下げるerratumは表で確認できず。ただし表にないことは未知不具合なしの証明ではない。DMA-767はv3.0対象でrev1.3へ適用しない |

取得した専用datasheet PDFは94頁、SHA256 `52ef629ec92510a6b32272afac263074eff38065a7e36bccb464b6e6324e03d3`。TRMは2975頁、SHA256 `ae1fa2a411776760e03329adc3f9a7c13e98c440168cab208f06e3b2d5818830`。PDF自体は本リポジトリへ含めない。

## IDF v5.5.2と今回の構成

[公式LL source v5.5.2](https://github.com/espressif/esp-idf/blob/v5.5.2/components/hal/esp32p4/include/hal/parlio_ll.h) のdivider範囲はRX/TXともinteger/fraction最大0x100（:23–29）。source/dividerから40MHz超の数値を計算できても、それは公称IO上限を超えてよい根拠にはならない。整数160MHz/20=8MHz、/16=10MHz、/4=40MHzは分周算術であり、実際の選択source周波数・pad duty・通信可否の実測とは区別する。

LLのTX START（:576–587付近）は立上りtriggerでありSTARTを0にするだけでは進行中転送を止めない。TXのdisable/GDMA停止/IRQ回収を確認して再利用する現在の所有権規則が必要。sample edgeはTX/RXのI/O inversion bitへ設定され、GPIO matrix側反転があるためAPIのpositive/negative名と物理edgeを同一視しない。

現在のホストはTX unitを16bitとし、DMAに各wire byteを2byteへpackし、TXD0..7だけを物理DATAへ出す。TXD15は内部VALIDによるclock gate制御で物理DATAへ出していない。RXは8bit内部master。従ってどちらも物理1clockあたり1byte、8MHzは各方向raw8MB/s。TX16bitだから物理16MB/s、あるいはTX/RX同時合計16MB/sとはしない。MEMリンクは同じDATA8bitをDIRで交互利用するhalf-duplexで、TRMのcontroller full-duplex可能というfeatureをこのキャリアの同時転送能力へ流用できない。

公式RX finite repeated試験は1bit/1MHz/固定5120B・主にcallback数を確認し、8bit/可変24→4122Bの完全CRC比較とは異なる。P4はSDK v5.5.2 test_apps/parlio/pytest_parlio_unity.pyでrev3 migration理由のtemp_skip_ci。これをrev1.3でreset省略可能という証拠にしない。

## 推論：現在の4KiBプロトコルの理想的wire上限

4KiB tagged WR requestは4114B、ACK8B、RD request18B、RD response4106B。ヘッダ/CRCだけを含めた最少合計8246Bでpayload8192B（WR4096＋RD4096）。8MHz・1byte/clockならpayload最大 `8×8192/8246 = 7.9476MB/s` 程度。この値はprefix、DMA capture余裕、DIR切替、READY待ち、DDR、reset、cache、CPU検証を全部0と仮定した楽観的な計算値。

現ホスト設定のpreamble1/要求、RXmargin16/応答を含めると、WR TX4115＋RX24、RD TX19＋RX4122、合計8280clock機会となる。最低wire時間は `4134/f_TX + 4146/f_RX` 秒/WRRD組、payload8192B。両8MHzなら1.035ms/組、平均0.5175ms/要求、理想payload上限約7.9150MB/s。両40MHzなら算術上39.5749MB/sだが、P4controller公称値に当てはめただけでFPGA/基板/現RTLが可能という意味ではない。実際には停止まで余分に回るclockやガードもあるので8280は観測waveformの厳密な全pulse数ではなく、必要なbyteclockからの下界。

現qualified通信側の平均1.325920ms/要求と比べ、この最低wire時間だけでも約39%を占める。残差約0.808420ms/要求にはsoftware/IRQ/scheduler/cache/reset/切替だけでなく、FPGA応答準備・DDR待ち・安全なguardも含まれる。差分すべてをGPIO汎用API費用とは呼べない。worker CPU runtimeはISR課金もあり、CPUとwire/待ちは重なるため比率を単純加算しない。

## 未確認・結論の境界

- 公称40MHzはP4controller単体のIO上限。TX16bit内部VALID15/physical8とRX8masterについて、今回のpad/負荷/方向条件で個別40MHz動作を保証するAC条件は未確認。
- TX側はFPGA SYS27受信器のsample latency/hold条件、RX側はFPGA返信filter/serializer位相とP4 physical sampling windowを別々に評価する必要がある。ホストAPI overhead削減だけではwire FORMAT/CRC不合格の原因を解消できない。
- 現在のA0A9＋a72b75eではTX/RX両8MHzが有界PASS、両10MHzの最初WRがFORMATで不合格。これは現imageの両方向条件であり、RX上限が8MHzという意味ではない。
- 歴史上はD7F5（reply phase3）＋host ELF `0195a00bd1ef4ab4f667e6f4b155eaaeba4dabffc07e57b0d10a88ffa20471d6`、TX2MHz positive/RX20MHz positiveで202段階・617frame PASSを確認している。同FWでA0A9へ戻すRX20対照は失敗し、返信位相依存の別profile。現在のA0A9/8MHz均衡profileと混同せず、RX20到達済みの事実を残す。根拠：`docs/MEMV1_再開記録_2026-11-05.md` のphase3記録、および `fpga/validation/memv1-resume-2026-11-05/phase3-qualification-summary.json`。
- TXとRXの周波数上限/位相は別評価が必要。8PASS/10FAILも過去RX20PASSも、P4/FPGA/基板全体の絶対最高周波数の証明ではない。
- GPIO matrix/IO MUXの伝搬遅延、pad Tco、FPGA同期/入力hold、配線skew、反射、duty、温度電圧を含むtiming budgetが未確定。SPI専用のmatrix timing/delay規則をPARLIOへそのまま適用しない。
- 現在の律速を「CPU/GPIO汎用性だけ」とは断定できない。確認できたことはguard、allocation、MMIO、packing、zero/cache、route、試験期待値処理を個別に減らすとjob時間が減ったこと。更なるclock上昇やreset削減には別の証拠が必要。

## 目標「実効8MB/s近辺」へ向けた方向別の読み方

raw8MHz・1byte/clockではprotocol overheadがあるため厳密なpayload8MB/sは達しない。ただしユーザー目標は8MB/s近辺として評価し、丸め差だけで達成不能とは扱わない。現preamble/capture条件でwire最少値約7.915MB/sはraw限界近辺の算術値で、準備/検証/DDR/切替をさらに含む実効値には追加の余裕が必要。

TX2/RX20の歴史profileはRX20到達の証拠だが、WR/RD均衡jobの実効8MB/sを証明しない。上記byteclock式なら4134/2MHz＋4146/20MHz＝2.2743ms/WRRD組、payload8192Bでwire上限約3.602MB/sに制限される。一方、仮にTX8/RX20なら下界0.72405ms/組・約11.31MB/sとなるが、これは異なるimage/phaseの成功条件を組み合わせた未実証の仮定。実装変更なしの現段階では、TX要求受信限界とRX返信位相を個別に整理し、両方成立するprofileを見つける課題として記載する。
