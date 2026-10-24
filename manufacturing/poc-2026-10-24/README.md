# PoC製造候補 発注保留

M5-Busの物理的な1番端子の位置が未確定です。このフォルダは検査済みCADからの製造候補で、現物照合後に確定します。

- 4層、1.6mm、125×78mm。外層35µm、内層17.5µm、JLC04161H-7628相当。解析の表層-GND間隔0.2104mm。
- 入力12V限定。24V不可。BUS ARMは開放で出荷。
- gerbers.zip: 基板・ドリル。jlc-bom.csv / jlc-cpl.csv: 主要SMD92個、38行。J4 CoreソケットとJ2 USB-Cを含む。
- manual-assembly.csv: J1、J3、J5、SW1/SW2/SW3、JP1、機構部品。dnp.csvは実装しない。
- 座標原点はKiCadの(2,79)mm、出力は右向きX、上向きY、すべて基板内。回転はKiCad規約。業者の部品プレビューで端子1・極性を照合する。
- assembly-top.svg / assembly-bottom.svg: 実装図。下面図は下面から見た鏡像表示。
- package-check.json: 元PCBハッシュ、BOM/CPL一致、各ファイルのSHA-256。

詳細と初回通電手順は docs/PoC発注準備_パラレル通信と電源_2026-10-24.md を参照。
