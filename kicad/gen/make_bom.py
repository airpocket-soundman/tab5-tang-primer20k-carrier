"""Generate kicad/bom.csv from the design data; look up JLCPCB basic-part IDs via jlcsearch (best effort).

python -X utf8 kicad/gen/make_bom.py
"""
import csv
import json
import os
import sys
import urllib.request
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
import design

OUT = os.path.join(os.path.dirname(__file__), "..", "bom.csv")


def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def num(v):
    v = v.strip()
    mult = {"R": 1, "k": 1e3, "u": 1e-6, "n": 1e-9, "p": 1e-12}
    for suf in ("k", "R"):
        if v.endswith(suf):
            return float(v[:-1]) * mult[suf]
    if "k" in v:
        a, b = v.split("k")
        return float(a + "." + b) * 1e3
    return None


def lookup_resistor(val, pkg):
    ohms = {"0R": 0, "33R": 33, "10k": 1e4, "1k": 1e3, "3.3k": 3300, "15k": 1.5e4, "100k": 1e5, "2.2k": 2200,
            "20k": 2e4, "499R": 499}.get(val)
    if ohms is None:
        return None
    d = get("https://jlcsearch.tscircuit.com/resistors/list.json?package=%s&resistance=%g&is_basic=true" % (pkg, ohms))
    for k, v in d.items():
        if isinstance(v, list) and v:
            return "C%s" % v[0]["lcsc"], "basic"
    return None


def lookup_cap(farad, pkg):
    d = get("https://jlcsearch.tscircuit.com/capacitors/list.json?package=%s&capacitance=%g&is_basic=true" % (pkg, farad))
    for k, v in d.items():
        if isinstance(v, list) and v:
            return "C%s" % v[0]["lcsc"], "basic"
    return None


KNOWN = {  # best-effort, verify before ordering
    "SS54": ("C22452", "basic"),
    "2N7002": ("C8545", "basic"),
    "AMS1117-3.3": ("C6186", "basic"),
    "LED": ("C2286", "basic (0603 red)"),
    "TPS5430DDAR": ("", "basic per jlcsearch (ID to confirm)"),
}


def main():
    comps = design.build()
    groups = OrderedDict()
    for c in comps:
        key = (c.value, c.fp, c.dnp)
        groups.setdefault(key, []).append(c)
    rows = []
    for (value, fp, dnp), cs in groups.items():
        lcsc, cls = "", "check"
        name = fp.split(":")[1]
        if name.startswith(("R_0603", "R_0402")):
            r = lookup_resistor(value, "0402" if name.startswith("R_0402") else "0603")
            if r:
                lcsc, cls = r
        elif name.startswith("C_0603") or name.startswith("C_1206"):
            pkg = "0603" if "0603" in name else "1206"
            val = value.split("/")[0]
            mult = {"u": 1e-6, "n": 1e-9, "p": 1e-12}
            try:
                f = float(val[:-1]) * mult[val[-1]]
                r = lookup_cap(f, pkg)
                if r:
                    lcsc, cls = r
                else:
                    cls = "extended/check (voltage rating)"
            except Exception:  # noqa: BLE001
                pass
        elif value in KNOWN:
            lcsc, cls = KNOWN[value]
        elif cs[0].lcsc:
            lcsc, cls = cs[0].lcsc, "extended" if cs[0].lcsc not in ("C363878",) else "extended"
        elif name.startswith(("PinHeader", "BarrelJack", "HDMI", "USB_C", "SW_", "MountingHole")):
            cls = "THT/hand-solder or extended (select part)"
        rows.append([",".join(sorted(x.ref for x in cs)), value, fp, len(cs), "DNP" if dnp else "", lcsc, cls,
                     cs[0].comment])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Refs", "Value", "Footprint", "Qty", "DNP", "LCSC", "JLC class", "Note"])
        w.writerows(rows)
    print("wrote", OUT, len(rows), "lines")
    # Core pin table (SODIMM pad -> carrier signal), for the FPGA constraint file
    notes = {"HDMI_D2P": "TX5_N pad: P/N swapped on the pins -> invert the D2 data bits in the FPGA (TMDS data lanes only)",
             "HDMI_D2N": "TX5_P pad (see HDMI_D2P)", "HDMI_D1P": "TX3_P", "HDMI_D1N": "TX3_N", "HDMI_D0P": "TX2_P",
             "HDMI_D0N": "TX2_N", "HDMI_CKP": "TX1_P", "HDMI_CKN": "TX1_N"}
    pin_out = os.path.join(os.path.dirname(OUT), "core_pin_assignment.csv")
    with open(pin_out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sodimm_pin", "signal", "note"])
        for sig, pin in sorted(design.CORE_PINS.items(), key=lambda kv: kv[1]):
            w.writerow([pin, sig, notes.get(sig, "")])
    print("wrote", pin_out, len(design.CORE_PINS), "pins")


if __name__ == "__main__":
    main()
