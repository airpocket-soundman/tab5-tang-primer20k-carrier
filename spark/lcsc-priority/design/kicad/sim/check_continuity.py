"""Copper-continuity check of the TMDS lines (KiCad python):

  "C:/Program Files/KiCad/10.0/bin/python.exe" -X utf8 kicad/sim/check_continuity.py

For every TMDS line the Core pad must reach the HDMI connector pad through copper only (tracks, vias, pads of that net), i.e. WITHOUT
relying on any internal connection of a component. The check walks KiCad's connectivity graph (pad/track/via contacts) and never crosses
a component body: the two pads of the AC-coupling capacitor and the ESD pads count as connected only if copper joins them.
Also reports branch lengths (bias resistors) and the P/N polarity order at the Core and at the connector.
Also checks the PIN MAPPING (not the visual P/N order): each line must land on the expected SODIMM pad and on the expected HDMI Type-A
connector pad (D2+ 1, D1+ 4, D0+ 7, CK+ 10, D2- 3, D1- 6, D0- 9, CK- 12). D2 is deliberately inverted on the Core pins (HDMI_D2P is on
TX5_N pad 56, HDMI_D2N on TX5_P pad 58): the FPGA must invert the D2 serial bits (kicad/core_pin_assignment.csv).
Exit code: 0 only if every line is copper-continuous (Core pad -> cap -> connector pad) and every pin lands on the expected pad.
Output: kicad/sim/continuity_report.json
"""
import sys
import json
import math
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
b = pcbnew.LoadBoard(os.environ.get("CHECK_PCB") or os.path.join(HERE, "..", "tab5-fpga-carrier.kicad_pcb"))
mm = pcbnew.ToMM
conn = b.GetConnectivity()
LINES = ["D2P", "D2N", "D1P", "D1N", "D0P", "D0N", "CKP", "CKN"]


def pads_of(net):
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                out.append((fp.GetReference() + "." + p.GetNumber(), p))
    return out


def reach(start_item, net):
    """Items of `net` reachable from start_item through copper contacts only (no zones, no component-internal links)."""
    seen = {start_item.m_Uuid.AsString(): start_item}
    stack = [start_item]
    while stack:
        it = stack.pop()
        for o in conn.GetConnectedItems(it, getattr(pcbnew, "EXCLUDE_ZONES", 0)):
            if o.GetNetname() != net:
                continue
            k = o.m_Uuid.AsString()
            if k not in seen:
                seen[k] = o
                stack.append(o)
    return seen


def track_len(items):
    tot = 0.0
    for o in items:
        if isinstance(o, pcbnew.PCB_TRACK) and not isinstance(o, pcbnew.PCB_VIA):
            tot += math.hypot(mm(o.GetEnd().x - o.GetStart().x), mm(o.GetEnd().y - o.GetStart().y))
    return tot


EXPECT_CORE = {"D2P": "56", "D2N": "58", "D1P": "68", "D1N": "70", "D0P": "130", "D0N": "132", "CKP": "140", "CKN": "142"}
EXPECT_HDMI = {"D2P": "1", "D2N": "3", "D1P": "4", "D1N": "6", "D0P": "7", "D0N": "9", "CKP": "10", "CKN": "12"}
report = {"lines": {}, "ok": True}
for l in LINES:
    rec = {}
    # core side: J4 pad -> cap pad 1 ; carrier side: cap pad 2 -> ... -> J5 pad
    for tag, net, a_pref, b_pref in (("core", "HDMI_%s" % l, "J4.", "C"), ("carrier", "HDMI_%s_C" % l, "C", "J5.")):
        ps = pads_of(net)
        a = [p for ref, p in ps if ref.startswith(a_pref)]
        bb = [p for ref, p in ps if ref.startswith(b_pref) and (tag == "core" or ref.startswith("J5."))]
        if tag == "carrier":
            a = [p for ref, p in ps if ref.startswith("C")]
            bb = [p for ref, p in ps if ref.startswith("J5.")]
        ok = False
        esd_pads = []
        extra = 0.0
        if a and bb:
            seen = reach(a[0], net)
            ok = bb[0].m_Uuid.AsString() in seen
            esd_pads = sorted(ref for ref, p in ps if ref.startswith("U") and p.m_Uuid.AsString() in seen)
            total = track_len(seen.values())
            rec[tag] = dict(ok=ok, pads_reached=sorted(ref for ref, p in ps if p.m_Uuid.AsString() in seen), copper_len_mm=round(total, 2))
        else:
            rec[tag] = dict(ok=False, error="pads not found")
        report["ok"] &= ok
    pc = [ref for ref, p in pads_of("HDMI_%s" % l) if ref.startswith("J4.")]
    pk = [ref for ref, p in pads_of("HDMI_%s_C" % l) if ref.startswith("J5.")]
    rec["pins"] = dict(core=pc, connector=pk, expect_core="J4." + EXPECT_CORE[l], expect_connector="J5." + EXPECT_HDMI[l],
                       ok=(pc == ["J4." + EXPECT_CORE[l]] and pk == ["J5." + EXPECT_HDMI[l]]))
    report["ok"] &= rec["pins"]["ok"]
    report["lines"][l] = rec
# P/N order (top to bottom) at the Core pads and at the connector pads
def y_of(ref_pref, net):
    for ref, p in pads_of(net):
        if ref.startswith(ref_pref):
            return mm(p.GetPosition().y)
    return None


pol = {}
for pair in ("D2", "D1", "D0", "CK"):
    pc, nc = y_of("J4.", "HDMI_%sP" % pair), y_of("J4.", "HDMI_%sN" % pair)
    pk, nk = y_of("J5.", "HDMI_%sP_C" % pair), y_of("J5.", "HDMI_%sN_C" % pair)
    pol[pair] = dict(core_P_above_N=pc < nc, connector_P_above_N=pk < nk, same_order=(pc < nc) == (pk < nk))
report["polarity"] = pol
out = os.environ.get("CHECK_JSON") or (None if os.environ.get("CHECK_PCB") else os.path.join(HERE, "continuity_report.json"))
if out:
    json.dump(report, open(out, "w"), indent=1)
print("TMDS copper continuity:", "ALL OK" if report["ok"] else "FAILED")
for l, r in report["lines"].items():
    print(l, {k: (v["ok"], v.get("copper_len_mm")) for k, v in r.items()})
print("pins", {l: r["pins"]["ok"] for l, r in report["lines"].items()})
print("polarity (information only)", {k: v["same_order"] for k, v in pol.items()})
sys.exit(0 if report["ok"] else 1)
