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
* PCB: **121 / 121 nets routed**, **DRC: 0 errors, 0 unconnected** (silkscreen warnings only).
* HDMI channel (estimate, differential mode only): SDD11 <= -14 dB up to 1.65 GHz (worst -12.8 dB to 3.3 GHz), SDD21 about -0.3 ... -0.9 dB. 3D EM validation (openEMS) not done.
* **Not manufacturing-ready**: M5-Bus pin-1 orientation, outline and holes must be checked against the real Tab5; ESD footprint / part classes and the Core SODIMM 3D model are open (see `bom.csv`); the slide switch footprint is generic (hand-fitted);
  FPGA constraint file (.cst) still to be written from `core_pin_assignment.csv`.
* No Ethernet / MIPI / USB-host (see site spec).

## Known issues (must be fixed before ordering)
* **TMDS ESD (U4/U5, LCSC C293965 = DOWO RCLAMP0524P, DFN2510-10L)**: the board assumes the IN pins (1/2/4/5) are internally connected to the OUT pins (10/9/7/6). The vendor datasheet only defines I/O = pins 1,2,4,5 and GND = 3,8, so this is **not guaranteed**. Route each TMDS line as continuous copper and connect the ESD as a shunt tap, or use a part with a guaranteed flow-through.
* **499 ohm bias resistors** hang on 21-53 mm branches (CKN 53.5 mm). Move them to the tap points (a few mm).
* Target is **720p60 only** (1080p60 exceeds the GW2A serializer limit of 1200 Mbps).
* The HDMI channel estimate (`docs/HDMI_信号品質_調査と方針.md`) does not include the two items above; re-run it after the fix.
