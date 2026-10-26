"""Negative continuity test (KiCad python): a copper-continuity check is only meaningful if it FAILS when the copper is removed.

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/check_negative.py

For each of the 8 TMDS lines the ESD copper strap that carries the line from the ESD input pad (1/2/4/5) to the output pad (10/9/7/6) is
deleted in a temporary copy of the board; check_continuity.py (CHECK_PCB) must then report exactly that line as discontinuous and all the
others as continuous. Exit code 1 if the check does not detect a removed strap, or flags another line. Output: kicad/sim/negative_report.json
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb")
LINES = ["D2P", "D2N", "D1P", "D1N", "D0P", "D0N", "CKP", "CKN"]
mm = pcbnew.ToMM


def straps(board):
    """{net: track} of the tracks whose two ends sit on two different pads of one ESD part (U4/U5)."""
    pad_pos = {}
    for fp in board.GetFootprints():
        if fp.GetReference() in ("U4", "U5"):
            for p in fp.Pads():
                pad_pos[(fp.GetReference(), p.GetNumber())] = (mm(p.GetPosition().x), mm(p.GetPosition().y))
    out = {}
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or not t.GetNetname().endswith("_C"):
            continue
        a, b = (mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y))
        ends = []
        for pt in (a, b):
            ends.append([k for k, v in pad_pos.items() if math.hypot(v[0] - pt[0], v[1] - pt[1]) < 0.02])
        if ends[0] and ends[1] and ends[0][0] != ends[1][0]:
            out[t.GetNetname()] = t
    return out


def make_negative(line, path):
    """Child mode: save a copy of the board without the ESD strap of `line`."""
    board = pcbnew.LoadBoard(PCB)
    st = straps(board)
    net = "HDMI_%s_C" % line
    if net not in st:
        sys.exit(3)
    board.Remove(st[net])
    pcbnew.SaveBoard(path, board)


if len(sys.argv) == 3:
    make_negative(sys.argv[1], sys.argv[2])
    sys.exit(0)

report = dict(cases={}, ok=True)
tmpdir = tempfile.mkdtemp(prefix="negcheck_")
for line in LINES:
    path = os.path.join(tmpdir, "neg_%s.kicad_pcb" % line)
    jpath = os.path.join(tmpdir, "neg_%s.json" % line)
    rc = subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), line, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    if rc != 0 or not os.path.exists(path):
        report["cases"][line] = dict(error="strap not found / board not written (rc %d)" % rc)
        report["ok"] = False
        continue
    env = dict(os.environ, CHECK_PCB=path, CHECK_JSON=jpath)
    subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "check_continuity.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    r = json.load(open(jpath))
    bad = [l for l, v in r["lines"].items() if not (v["core"]["ok"] and v["carrier"]["ok"])]
    ok = bad == [line]
    report["cases"][line] = dict(detected_as_discontinuous=bad, ok=ok)
    report["ok"] &= ok
json.dump(report, open(os.path.join(HERE, "negative_report.json"), "w"), indent=1)
print("negative test (strap removed -> exactly that line must fail):", "ALL OK" if report["ok"] else "FAILED")
for l, c in report["cases"].items():
    print(" ", l, c)
sys.exit(0 if report["ok"] else 1)
