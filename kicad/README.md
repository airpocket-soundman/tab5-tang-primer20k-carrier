# KiCad design data (v2.0 draft)

Tab5 x Tang Primer 20K carrier. Generated from a single data model so that the schematic and the PCB always agree.

| File | Content |
|---|---|
| `tab5-fpga-carrier.kicad_pro / .kicad_sch / .kicad_pcb` | KiCad 10 project (schematic A0, 4-layer PCB 125x78 mm) |
| `lib/carrier.kicad_sym`, `lib/carrier.pretty/` | Core SODIMM symbol + Sipeed footprint (LCSC C367004), RCLAMP0524P symbol |
| `gen/design.py` | Parts, nets, Core pin map (verified against the Sipeed SOM schematic), placement data |
| `gen/make_sch.py` | Writes the schematic (normal Python 3) |
| `gen/make_pcb.py`, `place_pcb.py`, `route_pcb.py`, `finish_pcb.py` | Board, placement, router with coupled-pair routing, touch-ups (KiCad's Python) |
| `gen/make_bom.py` | `bom.csv` and `core_pin_assignment.csv` |
| `sim/` | HDMI signal-integrity tools: 2D field solver, channel analysis, S-parameter estimate (see `docs/HDMI_信号品質_調査と方針.md`) |

Regenerate:

```
python -X utf8 kicad/gen/make_sch.py
"C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 -u kicad/gen/make_pcb.py      # place + route, ~7 min
"C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/gen/finish_pcb.py NONE.0  # touch-ups, GND island vias, zone refill
kicad-cli pcb drc --severity-error --all-track-errors ...                            # 0 violations expected
"C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/tmds_channel.py --extract
python -X utf8 kicad/sim/tmds_channel.py ; python -X utf8 kicad/sim/tmds_sparam.py   # needs numpy, scipy, matplotlib
```

## Layout (v2.0)
* M5-Bus header in the middle; the Core (SODIMM) sits RIGHT of it, rotated 180 deg, card extends to the right. 33R series resistors in between.
* HDMI Type-A on the right edge, upper part (the keyboard attaches to the bottom). Power input, USB-C PD, buck, LDO on the left.
* Switch row at the top left: FPGA ON/OFF slide switch (THT), user button, Tab5 reset button. PMOD x2 and spare-IO pads (1x9) on the right: **pads only, headers DNP**.
* Rules: parts other than HDMI / USB-C / DC jack stay 2.5 mm from the outline; every part stays 5 mm from the M3 holes; USB-C >= 10 mm from the screws.
* HDMI circuit follows the official Tang Primer 20K Dock: 100 nF AC coupling, 499R bias, RCLAMP0524P (TMDS) and SRV05-4 (DDC/HPD) ESD.
  TMDS pairs: TX1/TX2/TX3/TX5 (TX4 is 1.9 mm skewed inside the Core board). **D2 uses TX5 with P/N swapped on the pins: invert the D2 data bits in the FPGA.**
* TMDS pairs are routed as coupled pairs (0.2 mm / 0.13 mm gap, nested vertical lanes): intra-pair skew 0.00 mm, ~104 ohm differential on F.Cu (2D solver).

## Status
* Schematic: ERC 0 violations; netlist matches the data model.
* PCB: **113 / 113 nets routed**, **DRC: 0 errors, 0 unconnected** (silkscreen warnings only).
* HDMI channel (4-port estimate, report r3): worst-pair SDD11 <= -12.9 dB up to 1.5 GHz, SDD21 -0.88 dB at 742 MHz, SCD21 <= -24.9 dB (mode conversion). Combined sensitivity (Core Z x ESD C): Core 85 ohm x ESD 0.35 pF (-9.1 dB), Core 85 ohm x ESD 0.50 pF (-7.9 dB) fail the -10 dB goal. 3D EM validation (openEMS) not done.
* **Not manufacturing-ready**: M5-Bus pin-1 orientation, outline and holes must be checked against the real Tab5; part classes and the Core SODIMM 3D model are open (see `bom.csv`); the slide switch footprint is generic (hand-fitted);
  FPGA constraint file (.cst) still to be written from `core_pin_assignment.csv`.
* No Ethernet / MIPI / USB-host (see site spec).

## Known issues
* **TMDS ESD (U4/U5, LCSC C293965 = DOWO RCLAMP0524P, DFN2510-10L)**: fixed on the board side. Each line is continuous copper (pad 1-10, 2-9, 4-7, 5-6 are strapped with copper) and the ESD is a tap, so the design no longer depends on any internal pin connection. Footprint `carrier:DFN2510-10L_RCLAMP0524P` (own, from the DOWO outline, GND land widened to 0.42 mm; the datasheet has no land pattern - check JLCPCB's footprint and pin-1 orientation when ordering, `docs/ESD_フットプリント照合_RCLAMP0524P.md`).
* **499 ohm bias resistors** now hang on 2-11 mm branches (was 21-53 mm); D1 N side is 11.5 mm (target: a few mm). They are included in the channel estimate.
* Target is **720p60 only** (1080p60 exceeds the GW2A serializer limit of 1200 Mbps). **Invert the D2 data (all serial bits after TMDS encoding)** in the FPGA.
* Channel estimate (4-port model, P/N branches at their own taps; report r3): see the Status line. The 3D solver (openEMS) is not calibrated and is not used for conclusions.

## Checks (exit code 1 on failure; KiCad python unless noted)
`sim/check_continuity.py` (copper continuity + expected pin numbers), `sim/check_negative.py` (remove each ESD strap, exactly that line must fail), `sim/check_classification.py` (every TMDS track/via belongs to main/stub/strap/branch), `sim/check_esd_footprint.py` (footprint vs DOWO datasheet), `kicad-cli pcb drc`. Model/report (system python): `sim/tmds_channel.py`, `sim/tmds_sparam.py` (4-port P/N model), `sim/make_report_figs.py`, `sim/make_manifest.py` (SHA-256 of all inputs/results), `sim/make_report_page.py` -> `site/hdmi-simulation-r3.html`. FPGA side: `docs/FPGA_HDMI要求_D2反転とピン.md`.

## 第3版の追加監査への検査修正（2026-10-24）

配置済みランドの寸法とPCB／モデルの配線幅を検査し、二重分類・部分的stale・ビア形状も検出するよう修正。正常と故障注入の計24ケースに成功した。D2の色説明を赤へ訂正し、符号語と制御期間のRTL試験要求を登録した。回路・PCB・チャネルモデルは変更していない。

詳細：[検査修正と再現手順](../docs/HDMI_R3_検査修正_2026-10-24.md)、公開追記：[hdmi-audit-checks.html](../site/hdmi-audit-checks.html)。
