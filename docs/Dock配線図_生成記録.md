# Dock配線図の生成・参照記録

2026-10-28。既存の配線仕様をHTML/SVGへ図解化。ピン、電源、通信、コマンドは変更しない。全ホスト共通の物理配線であり、各ホストへの仕様同期は不要。

- HTML：`site/dock-jumper-wiring.html`
- SVG：`site/img/dock-jumper-wiring.svg`（写真を内包し単独表示可能）
- 再生成：`python tools/build_dock_wiring.py`。正本のMarkdown表から15信号を抽出する。
- Dock部品面写真：Sipeed公式Wiki https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html の `https://wiki.sipeed.com/hardware/zh/tang/tang-primer-20k/assets/dock-up.png`。2026-10-28取得。ローカル保存：`docs/reference/tang-primer-20k/dock-up.png`。J5/J12/J14の相対位置を目視確認。写真からDockヘッダの1番方向は確定できず、図でも物理配列として描かない。実物照合が必要。
- Tab5裏面の向き：`docs/reference/tab5/mbus_orientation_confirmation_2026-10-24.json`。電池区画が左、M5-Bus左上が1番。
- 電気的対応と抵抗・GND条件：`Dockジャンパ試験_配線とFPGA構成_2026-10-28.md`。本図は実機配線・電気特性の検証ではない。

作業開始時に確認したローカルホスト参照版（未コミット作業ツリーを含む。リリース版ではない）：

| 対象 | HEAD | 確認内容 |
|---|---|---|
| ESP-IDF tab5-fpga-gpu | 3b1ace3 | README、Project_B、bringup/tab5/main/main.c と CMakeLists.txt、main/lab.hpp。独立診断のGPIO通信・gfx_lcd実装あり。GPU LABのFPGA backendはREADMEでは未実装 |
| Linux tab5-linux-fpga | e599ec9 | README、DEVELOPMENT_GOALS、linux/dts/easystick-stamp-p4.dts、tools一覧。GPIO bank定義あり。toolsにFPGA通信ツールを確認できず、物理通信の完成・実機検証は確認できない |
| MeOS tab5-meos-fpga | 7607793 | README、FPGA_CARRIER_REQUIREMENTS、drivers/fpga/fpga_gpio.c/.h。作業ツリーにGPIO backendあり。古い資料の「物理backend未実装」は現作業ツリーを表さない。実機検証済みとは扱わない |
| esp32p4-linux-fpga-memory | e4aa69d | README、docs/Project_A_P4_Linux_FPGA_Virtual_MMU.md。明示的READ/WRITE・外部データ領域の研究要求。今回の配線図でDDR3の動作やLinuxメインRAM拡張を示すものではない |

## ピン配置模式図の追加（2026-10-28）

`site/img/dock-header-pinout.svg`にJ5/J12/J14の各12ピンを追加。回路図記号を横展開し、上段奇数・下段偶数、1番四角、信号名・用途・Tab5接続先を表示。物理方向の確定とはしない。

公式Wikiのdock-back.pngを取得し、RGB LCDのR0〜G2対応ヘッダの電源シルクが端から3.3V、GNDと読める一方、保存済みPDFではJ5の1/2=GND、3/4=3.3Vである差異を確認。写真と回路図の版の対応は未確認。保存済みDock_3714_Schematics.pdfの物理4/8/9ページを描画確認したところ、図枠はDock_3713、Rev 1.1、2023-09-12だった。既存資料の「Rev1.3、2026-05-20」は今回の描画では確認できず、番号の実装方向を固定する根拠には使わない。ピン仕様は変更せず、HTMLに差異と要確認事項を記載した。

ブラウザで模式図の表示、画像読み込み、幅390px時の横はみ出しなしを確認。SVG XMLの解析成功。実機の番号向き・導通・電圧は未確認。

## 写真上の1番ピン特定（2026-10-28）

前節の「写真上の向きは未確定」は公式配置データについて解消。公式配布の `TANG/Primer_20K/03_Bit_number_map/Dock/Tang_Primer_20K_Dock_3709_ibom.html` を取得し、内包するpcbdataを展開した（Dock_3709_pcbdata.json）。J5のpin1は(172.19,88.4)、J12は(210.376666,88.4)、J14は(229.47,88.375)。全て矩形パッド・pin1=1で、部品面の左下にある。他方の行はY=85.86前後、右方向に2.54mm刻み。USB下の公式写真と信号シルクを照合した。

したがって掲載旧版写真は各ヘッダ左下が1番、上段偶数・下段奇数で右へ増える。写真のJ5は1/2=3V3、3/4=GND、5=L9、6=N8。3713系回路図のJ5は電源ペアが逆なので、旧版写真に現行電源表を当てはめない。公式Readmeも3708/3709を旧版扱いとしている。3709配置データだけで手元の3713/3714の実装向きを保証しない。信号仕様の変更はなし。HTMLと写真SVGに版の違いを注記。

## ユーザー実物シルクに基づく図解訂正

J5の上段=3V3/GND/N8/N7/D11/B11、下段=3V3/GND/L9/N9/N6/A11をユーザーが確認。写真と同じ向きに統一し、全模式図を上段偶数・下段奇数へ訂正。J5は1/2=3V3、3/4=GNDへ変更し、HTML・結線SVG・Markdown試験手順のGND指示も合わせた。回路図との差異は版比較として残し、実物配線の主図に混在させない。信号・GPIO・コマンドは変更なし。ホストコード変更は不要（GND配線説明の訂正のみ）。J12/J14の手元実物確認は未完了。表示確認と390px幅のはみ出し確認を実施。
