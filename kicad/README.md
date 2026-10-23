# KiCad design data (v0.1 draft)

Tab5 x Tang Primer 20K carrier. Generated from a single data model so that the schematic and the PCB always agree.

| File | Content |
|---|---|
| `tab5-fpga-carrier.kicad_pro / .kicad_sch / .kicad_pcb` | KiCad 10 project (schematic A0, 4-layer PCB ~81x78 mm) |
| `lib/carrier.kicad_sym`, `lib/carrier.pretty/` | Core SODIMM symbol and Sipeed footprint (LCSC C367004) |
| `gen/design.py` | Parts, nets, Core pin map (verified against Sipeed SOM schematic), placement hints |
| `gen/make_sch.py` | Writes the schematic (run with normal Python 3) |
| `gen/make_pcb.py`, `place_pcb.py`, `route_pcb.py` | Board, auto placement, grid A* router (run with KiCad's bundled Python) |

Regenerate:

```
python -X utf8 kicad/gen/make_sch.py
"C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/gen/make_pcb.py
```

## Layout (v1.0 draft)
* Core (SODIMM) on the LEFT of the M5-Bus header (over the battery bay), card extends to the left; 33R series resistors
  between Core and header; HDMI Type-A on the bottom edge; DC jack / USB-C PD / buck / LDO on the right.
* PMOD x2, spare-IO pads (1x9) in the left strip: **pads only, headers not fitted (DNP)**. Reset button (Tab5 RST), FPGA ON/OFF slide switch (buck EN), 3 user buttons, 4 LEDs.
* Pin assignment is optimised for the fan-out (pin swap, `design._apply_pin_swap`) -> see `core_pin_assignment.csv`.
* Placement studies: `gen/study_hdmi.py` (connector position), `gen/study_tmds.py` (TMDS channel <-> TX pair).

## Status
* Schematic: ERC opens; netlist matches the data model (0 mismatches).
* PCB: **106 / 106 nets routed**, GND via In1/In2 planes + F/B pours + 84 stitching vias.
  **DRC: 0 errors, 0 unconnected**; warnings only (silkscreen).
* Pipeline: `make_sch.py` -> `make_pcb.py` (place + route, ~4 min) -> `finish_pcb.py NONE.0` (touch-ups, zone refill) -> DRC.
* **Not manufacturing-ready**: HDMI TMDS pairs are not impedance/length matched (length spread ~17 mm, intra-pair < 5 mm);
  M5-Bus pin-1 orientation, board outline (full Tab5 width) and mounting holes must be checked against the real Tab5;
  Core SODIMM 3D model and LCSC part selection are open (see `bom.csv`); FPGA constraint file (.cst) still to be written from `core_pin_assignment.csv`.
* No Ethernet / MIPI / USB-host (see site spec).
