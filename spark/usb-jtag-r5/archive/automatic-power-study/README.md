> 破棄した初期検討。ユーザー指定により手動ジャンパ版へ置換。現行設計は上位のREADMEとKiCadファイル。

# USB給電・JTAG対応 r5（KiCad設計中）

2026-11-03。現行の `../single-sided-r4/`（Full/Lite、EasyEDA、見積データ、公開物）を保持し、Full版を基に次版を別設計として作成する。正の設計は `full/design/kicad/tab5-fpga-carrier-r5.kicad_sch` と同名PCB。**設計レビュー用。製造・発注用ではない。** 廉価版はr4のままで、r5の検証を転用しない。

## 使用条件

Tab5のバッテリーは装着不可。外部給電のみを前提とする。PC接続時はTab5を起動する必要がない。PC用USBとPD入力は同じJ2であり、同時に2本のケーブルは接続しない。

| 入力 | Core／周辺回路 | Tab5 |
|---|---|---|
| PC USB-C 5V、1.5A以上を広告するSource、C-Cデータケーブル、JP2=2–3 | USB設定後に給電しJTAG書き込みする設計 | HVIN経路OFF、バスOFF |
| PC USB 5V、標準500mA枠、JP2=1–2 | デバッガ認識。低電流試験は可能だがCoreの書き込み動作は保証しない | OFF |
| USB PD 12V | 給電。JP2=1–2でも高電流側を選択 | 給電 |
| 安定化バレル12V | 給電 | 給電 |
| PC USB＋バレル12V | PCからJTAG。12V側で全体へ給電 | 給電 |

**USB 2.0の500mAだけでCore全体を保証できる、という前段の見込みは採用しない。** Sipeed公式データシートp3はCore電源を5V±10%、0.5Aと指定する。USB–JTAGの電力が別に必要である。JP2=2–3はUSB-Cの1.5A以上の電流広告を確認したSource専用で、USB-A変換ケーブル、単に「USB3ポート」と呼ばれるポート、広告電流不明のポートでは使わない。**本版にはCC広告電流の自動検出はない。** JP2の出荷時設定は1–2（安全側）。適合するPC Sourceがない場合はバレル給電を併用する。

## 電源回路

```text
J2 VBUS 5/12V → U11 TPS259470（UV/OV、逆流阻止） ┐
                                                ├→ SYS_IN → U2 TPS630701 → SYS_5V
J1 12V → F1 → U21 TPS259470（UV/OV、逆流阻止） ─┘                    ├→ FT232H
                       SYS_IN → U12 高電圧限定 → VIN → Tab5 HVIN      └→ U13 → +5V → Core・周辺
```

- r4のD1/D2ショットキーORとTPS5430を置換する。USBの電圧降下を小さくするため、逆流阻止付きeFuse同士をORし、昇降圧で5Vを生成する。**VBUSからCoreへの直通バイパスはない。** 12VへのPD遷移中もCoreはレギュレータの出力側にある。
- U11のUVLO立上り公称4.188V、U21/U12は10.644V。3個ともOVLO公称13.2V。部品誤差とヒステリシスは `full/design/kicad/sim/electrical-review.json` で計算する。バレル24V／PD20V対応ではない。
- U12は5VではTab5 HVINを切り離す。TAB_3V3、CORE_PGOOD、JP1 ARMによる既存バス分離を維持する。Tab5の5V/BAT出力は接続しない。
- Core／周辺への給電条件は `REG_PGOOD AND (USB_CONFIGURED OR HV_VALID)`。USB切断／Suspend時は、HVがない限りCoreを停止する。PD交渉／給電元の切替時に無瞬断であるとは主張しない。
- U13 TPS2553はR74=150kΩ。高電流許可時はQ6経由でR75=39kΩを並列にする。1.5AはUSB入力の条件であり、Coreへ1.5Aを供給する指定ではない。Coreだけでなく+5V以下のLED・HDMI等を含む電流枠である。
- eFuseのOVLOは静的閾値による保護。高速サージ、投入電流、短絡、PD遷移、相互逆流、熱、ループ安定性は実機／回路シミュレーション未検証。簡易状態表の合格をその検証に代用しない。

## USB–JTAG

J2を16接点USB2対応コネクタへ変更。CC1/CC2は従来のCH224K（12V要求）へ、D+/D−はFT232HLへ接続する。CH224KのDP/DMは未接続を維持し、USBデータ線へ接続しない。USB ESDのクランプ先に12V VBUSを使用しない。

FT232HLのADBUS0/1/2/3をTCK/TDI/TDO/TMSに使用し、Ioff対応SN74LVC125Aを介してJ9へ出す。バッファはCore側の周辺3.3Vで給電する。Core上の8P JTAG/UARTへ短いケーブルで接続する構成で、未確定のSODIMM JTAGピンへ配線を割り当てない。

| J9 | Core側信号 |
|---|---|
| 1 | NC（Coreの+5Vを重複給電しない） |
| 2 | TMS |
| 3 | TDO |
| 4 | TCK |
| 5 | TDI |
| 6、7 | NC（UART不使用） |
| 8 | GND |

ピン表は保存済みSOM-3961回路図のJTAG/UARTブロックを参照。**実物Coreの版、J9/相手側の嵌合面、ケーブルのピン1を確認するまで接続しない。** 外部ライターとの同時駆動は禁止。r5はCoreへこのケーブルを接続して使用する仕様であり、SODIMMを差すだけではUSB書き込みできない。

93LC56B EEPROMは必須。FT_PROGでACBUS0=PWREN#、ACBUS7 lowでSuspend、USB最大電流500mA、I/O弱駆動／Slowを設定する。USB-C電流広告はUSB descriptorと別の条件。EEPROMが空の場合、ACBUS0のpull-upとR78によりUSB単独のCore給電を抑止し、FT_PROGから初期設定する。EEPROM書き込み・実機動作は未実施。

openFPGALoaderではFT232Hケーブル設定を使用する。`tangprimer20k`プリセットのFT2232設定を無条件に流用しない。VID/PID、インターフェース番号、JTAG周波数を実機で確認し、初回は1MHz以下で識別→SRAM書き込み→フラッシュの順に検証する。USBやフラッシュへの書き込みは今回実施していない。

## ホスト照合と継承

`host-review.json` は参照コミット・資料SHAを記録する。Linux本体のREADME、DEVELOPMENT_GOALS、Device Treeも確認し、研究リポジトリだけで代替していない。現在のローカルLinuxツリーには `tools/fpga-link/transport.py` もFPGA通信ドライバもなく、未実装として扱う。MeOSのGPIO／LINK／GFX実装、ESP-IDFの診断GPIO・表示実装も照合する。

通常の12V給電時はM5-Bus／Core通信ピンとデバイスコマンドをr4から変更しないため、ESP-IDF／MeOS／Linuxのホストプロトコル変更は不要という設計判断。USBのみの書き込み時は全OSを停止する。ホストの給電条件・書き込み手順へのr5反映は必要だが、r5未リリースのためホスト各リポジトリは未更新。DDR3や各ビットストリームの動作／性能を新たに検証したものではない。

## 再生成・状態

```powershell
python -X utf8 spark/usb-jtag-r5/full/design/kicad/gen/build_r5.py
& 'C:/Program Files/KiCad/10.0/bin/python.exe' spark/usb-jtag-r5/full/design/kicad/gen/derive_pcb.py
python -X utf8 spark/usb-jtag-r5/verify_design.py
```

回路図は部品モデルから再生成する。PCBはr4の嵌合位置と変更しない信号配線を継承し、新規回路の配置・配線を行う。`make_pcb.py`／`route_pcb.py` は初期検討用で、r5の正規再生成入口は `derive_pcb.py`。r4製造・公開用スクリプトはr5に使用しない。

**製造リリース前の必須残件：** PCB DRC／未配線0、電源ICの参照レイアウト照合、USB差動インピーダンスとスタブ・配線長差、クリスタル周辺、TI特殊ランドの銅箔・マスク・ペースト確認、コネクタ嵌合／Core上空のケーブル、LCSC部品確定、電源・USB・JTAG・全ホストの実機試験。r4のDRC0やEasyEDA結果はr5の合格実績に転用しない。Gerber／CPL／発注ZIPは作らない。

## 一次資料

- [Sipeed Tang Primer20K公式](https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html)、本リポジトリ `docs/reference/tang-primer-20k/SOM-3961_Schematic.pdf` とデータシートp3。
- [TI TPS63070/701 Rev.B](https://www.ti.com/lit/ds/symlink/tps63070.pdf)：固定5V、16V入力、RNM0015Aランド。
- [TI TPS25947 Rev.C](https://www.ti.com/lit/ds/symlink/tps25947.pdf)：逆流阻止、UVLO/OVLO、RPW0010Aランド。
- [TI TPS2553 Rev.G](https://www.ti.com/lit/ds/symlink/tps2553.pdf)：電流制限と誤差式。
- [FTDI FT232H v2.2](https://ftdichip.cn/Support/Documents/DataSheets/ICs/DS_FT232H.pdf)：5Vモード、MPSSE、93LC56B、PWREN、VBUS検出。
