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

## Status
* Schematic: ERC opens; netlist matches the data model (0 mismatches).
* PCB: **103 / 103 nets auto-routed** (3 routing layers + rip-up & reroute), GND via In1/In2 planes, F/B pours and 84 stitching vias.
  DRC: 0 errors; warnings only (silkscreen overlap, 3 hole-to-hole). One GND island (pad R33.2) is still reported unconnected.
* **Not manufacturing-ready**: HDMI TMDS pairs are not impedance/length matched; M5-Bus pin-1 orientation, board outline and
  mounting-hole pattern must be checked against the real Tab5; SODIMM 3D model and LCSC part selection are open (see `bom.csv`).
* Pipeline: `make_sch.py` -> `make_pcb.py` (place + route) -> `finish_pcb.py R33.2` (touch-ups, zone refill).
* No Ethernet / MIPI / USB-host (see site spec).
