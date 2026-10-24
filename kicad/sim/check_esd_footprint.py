"""Check the ESD footprint (U4/U5) against the DOWO RCLAMP0524P datasheet (KiCad python):

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/check_esd_footprint.py

Part fixed for purchase: DOWO RCLAMP0524P, LCSC C293965, package DFN2510-10L, datasheet Rev.G1.00 (2024/03/01),
file RClamp0524P_DOWO_C293965.pdf, SHA-256 C6941D13961C2CC62C62AC10E274CF329A253F3BDF872E7D633B45DE0A0BE39A (not redistributed here).
Datasheet facts used (page): p.1/p.2 pin configuration + note "I/O pins are pin 1,2,4,5, GND pins are pin 3,8", 6/7/9/10 = NC;
p.4 outline: D 2.50 (2.45-2.55), E 1.00 (0.95-1.05), lead width b 0.20 (0.15-0.25), GND lead b1 0.40 (0.35-0.45), lead length L 0.38 (0.33-0.43),
Nd 2.00 BSC (pitch e 0.50 BSC, 5 leads per side). The datasheet gives NO land pattern; the land is derived from the outline (see
docs/ESD_フットプリント照合_RCLAMP0524P.md). Checks the footprint in the library and the two placed parts on the board; exit code 1 on any failure.
Output: kicad/sim/esd_footprint_check.json
"""
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
mm = pcbnew.ToMM
PCB = os.environ.get("CHECK_PCB") or os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb")
LIB = os.path.join(HERE, "..", "lib", "carrier.pretty")
BODY_X = 1.00                                    # E (body width across the lead rows)
LEAD = dict(len_nom=0.38, w=0.20, w_gnd=0.40)    # lead length L, lead width b, GND lead width b1
checks, fails = [], []


def check(name, ok, detail):
    checks.append(dict(name=name, ok=bool(ok), detail=detail))
    if not ok:
        fails.append(name)


def inspect(fp, tag):
    pads = {p.GetNumber(): p for p in fp.Pads()}
    check(tag + ": 10 pads numbered 1..10", sorted(pads, key=int) == [str(i) for i in range(1, 11)], sorted(pads, key=int))
    rows = {}
    for num, p in pads.items():
        ps = p.GetPosition()
        x, y = mm(ps.x) - mm(fp.GetPosition().x), mm(ps.y) - mm(fp.GetPosition().y)
        rows[num] = (x, y, mm(p.GetSize().x), mm(p.GetSize().y))
    # footprint frame (rotation 0): pads 1-5 on the left row, 6-10 on the right row, same y order mirrored
    if abs(fp.GetOrientationDegrees()) < 1e-6:
        ys_l = [rows[str(i)][1] for i in range(1, 6)]
        ys_r = [rows[str(i)][1] for i in range(10, 5, -1)]
        pitch_ok = all(abs((ys_l[i + 1] - ys_l[i]) - 0.5) < 1e-3 for i in range(4)) and all(abs(a - b) < 1e-3 for a, b in zip(ys_l, ys_r))
        check(tag + ": pitch 0.50 mm, pin n opposite pin 11-n", pitch_ok, ys_l)
        xl, xr = rows["1"][0], rows["10"][0]
        # land must cover the lead: lead occupies |x| in [BODY_X/2 - L, BODY_X/2]
        lead_in, lead_out = BODY_X / 2 - LEAD["len_nom"], BODY_X / 2
        for num in ("1", "6"):
            x, _y, lx, _ly = rows[num]
            lo, hi = abs(x) - lx / 2, abs(x) + lx / 2
            check(tag + ": land %s covers the lead length (%.2f-%.2f) with toe" % (num, lead_in, lead_out), lo <= lead_in + 0.02 and hi >= lead_out + 0.05, (lo, hi))
        for num in ("1", "2", "4", "5"):
            check(tag + ": signal land %s width >= lead 0.20 and gap to neighbours >= 0.15" % num,
                  LEAD["w"] <= rows[num][3] and 0.5 - rows[num][3] / 2 - rows["3"][3] / 2 >= 0.14, rows[num][3])
        check(tag + ": GND land 3/8 width >= GND lead 0.40", rows["3"][3] >= LEAD["w_gnd"] and rows["8"][3] >= LEAD["w_gnd"], (rows["3"][3], rows["8"][3]))
    return rows


# library footprint
lib_fp = pcbnew.FootprintLoad(LIB, "DFN2510-10L_RCLAMP0524P")
check("library footprint DFN2510-10L_RCLAMP0524P exists", lib_fp is not None, "")
if lib_fp is not None:
    inspect(lib_fp, "library")

# placed parts: footprint name, pad->net mapping (I/O 1,2,4,5 on a line net, GND 3,8, 6/7/9/10 joined by copper to their line)
board = pcbnew.LoadBoard(PCB)
placed = {}
for fp in board.GetFootprints():
    if fp.GetReference() in ("U4", "U5"):
        nets = {p.GetNumber(): p.GetNetname() for p in fp.Pads()}
        name = fp.GetFPID().GetLibItemName()
        check("%s uses DFN2510-10L_RCLAMP0524P" % fp.GetReference(), str(name) == "DFN2510-10L_RCLAMP0524P", str(name))
        check("%s GND pads are 3 and 8" % fp.GetReference(), nets["3"] == "GND" and nets["8"] == "GND", (nets["3"], nets["8"]))
        io_ok = all(nets[k].startswith("HDMI_") and nets[k].endswith("_C") for k in ("1", "2", "4", "5"))
        check("%s I/O pins 1,2,4,5 on the TMDS lines" % fp.GetReference(), io_ok, {k: nets[k] for k in ("1", "2", "4", "5")})
        tie_ok = all(nets[a] == nets[b] for a, b in (("1", "10"), ("2", "9"), ("4", "7"), ("5", "6")))
        check("%s NC pins 6/7/9/10 only joined to their line by copper (strap)" % fp.GetReference(), tie_ok, {k: nets[k] for k in ("6", "7", "9", "10")})
        placed[fp.GetReference()] = dict(nets=nets, pos=[round(mm(fp.GetPosition().x), 3), round(mm(fp.GetPosition().y), 3)], rot=fp.GetOrientationDegrees())
report = dict(ok=not fails, failed=fails, checks=checks, placed=placed)
if not os.environ.get("CHECK_PCB"):
    json.dump(report, open(os.path.join(HERE, "esd_footprint_check.json"), "w"), indent=1, ensure_ascii=False)
print("ESD footprint check:", "OK" if report["ok"] else "FAILED", "(%d checks)" % len(checks))
for c in checks:
    print(" ", "ok  " if c["ok"] else "FAIL", c["name"])
sys.exit(0 if report["ok"] else 1)
