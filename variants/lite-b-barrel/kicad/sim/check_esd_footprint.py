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
TOL_MM = 0.001


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


def compare_placed(fp, expected):
    """Compare the actual embedded pads, not merely the library identifier.

    Apply the same side and orientation to a fresh library footprint. Relative
    positions then remove translation/rotation without losing mirrored pin IDs.
    """
    # KiCad Flip requires an owning board (a bare library footprint can crash).
    expected_board = pcbnew.BOARD()
    expected_board.Add(expected)
    if fp.IsFlipped():
        expected.Flip(expected.GetPosition(), False)
    expected.SetOrientationDegrees(fp.GetOrientationDegrees())
    actual_pads = list(fp.Pads())
    reference_pads = {p.GetNumber(): p for p in expected.Pads()}
    numbers = [p.GetNumber() for p in actual_pads]
    tag = fp.GetReference()
    check(tag + ": exactly ten unique pads 1..10",
          sorted(numbers) == sorted(reference_pads), numbers)
    for method in ("GetLocalSolderMaskMargin", "GetLocalSolderPasteMargin", "GetLocalSolderPasteMarginRatio"):
        check(tag + ": footprint " + method, getattr(fp, method)() == getattr(expected, method)(),
              str(getattr(fp, method)()))
    for pad in actual_pads:
        number = pad.GetNumber()
        if number not in reference_pads:
            continue
        ref = reference_pads[number]
        pos, rpos = pad.GetFPRelativePosition(), ref.GetFPRelativePosition()
        size, rsize = pad.GetSize(), ref.GetSize()
        angle = (pad.GetFPRelativeOrientation().AsDegrees() - ref.GetFPRelativeOrientation().AsDegrees() + 180) % 360 - 180
        geometry_ok = (abs(mm(pos.x-rpos.x)) <= TOL_MM and abs(mm(pos.y-rpos.y)) <= TOL_MM
                       and abs(mm(size.x-rsize.x)) <= TOL_MM and abs(mm(size.y-rsize.y)) <= TOL_MM
                       and abs(angle) <= 0.001 and pad.GetShape() == ref.GetShape()
                       and pad.GetAttribute() == ref.GetAttribute()
                       and abs(pad.GetRoundRectRadiusRatio()-ref.GetRoundRectRadiusRatio()) <= 1e-6)
        check(tag + "." + number + ": placed pad geometry matches library", geometry_ok,
              dict(position_mm=[mm(pos.x), mm(pos.y)], size_mm=[mm(size.x), mm(size.y)], angle_delta=angle))
        check(tag + "." + number + ": placed pad layers match library",
              pad.GetLayerSet().FmtBin() == ref.GetLayerSet().FmtBin(), pad.GetLayerSet().FmtBin())
        for method in ("GetLocalSolderMaskMargin", "GetLocalSolderPasteMargin", "GetLocalSolderPasteMarginRatio"):
            check(tag + "." + number + ": " + method,
                  getattr(pad, method)() == getattr(ref, method)(), str(getattr(pad, method)()))


# library footprint
lib_fp = pcbnew.FootprintLoad(LIB, "DFN2510-10L_RCLAMP0524P")
check("library footprint DFN2510-10L_RCLAMP0524P exists", lib_fp is not None, "")
if lib_fp is not None:
    inspect(lib_fp, "library")

# placed parts: footprint name, pad->net mapping (I/O 1,2,4,5 on a line net, GND 3,8, 6/7/9/10 joined by copper to their line)
board = pcbnew.LoadBoard(PCB)
placed = {}
references = [fp.GetReference() for fp in board.GetFootprints() if fp.GetReference() in ("U4", "U5")]
check("exactly one U4 and one U5", sorted(references) == ["U4", "U5"], references)
for fp in board.GetFootprints():
    if fp.GetReference() in ("U4", "U5"):
        compare_placed(fp, pcbnew.FootprintLoad(LIB, "DFN2510-10L_RCLAMP0524P"))
        nets = {p.GetNumber(): p.GetNetname() for p in fp.Pads()}
        name = fp.GetFPID().GetLibItemName()
        check("%s uses DFN2510-10L_RCLAMP0524P" % fp.GetReference(), str(name) == "DFN2510-10L_RCLAMP0524P", str(name))
        check("%s GND pads are 3 and 8" % fp.GetReference(), nets.get("3") == "GND" and nets.get("8") == "GND", (nets.get("3"), nets.get("8")))
        io_ok = all(nets.get(k, "").startswith("HDMI_") and nets.get(k, "").endswith("_C") for k in ("1", "2", "4", "5"))
        check("%s I/O pins 1,2,4,5 on the TMDS lines" % fp.GetReference(), io_ok, {k: nets.get(k) for k in ("1", "2", "4", "5")})
        tie_ok = all(a in nets and b in nets and nets[a] == nets[b] for a, b in (("1", "10"), ("2", "9"), ("4", "7"), ("5", "6")))
        check("%s NC pins 6/7/9/10 share their line net (copper verified separately)" % fp.GetReference(), tie_ok, {k: nets.get(k) for k in ("6", "7", "9", "10")})
        placed[fp.GetReference()] = dict(nets=nets, pos=[round(mm(fp.GetPosition().x), 3), round(mm(fp.GetPosition().y), 3)], rot=fp.GetOrientationDegrees())
for fp in board.GetFootprints():
    if fp.GetReference() == "U6":
        compare_placed(fp, pcbnew.FootprintLoad(LIB, "DFN2510-10L_RCLAMP0524P"))
        nets = {p.GetNumber(): str(p.GetNetname()) for p in fp.Pads()}
        expected = {"1":"HDMI_SDA","10":"HDMI_SDA","2":"HDMI_5V","9":"HDMI_5V","3":"GND","8":"GND","4":"HDMI_SCL","7":"HDMI_SCL","5":"HDMI_HPD","6":"HDMI_HPD"}
        check("U6 independent-ground sideband ESD mapping", nets == expected, nets)
report = dict(ok=not fails, failed=fails, checks=checks, placed=placed)
output = os.environ.get("CHECK_JSON") or (os.path.join(HERE, "esd_footprint_check.json") if not os.environ.get("CHECK_PCB") else None)
if output:
    json.dump(report, open(output, "w"), indent=1, ensure_ascii=False)
print("ESD footprint check:", "OK" if report["ok"] else "FAILED", "(%d checks)" % len(checks))
for c in checks:
    print(" ", "ok  " if c["ok"] else "FAIL", c["name"])
sys.exit(0 if report["ok"] else 1)
