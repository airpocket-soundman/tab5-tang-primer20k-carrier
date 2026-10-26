"""Generate the KiCad schematic, project-local symbol library and fp-lib/sym-lib tables.

Run with a normal Python 3 (no KiCad API needed):  python -X utf8 kicad/gen/make_sch.py
"""
import math
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
import design
import sexp
from sexp import Str

KICAD = "C:/Program Files/KiCad/10.0/share/kicad/"
OUT = os.path.join(os.path.dirname(__file__), "..")
SYMVER = "20251024"

_lib_cache = {}


def S(x):
    return Str(x)


def uid():
    return S(str(uuid.uuid4()))


def load_lib(lib):
    if lib not in _lib_cache:
        path = KICAD + "symbols/" + lib + ".kicad_sym"
        if lib == "carrier":
            path = os.path.join(OUT, "lib", "carrier.kicad_sym")
        _lib_cache[lib] = sexp.parse(open(path, encoding="utf-8").read())
    return _lib_cache[lib]


def get_symbol(lib, name):
    for c in sexp.find(load_lib(lib), "symbol"):
        if c[1] == name:
            return c
    raise KeyError(lib + ":" + name)


def flatten(lib, name):
    """Return a symbol node for embedding in a schematic (extends resolved, renamed Lib:Name)."""
    s = get_symbol(lib, name)
    ext = sexp.first(s, "extends")
    if ext:
        parent = flatten_raw(lib, ext[1])
        # child properties override parent's
        props = {p[1]: p for p in sexp.find(s, "property")}
        out = [c for c in parent]
        out[1] = S(name)
        newprops = []
        for c in out:
            if isinstance(c, list) and c[0] == "property" and c[1] in props:
                newprops.append(props[c[1]])
            else:
                newprops.append(c)
        out = newprops
        # unit symbols: rename prefix parent -> child
        res = []
        for c in out:
            if isinstance(c, list) and c[0] == "symbol":
                c = [c[0], S(str(c[1]).replace(ext[1] + "_", name + "_", 1))] + c[2:]
            res.append(c)
        out = res
        s = out
    else:
        s = [c for c in s]
    s[1] = S(lib + ":" + name)
    return s


def flatten_raw(lib, name):
    s = get_symbol(lib, name)
    ext = sexp.first(s, "extends")
    if ext:
        return flatten_raw(lib, ext[1])
    return s


def sym_pins(sym):
    out = {}
    for u in sexp.find(sym, "symbol"):
        for p in sexp.find(u, "pin"):
            at = sexp.first(p, "at")
            out[str(sexp.first(p, "number")[1])] = (float(at[1]), float(at[2]), float(at[3]),
                                                    str(sexp.first(p, "name")[1]))
    return out


def sym_props(sym):
    return {p[1]: p for p in sexp.find(sym, "property")}


# ---------------------------------------------------------------- carrier library (CORE_SODIMM_204)
def make_core_symbol():
    """Own 204-pin symbol: two columns, pin names carry the carrier signal name."""
    pinname = {}
    for n in design.CORE_5V:
        pinname[n] = "+5V"
    for n in design.CORE_GND:
        pinname[n] = "GND"
    for net, n in design.CORE_PINS.items():
        pinname[n] = net
    pitch = 2.54
    rows = 102
    top = (rows - 1) * pitch / 2
    pins = []
    for n in range(1, 205):
        odd = n % 2 == 1
        row = (n - 1) // 2
        x = -12.7 if odd else 12.7
        y = round(top - row * pitch, 2)
        ang = 0 if odd else 180
        nm = pinname.get(n, "~")
        ptype = "passive" if n in pinname else "no_connect"
        pins.append(["pin", ptype, "line", ["at", str(x), str(y), str(ang)], ["length", "2.54"],
                     ["name", S(nm), ["effects", ["font", ["size", "1.016", "1.016"]]]],
                     ["number", S(str(n)), ["effects", ["font", ["size", "1.016", "1.016"]]]]])
    hw, hh = 10.16, top + 2.54
    sym = ["symbol", S("CORE_SODIMM_204"),
           ["pin_names", ["offset", "0.508"]],
           ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
           ["property", S("Reference"), S("J"), ["at", "0", str(round(hh + 2, 2)), "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["property", S("Value"), S("CORE_SODIMM_204"), ["at", "0", str(round(hh + 5, 2)), "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["property", S("Footprint"), S("carrier:DDR3-SMD_0705F0BE40F"), ["at", "0", "0", "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]],
           ["property", S("Datasheet"), S(""), ["at", "0", "0", "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]],
           ["property", S("Description"), S("Tang Primer 20K Core DDR3-SODIMM-edge socket (pin names = carrier nets)"),
            ["at", "0", "0", "0"], ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]],
           ["symbol", S("CORE_SODIMM_204_0_1"),
            ["rectangle", ["start", str(-hw), str(round(hh, 2))], ["end", str(hw), str(round(-hh, 2))],
             ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]],
           ["symbol", S("CORE_SODIMM_204_1_1")] + pins]
    return sym


def make_rclamp_symbol():
    """RCLAMP0524P (4-channel ESD array, DFN2510-10L; pins 6/7/9/10 are NC): IN1..IN4 left, OUT1..OUT4 right, GND pins 3 and 8."""
    left = [("IO1", "1"), ("IO2", "2"), ("GND", "3"), ("IO3", "4"), ("IO4", "5")]
    right = [("NC", "10"), ("NC", "9"), ("GND", "8"), ("NC", "7"), ("NC", "6")]
    pins = []
    for i, (nm, num) in enumerate(left):
        pins.append(["pin", "passive", "line", ["at", "-10.16", str(round(5.08 - i * 2.54, 2)), "0"], ["length", "2.54"],
                     ["name", S(nm), ["effects", ["font", ["size", "1.016", "1.016"]]]],
                     ["number", S(num), ["effects", ["font", ["size", "1.016", "1.016"]]]]])
    for i, (nm, num) in enumerate(right):
        pins.append(["pin", "passive", "line", ["at", "10.16", str(round(5.08 - i * 2.54, 2)), "180"], ["length", "2.54"],
                     ["name", S(nm), ["effects", ["font", ["size", "1.016", "1.016"]]]],
                     ["number", S(num), ["effects", ["font", ["size", "1.016", "1.016"]]]]])
    return ["symbol", S("RCLAMP0524P"),
            ["pin_names", ["offset", "0.508"]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            ["property", S("Reference"), S("U"), ["at", "0", "8.5", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
            ["property", S("Value"), S("RCLAMP0524P"), ["at", "0", "-8.5", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
            ["property", S("Footprint"), S("carrier:DFN2510-10L_RCLAMP0524P"), ["at", "0", "0", "0"],
             ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]],
            ["property", S("Datasheet"), S(""), ["at", "0", "0", "0"],
             ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]],
            ["property", S("Description"), S("DOWO RCLAMP0524P 4-channel low-capacitance ESD array; I/O 1,2,4,5, GND 3,8, NC 6,7,9,10"),
             ["at", "0", "0", "0"], ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]],
            ["symbol", S("RCLAMP0524P_0_1"),
             ["rectangle", ["start", "-7.62", "7.62"], ["end", "7.62", "-7.62"],
              ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]],
            ["symbol", S("RCLAMP0524P_1_1")] + pins]


def make_bus_switch_symbol():
    """TI PW-20 pin numbering, datasheet SCDS124C. All data paths passive."""
    import copy
    symbol = copy.deepcopy(get_symbol('Connector_Generic','Conn_02x10_Odd_Even'))
    symbol[1] = S('SN74CB3Q3245')
    names = {'1':'NC','10':'GND','19':'~{OE}','20':'VCC'}
    names.update({str(2+i):'A%d'%(i+1) for i in range(8)})
    names.update({str(18-i):'B%d'%(i+1) for i in range(8)})
    for p in sexp.find(symbol,'property'):
        if p[1]=='Reference':p[2]=S('U')
        if p[1]=='Value':p[2]=S('SN74CB3Q3245')
        if p[1]=='Footprint':p[2]=S('Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm')
        if p[1]=='Datasheet':p[2]=S('https://www.ti.com/lit/ds/symlink/sn74cb3q3245.pdf')
    for child in sexp.find(symbol,'symbol'):
        child[1]=S(str(child[1]).replace('Conn_02x10_Odd_Even','SN74CB3Q3245'))
        for pin in sexp.find(child,'pin'):
            num=str(sexp.first(pin,'number')[1])
            sexp.first(pin,'name')[1]=S(names[num])
            if num=='1':pin[1]='no_connect'
    return symbol


def write_lib():
    os.makedirs(os.path.join(OUT, "lib"), exist_ok=True)
    lib = ["kicad_symbol_lib", ["version", SYMVER], ["generator", S("carrier_gen")], ["generator_version", S("1.0")],
           make_core_symbol(), make_rclamp_symbol(), make_bus_switch_symbol()]
    open(os.path.join(OUT, "lib", "carrier.kicad_sym"), "w", encoding="utf-8").write(sexp.dump(lib) + "\n")
    _lib_cache.pop("carrier", None)


# ---------------------------------------------------------------- schematic
def effects(size=1.27, hide=False, justify=None):
    e = ["effects", ["font", ["size", str(size), str(size)]]]
    if justify:
        e.append(["justify"] + justify)
    if hide:
        e.append(["hide", "yes"])
    return e


def fnum(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s != "-0" else "0"


BLOCK_ORIGIN = {  # block -> (x, y, columns width limit)
    "power": (30, 40, 360), "pd": (30, 190, 360), "buck": (30, 340, 360), "ldo": (30, 500, 360),
    "mbus": (420, 40, 200), "series": (680, 40, 360), "hdmi": (420, 330, 420), "tmds": (1250, 60, 420), "tmdsc": (1250, 300, 420), "pmod": (420, 520, 360),
    "jtag": (420, 640, 200), "gpio": (700, 440, 200), "ui": (700, 640, 360), "mech": (30, 640, 300), "core": (1000, 60, 100),
}


def build_sch():
    write_lib()
    comps = design.build()
    root = uuid.uuid4()
    lib_syms = {}
    nodes = []
    pwr_count = [0]

    def need(symid):
        lib, name = symid.split(":")
        if symid not in lib_syms:
            lib_syms[symid] = flatten(lib, name)
        return lib_syms[symid]

    # layout cursors
    cur = {b: [v[0], v[1], 0.0] for b, v in BLOCK_ORIGIN.items()}
    wires = []
    labels = []
    ncs = []
    instances = []

    def place_power(net, x, y, ang_out):
        lib, name = design.POWER_SYMS[net]
        sym = need(lib)
        pwr_count[0] += 1
        props = sym_props(sym)
        inst = ["symbol", ["lib_id", S(lib)], ["at", fnum(x), fnum(y), "0"], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "no"], ["on_board", "no"], ["dnp", "no"], ["uuid", uid()]]
        inst.append(["property", S("Reference"), S("#PWR%03d" % pwr_count[0]), ["at", fnum(x), fnum(y + 2), "0"],
                     effects(hide=True)])
        inst.append(["property", S("Value"), S(name), ["at", fnum(x), fnum(y + (3.5 if net == "GND" else -3.5)), "0"],
                     effects()])
        inst.append(["property", S("Footprint"), S(""), ["at", fnum(x), fnum(y), "0"], effects(hide=True)])
        inst.append(["property", S("Datasheet"), S(""), ["at", fnum(x), fnum(y), "0"], effects(hide=True)])
        inst.append(["pin", S("1"), ["uuid", uid()]])
        inst.append(["instances", ["project", S(design.PROJECT), ["path", S("/" + str(root)),
                                                                    ["reference", S("#PWR%03d" % pwr_count[0])],
                                                                    ["unit", "1"]]]])
        instances.append(inst)

    for c in comps:
        sym = need(c.sym)
        pins = sym_pins(sym)
        xs = [p[0] for p in pins.values()]
        ys = [p[1] for p in pins.values()]
        w = (max(xs) - min(xs)) if xs else 10
        h = (max(ys) - min(ys)) if ys else 10
        b = cur[c.block]
        x0, y0, rowh = b
        lim = BLOCK_ORIGIN[c.block][2]
        cellw = w + 70
        if c.block != "core" and x0 - BLOCK_ORIGIN[c.block][0] + cellw > lim and x0 > BLOCK_ORIGIN[c.block][0]:
            x0 = BLOCK_ORIGIN[c.block][0]
            y0 += rowh + 12
            rowh = 0
        cx = x0 + 35 + (-min(xs) if xs else 0)
        cy = y0 + (max(ys) if ys else 0) + 12
        cx = round(cx / 2.54) * 2.54
        cy = round(cy / 2.54) * 2.54
        b[0], b[1], b[2] = x0 + cellw, y0, max(rowh, h + 24)
        # symbol instance
        props = sym_props(sym)
        inst = ["symbol", ["lib_id", S(c.sym)], ["at", fnum(cx), fnum(cy), "0"], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "yes" if c.dnp else "no"],
                ["uuid", uid()]]

        def prop(key, val, hide=None):
            lp = props.get(key)
            if lp is not None:
                at = sexp.first(lp, "at")
                ax, ay = float(at[1]), float(at[2])
                ef = sexp.first(lp, "effects")
                hid = any(isinstance(z, list) and z[0] == "hide" for z in ef) or any(z == "hide" for z in ef)
                hid = hid if hide is None else hide
                return ["property", S(key), S(val), ["at", fnum(cx + ax), fnum(cy - ay), "0"], effects(hide=hid)]
            return ["property", S(key), S(val), ["at", fnum(cx), fnum(cy), "0"], effects(hide=True)]

        inst.append(prop("Reference", c.ref, False))
        inst.append(prop("Value", c.value, False))
        inst.append(prop("Footprint", c.fp, True))
        inst.append(prop("Datasheet", "", True))
        if c.lcsc:
            inst.append(["property", S("LCSC"), S(c.lcsc), ["at", fnum(cx), fnum(cy), "0"], effects(hide=True)])
        if c.comment:
            inst.append(["property", S("Comment"), S(c.comment), ["at", fnum(cx), fnum(cy), "0"], effects(hide=True)])
        used = set()
        for pn, net in c.pins.items():
            if pn not in pins:
                raise KeyError("%s pin %s not in symbol %s" % (c.ref, pn, c.sym))
            used.add(pn)
        for pn in sorted(pins, key=lambda s: (len(s), s)):
            inst.append(["pin", S(pn), ["uuid", uid()]])
        inst.append(["instances", ["project", S(design.PROJECT), ["path", S("/" + str(root)),
                                                                    ["reference", S(c.ref)], ["unit", "1"]]]])
        instances.append(inst)
        # connections: stub + label / power symbol / no-connect
        for pn, net in c.pins.items():
            px, py, ang, nm = pins[pn]
            wx, wy = cx + px, cy - py
            if net is None:
                ncs.append(["no_connect", ["at", fnum(wx), fnum(wy)], ["uuid", uid()]])
                continue
            ox, oy = -math.cos(math.radians(ang)), -math.sin(math.radians(ang))
            ox, oy = round(ox), round(oy)
            wy_dir = -oy
            stub = 5.08
            ex, ey = wx + ox * stub, wy + wy_dir * stub
            wires.append(["wire", ["pts", ["xy", fnum(wx), fnum(wy)], ["xy", fnum(ex), fnum(ey)]],
                          ["stroke", ["width", "0"], ["type", "default"]], ["uuid", uid()]])
            if net in design.POWER_SYMS:
                place_power(net, ex, ey, 0)
            else:
                # label angle: direction text extends
                if ox > 0:
                    la, just = 0, ["left", "bottom"]
                elif ox < 0:
                    la, just = 180, ["right", "bottom"]
                elif wy_dir < 0:
                    la, just = 90, ["left", "bottom"]
                else:
                    la, just = 270, ["right", "bottom"]
                labels.append(["label", S(net), ["at", fnum(ex), fnum(ey), str(la)], effects(justify=just),
                               ["uuid", uid()]])

    # PWR_FLAGs so ERC knows these rails are driven
    fsym = need("power:PWR_FLAG")
    for i, net in enumerate(["GND", "+5V", "HDMI_5V", "VIN", "PD_VDD", "DC_RAW", "VBUS_PD", "TAB_3V3"]):
        fx, fy = 30.48 + i * 25.4, 12.7 + 5.08 * 0
        fy = 20.32 + 0.0
        pwr_count[0] += 1
        fr = "#FLG%02d" % (i + 1)
        inst = ["symbol", ["lib_id", S("power:PWR_FLAG")], ["at", fnum(fx), fnum(fy), "0"], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "no"], ["on_board", "no"], ["dnp", "no"], ["uuid", uid()],
                ["property", S("Reference"), S(fr), ["at", fnum(fx), fnum(fy - 3), "0"], effects(hide=True)],
                ["property", S("Value"), S("PWR_FLAG"), ["at", fnum(fx), fnum(fy + 3.5), "0"], effects()],
                ["property", S("Footprint"), S(""), ["at", fnum(fx), fnum(fy), "0"], effects(hide=True)],
                ["property", S("Datasheet"), S(""), ["at", fnum(fx), fnum(fy), "0"], effects(hide=True)],
                ["pin", S("1"), ["uuid", uid()]],
                ["instances", ["project", S(design.PROJECT), ["path", S("/" + str(root)), ["reference", S(fr)],
                                                                ["unit", "1"]]]]]
        instances.append(inst)
        if net in design.POWER_SYMS:
            place_power(net, fx, fy, 0)
        else:
            labels.append(["label", S(net), ["at", fnum(fx), fnum(fy), "0"], effects(justify=["left", "bottom"]),
                           ["uuid", uid()]])

    # block captions
    texts = []
    caps = {"power": "POWER INPUT: DC barrel + USB-C PD (OR) -> VIN", "pd": "USB-C PD sink (CH224K, 12V request)",
            "buck": "VIN -> +5V buck (TPS5430)", "ldo": "+5V -> +3V3 (peripherals)",
            "mbus": "M5-BUS header (Tab5-facing side)", "series": "Power-off bus isolation + 33R (M=Tab5, ISO=switch, F=FPGA)",
            "hdmi": "HDMI OUT connector + DDC/HPD level shift + ESD", "tmds": "HDMI TMDS 499R bias, ESD", "tmdsc": "HDMI TMDS AC coupling caps", "pmod": "PMOD x2",
            "jtag": "FPGA JTAG header", "gpio": "Spare FPGA I/O pads", "ui": "LEDs / buttons", "mech": "Mounting holes (Tab5 M3)",
            "core": "Tang Primer 20K Core SODIMM socket (pin names = nets)"}
    for b, (x, y, _) in BLOCK_ORIGIN.items():
        texts.append(["text", S(caps[b]), ["exclude_from_sim", "no"], ["at", fnum(x), fnum(y - 6), "0"],
                      ["effects", ["font", ["size", "3", "3"]], ["justify", "left", "bottom"]], ["uuid", uid()]])
    notes = ["Nets: GND +5V +3V3 are power symbols; all other nets connect by label.",
             "M5-Bus pins 28 (5V) and 30 (BAT) are intentionally NOT connected (Tab5 outputs).",
             "Do NOT tie Tab5 5V to the FPGA 5V rail. GND is common."]
    for i, t in enumerate(notes):
        texts.append(["text", S(t), ["exclude_from_sim", "no"], ["at", "30", str(fnum(12 + i * 5)), "0"],
                      ["effects", ["font", ["size", "2.5", "2.5"]], ["justify", "left", "bottom"]], ["uuid", uid()]])

    sch = ["kicad_sch", ["version", SYMVER], ["generator", S("eeschema")], ["generator_version", S("10.0")],
           ["uuid", S(str(root))], ["paper", S("A0")],
           ["title_block", ["title", S("Tab5 x Tang Primer 20K carrier")], ["date", S("2026-10-22")],
            ["rev", S("0.1")], ["comment", "1", S("Generated by kicad/gen (draft, unrouted-review required)")]],
           ["lib_symbols"] + list(lib_syms.values())]
    sch += wires + labels + ncs + texts + instances
    sch.append(["sheet_instances", ["path", S("/"), ["page", S("1")]]])
    sch.append(["embedded_fonts", "no"])
    path = os.path.join(OUT, design.PROJECT + ".kicad_sch")
    open(path, "w", encoding="utf-8").write(sexp.dump(sch) + "\n")
    print("wrote", path, len(instances), "symbols")


def write_project_files():
    tbl = ['(sym_lib_table\n\t(version 7)\n\t(lib (name "carrier")(type "KiCad")(uri "${KIPRJMOD}/lib/carrier.kicad_sym")(options "")(descr "carrier-specific symbols"))\n)\n']
    open(os.path.join(OUT, "sym-lib-table"), "w", encoding="utf-8").write(tbl[0])
    f = ['(fp_lib_table\n\t(version 7)\n\t(lib (name "carrier")(type "KiCad")(uri "${KIPRJMOD}/lib/carrier.pretty")(options "")(descr "carrier-specific footprints"))\n)\n']
    open(os.path.join(OUT, "fp-lib-table"), "w", encoding="utf-8").write(f[0])


if __name__ == "__main__":
    build_sch()
    write_project_files()
