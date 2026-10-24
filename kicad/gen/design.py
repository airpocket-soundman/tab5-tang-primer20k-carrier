"""Design data model for the Tab5 x Tang Primer 20K carrier (v0.1).

Single source of truth: the schematic and the PCB are both generated from here.
Coordinates are millimetres in the Tab5 rear-view frame (origin = Tab5 top-left,
x to the right, y down), i.e. the view onto the carrier's outer (non Tab5) face.
"""
from collections import OrderedDict

import os

PROJECT = "tab5-fpga-carrier"
CORE_POS = (81.24, 40.6)      # point reflection of the old (38.3, 39.8) about the M-Bus header centre (56.27, 40.2)
SERIES_X = 71.04
HDMI_POSE = (119.0, 20.0, 0)
TMDS_X, TMDS_Y = 100.0, 13.0     # target of the AC-coupling / bias / ESD parts (between the Core pads and the HDMI connector)   # bottom edge, right of the M3 hole at (51.06, 75.95); see study_hdmi.py    # x, y, rotation of the HDMI connector (Type A); overridden by the placement study
HDMI_VARIANT = os.environ.get("CARRIER_HDMI", "A")   # "A" = Type-A receptacle, "micro" = Type-D (Molex 467651001, JLC C563878)

# ---------------------------------------------------------------- Core pin map
# Verified visually against Sipeed SOM-3961 schematic (docs/reference/tang-primer-20k).
CORE_PINS = {
    # Layout v3: Core sits LEFT of the M5-Bus header, card extends to the left.
    # Odd SODIMM pins are on the pad row facing the header; even pins face the left strip (HDMI / PMOD / UI).
    # 8-bit bus (bank0/1, 3.3V), all odd pins -> short link to the header
    "F_D0": 73, "F_D1": 75, "F_D2": 77, "F_D3": 79, "F_D4": 83, "F_D5": 85, "F_D6": 89, "F_D7": 91,
    "F_CLK": 80,   # K13 = IOT36A general I/O, NOT GCLKT_1 (K14). Timing must be checked for the receive implementation.
    "F_RDY": 95, "F_DIR": 97,
    "F_AUX0": 101, "F_AUX1": 103, "F_AUX2": 107, "F_AUX3": 109,
    # 16-bit extension lines (via DNP 0R)
    "F_EXT35": 113, "F_EXT37": 115, "F_EXT38": 119,
    # HDMI TMDS (TX1..TX4 true-LVDS pairs): P / N  (even pins). Channel <- pair chosen by study_tmds.py
    # (fewest vias on the HDMI-only routing study): D0<-TX4, D1<-TX3, D2<-TX2, CK<-TX1
    # Pair order top to bottom = connector order D2, D1, D0, CK, so that nothing crosses between the Core and the HDMI connector.
    # D2 uses TX5 with P/N swapped on the pins (TX5_N is the upper pad): invert the D2 data bits in the FPGA (allowed for
    # TMDS data lanes, never for the clock). TX4 is avoided: its N line is 1.9 mm shorter than P inside the Core board.
    "HDMI_D2P": 56, "HDMI_D2N": 58,     # TX5_N / TX5_P  (polarity swapped, invert D2 in logic)
    "HDMI_D1P": 68, "HDMI_D1N": 70,     # TX3
    "HDMI_D0P": 130, "HDMI_D0N": 132,   # TX2
    "HDMI_CKP": 140, "HDMI_CKN": 142,   # TX1
    # HDMI sideband (3.3V side)
    "F_HSCL": 152, "F_HSDA": 154, "F_HPD": 92,
    # LEDs / buttons (even)
    "F_LED0": 74, "F_LED1": 76, "F_LED2": 78, "F_LED3": 84,
    "F_BTN0": 86,
    # PMOD1 (left strip): six even pins + two odd
    "P1_0": 44, "P1_1": 46, "P1_2": 50, "P1_3": 52, "P1_4": 56, "P1_5": 58, "P1_6": 121, "P1_7": 123,
    # PMOD2 (left strip): all even
    "P2_0": 28, "P2_1": 30, "P2_2": 34, "P2_3": 36, "P2_4": 40, "P2_5": 42, "P2_6": 148, "P2_7": 146,
    # spare I/O breakout (bank7, 3.3V)
    "GPIO0": 125, "GPIO1": 129, "GPIO2": 131, "GPIO3": 176, "GPIO4": 180, "GPIO5": 182, "GPIO6": 186,
}
CORE_5V = [4, 5, 6, 7]
# GND pins detected on the Core schematic (see docs/reference/.../core_sodimm_pinmap.csv)
CORE_GND = [2, 3, 8, 9, 13, 14, 19, 20, 25, 26, 31, 32, 37, 38, 43, 48, 49, 54, 55, 60, 61, 66, 71, 72,
            127, 128, 133, 134, 138, 139, 144, 145, 150, 151, 155, 156, 161, 162, 168, 172, 173, 178,
            179, 184, 185, 189, 190, 195, 196]

# M5-Bus pin -> (Tab5 GPIO label, net on Tab5 side)
MBUS = OrderedDict([
    (1, "GND"), (3, "GND"), (5, "GND"),
    (7, "M_D0"), (9, "M_D1"), (11, "M_D2"), (13, "M_EXT38"), (15, "M_AUX3"), (17, "TAB_SDA"),
    (19, "M_D3"), (21, "M_D5"), (23, "M_D7"),
    (25, "VIN"), (27, "VIN"), (29, "VIN"),
    (2, "M_CLK"), (4, "M_AUX0"), (6, "TAB_RST"), (8, "M_RDY"), (10, "M_AUX1"), (12, "TAB_3V3"),
    (14, "M_EXT37"), (16, "M_AUX2"), (18, "TAB_SCL"), (20, "M_D4"), (22, "M_D6"), (24, "M_EXT35"),
    (26, "M_DIR"), (28, None), (30, None),
])

SERIES = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "CLK", "RDY", "DIR", "AUX0", "AUX1", "AUX2", "AUX3"]
EXT = ["EXT35", "EXT37", "EXT38"]

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"

GROUNDS = {"GND"}
POWER_SYMS = {"GND": ("power:GND", "GND"), "+5V": ("power:+5V", "+5V"), "+3V3": ("power:+3V3", "+3V3")}


def core_pad_x(n):
    """Local x of SODIMM pad n in the Sipeed footprint (becomes the y offset after the 270 deg rotation)."""
    if n <= 71:
        return -31.65 + (n - 1) * 0.3
    return 31.65 - (204 - n) * 0.3


class Comp:
    def __init__(self, ref, sym, fp, value, pins, block, pos=None, rot=0, side="F", dnp=False,
                 comment="", lcsc=""):
        self.ref, self.sym, self.fp, self.value = ref, sym, fp, value
        self.pins = pins          # {pin number: net or None(no-connect)}
        self.block, self.pos, self.rot, self.side = block, pos, rot, side
        self.dnp, self.comment, self.lcsc = dnp, comment, lcsc
        self.pads = None          # optional {pad name: net} when pad names differ from pin numbers


comps = []
_counters = {}


def ref(prefix):
    _counters[prefix] = _counters.get(prefix, 0) + 1
    return "%s%d" % (prefix, _counters[prefix])


def add(prefix, sym, fp, value, pins, block, pos=None, rot=0, side="F", **kw):
    c = Comp(ref(prefix), sym, fp, value, pins, block, pos, rot, side, **kw)
    comps.append(c)
    return c


def two(prefix, sym, fp, value, a, b, block, pos=None, rot=0, **kw):
    return add(prefix, sym, fp, value, {"1": a, "2": b}, block, pos, rot, **kw)



# ----------------------------------------------------------------------------- pin swap (monotone fan-out)
def _apply_pin_swap():
    CORE_Y = CORE_POS[1]

    def ypos(n):                                   # board y of Core pad n (Core rotated 270 deg)
        return CORE_Y + core_pad_x(n)

    # 1) bus: header pin order (top to bottom) <-> odd Core pads (top to bottom)
    bus = ["F_D%d" % i for i in range(8)] + ["F_RDY", "F_DIR", "F_AUX0", "F_AUX1", "F_AUX2", "F_AUX3",
                                              "F_EXT35", "F_EXT37", "F_EXT38"]
    inv = {v: k for k, v in MBUS.items() if v}

    def header_y(sig):
        pin = inv["M_" + sig[2:]]
        return 22.15 + 2.54 * ((pin + 1) // 2 - 1) + (0.01 if pin % 2 == 1 else 0.0)

    sigs = sorted(bus, key=header_y)
    pads = sorted((CORE_PINS[x] for x in bus), key=ypos)
    for sig, pad in zip(sigs, pads):
        CORE_PINS[sig] = pad

    # 2) PMOD / GPIO pad rows: pad order top to bottom  IO0,IO4,IO1,IO5,IO2,IO6,IO3,IO7
    pmod_order = [0, 4, 1, 5, 2, 6, 3, 7]

    def assign(prefix, pins):
        pins = sorted(pins, key=ypos)
        for k, pin in zip(pmod_order, pins):
            CORE_PINS["%s_%d" % (prefix, k)] = pin

    assign("P1", [123, 121, 92, 90, 86, 84, 78, 76])
    assign("P2", [64, 62, 52, 50, 46, 44, 42, 40])
    gp = [186, 182, 180, 176, 131, 129, 125]                       # GPIO0..6 top to bottom
    for i, pin in enumerate(sorted(gp, key=ypos)):
        CORE_PINS["GPIO%d" % i] = pin
    for sig, pin in (("F_HSCL", 36), ("F_HSDA", 34), ("F_HPD", 30), ("F_BTN0", 74),
                     ("F_LED0", 146), ("F_LED1", 148), ("F_LED2", 152), ("F_LED3", 154)):
        CORE_PINS[sig] = pin
    assert len(set(CORE_PINS.values())) == len(CORE_PINS), "duplicate Core pin"


_apply_pin_swap()


def hdmi_stub_dir(x, y):
    """Direction (dx, dy) in which the HDMI pads face (away from the connector body)."""
    rot = int(round(HDMI_POSE[2])) % 360
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[rot]


def build():
    comps.clear()
    _counters.clear()

    # ------------------------------------------------------------ power input
    jdc = add("J", "Connector:Barrel_Jack", "Connector_BarrelJack:BarrelJack_Horizontal", "DC 12-24V",
              {"1": "DC_RAW", "2": "GND"}, "power", pos=(113.0, 50.0), rot=180)
    jdc.pads = {"1": "DC_RAW", "2": "GND", "3": "GND"}
    jdc.comment = "DC barrel jack, centre positive (THT, hand assembly)"
    two("F", "Device:Polyfuse", "Fuse:Fuse_1812_4532Metric", "PTC 3A hold", "DC_RAW", "DC_IN", "power",
        pos=(106.0, 46.0), rot=90)
    add("D", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", {"1": "VIN", "2": "DC_IN"}, "power",
        pos=(100.5, 51.0), rot=90, comment="reverse-polarity + OR (DC jack)")
    add("D", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", {"1": "VIN", "2": "VBUS_PD"}, "power",
        pos=(100.5, 56.0), rot=90, comment="OR (USB-C PD)")
    add("D", "Device:D_TVS", "Diode_SMD:D_SMB", "SMBJ24A (to be selected)", {"1": "VIN", "2": "GND"}, "power",
        pos=(111.0, 57.5), rot=0, comment="24V-class TVS; clamp vs MP4560/TPS5430 abs-max TBD")
    add("C", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", "100u/35V", {"1": "VIN", "2": "GND"}, "power",
        pos=(100.0, 64.0), rot=0)

    usb = add("J", "Connector:USB_C_Receptacle_PowerOnly_6P",
              "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x-0190_6P_TopMnt_Horizontal", "USB-C PD in",
              {"A5": "CC1", "A9": "VBUS_PD", "A12": "GND", "B5": "CC2", "B9": "VBUS_PD", "B12": "GND",
               "SH": "GND"}, "power", pos=(123.0, 26.0), rot=90)
    usb.comment = "power-only USB-C 6P receptacle"

    # ------------------------------------------------------------ PD sink
    add("U", "Interface_USB:CH224K", "Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm", "CH224K",
        {"1": "PD_VDD", "2": "PD_CFG2", "3": "PD_CFG3", "4": None, "5": None, "6": "CC2", "7": "CC1",
         "8": "PD_VBUS_S", "9": "PD_CFG1", "10": "PD_PG", "11": "GND"}, "pd", pos=(110.5, 21.5), rot=0,
        comment="PD sink, 20V request: CFG1=0 CFG2=1(internal PU) CFG3=0")
    two("R", "Device:R", R0603, "10k", "VBUS_PD", "PD_VDD", "pd", pos=(105.0, 19.5), rot=90)
    two("C", "Device:C", C0603, "1u/50V", "PD_VDD", "GND", "pd", pos=(105.0, 23.0), rot=90)
    two("R", "Device:R", R0603, "1k", "VBUS_PD", "PD_VBUS_S", "pd", pos=(105.0, 16.5), rot=90)
    two("R", "Device:R", R0603, "0R", "PD_CFG1", "GND", "pd", pos=(115.0, 18.0), rot=90,
        comment="CFG1 low (fit)")
    two("R", "Device:R", R0603, "0R", "PD_CFG3", "GND", "pd", pos=(115.0, 21.0), rot=90,
        comment="CFG3 low (fit) -> 20V; DNP -> 15V")
    two("R", "Device:R", R0603, "0R", "PD_CFG2", "GND", "pd", pos=(115.0, 24.0), rot=90, dnp=True,
        comment="CFG2 low (DNP): fit with CFG3 open -> 12V")

    # ------------------------------------------------------------ buck 5V
    add("U", "Regulator_Switching:TPS5430DDA", "Package_SO:TI_SO-PowerPAD-8_ThermalVias", "TPS5430DDAR",
        {"1": "BUCK_BOOT", "2": None, "3": None, "4": "BUCK_FB", "5": "BUCK_EN", "6": "GND", "7": "VIN",
         "8": "BUCK_PH", "9": "GND"}, "buck", pos=(106.0, 71.0), rot=0)
    two("C", "Device:C", C0603, "10n", "BUCK_BOOT", "BUCK_PH", "buck", pos=(106.0, 66.5), rot=0)
    add("L", "Device:L", "Inductor_SMD:L_Bourns_SRR1260", "15u/4A", {"1": "BUCK_PH", "2": "+5V"}, "buck",
        pos=(120.5, 69.5), rot=0)
    add("D", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", {"1": "BUCK_PH", "2": "GND"}, "buck",
        pos=(111.5, 75.5), rot=0, comment="catch diode")
    two("R", "Device:R", R0603, "10k", "+5V", "BUCK_FB", "buck", pos=(101.0, 73.0), rot=90)
    two("R", "Device:R", R0603, "3.3k", "BUCK_FB", "GND", "buck", pos=(101.0, 76.0), rot=90,
        comment="Vout = 1.221*(1+10k/3.3k) = 4.92V")
    two("R", "Device:R", R0603, "100k", "VIN", "BUCK_EN", "buck", pos=(101.0, 69.5), rot=90)
    two("R", "Device:R", R0603, "15k", "BUCK_EN", "GND", "buck", pos=(101.0, 66.5), rot=90,
        comment="UVLO ~9.6V (holds off until PD reaches 20V)")
    two("C", "Device:C", C1206, "10u/50V", "VIN", "GND", "buck", pos=(106.0, 62.5), rot=0)
    two("C", "Device:C", C1206, "10u/50V", "VIN", "GND", "buck", pos=(110.5, 62.5), rot=0)
    two("C", "Device:C", C0603, "100n/50V", "VIN", "GND", "buck", pos=(113.5, 66.5), rot=90)
    add("C", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", "220u/10V polymer", {"1": "+5V", "2": "GND"}, "buck",
        pos=(112.0, 60.5), rot=0, comment="TI reference design uses 220uF POSCAP on the output (loop compensation needs ESR)")
    two("C", "Device:C", C1206, "47u/10V", "+5V", "GND", "buck", pos=(113.5, 71.0), rot=90)
    two("C", "Device:C", C1206, "47u/10V", "+5V", "GND", "buck", pos=(116.5, 76.0), rot=0)

    # ------------------------------------------------------------ 3V3 LDO
    add("U", "Regulator_Linear:AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "AMS1117-3.3",
        {"1": "GND", "2": "+3V3", "3": "+5V"}, "ldo", pos=(68.0, 9.0), rot=0)
    two("C", "Device:C", C1206, "10u/16V", "+5V", "GND", "ldo", pos=(62.0, 9.0), rot=90)
    two("C", "Device:C", C1206, "22u/10V", "+3V3", "GND", "ldo", pos=(74.0, 9.0), rot=90)

    # ------------------------------------------------------------ M5-Bus header (Tab5-facing side)
    pins = OrderedDict((str(k), v) for k, v in sorted(MBUS.items()))
    add("J", "Connector_Generic:Conn_02x15_Odd_Even", "Connector_PinHeader_2.54mm:PinHeader_2x15_P2.54mm_Vertical",
        "M5-BUS (to Tab5)", pins, "mbus", pos=(56.27, 22.15), rot=180, side="B",
        comment="male header on Tab5-facing side; pin-1 orientation to be confirmed on the real Tab5")
    # series resistors M_x -> F_x (33R); placed in one column left of the socket
    # series resistors: one per signal, horizontal, y aligned with the matching Core pad (min pitch 1.5mm)
    names = [(CORE_PINS["F_" + s], s, 0) for s in SERIES] + [(CORE_PINS["F_" + s], s, 1) for s in EXT]
    CORE_Y = CORE_POS[1]
    names.sort(key=lambda t: CORE_Y + core_pad_x(t[0]))      # Core is rotated 270 deg: y = CORE_Y + local_x
    targets = [CORE_Y + core_pad_x(n) for (n, _, _) in names]
    ys = list(targets)
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + 1.5)
    shift = (sum(targets) - sum(ys)) / len(ys)          # re-centre
    ys = [y + shift for y in ys]
    for (n, s, ext), y in zip(names, ys):
        if ext:
            two("R", "Device:R", R0603, "0R", "M_" + s, "F_" + s, "series", pos=(SERIES_X, round(y, 2)), rot=0,
                dnp=True, comment="16-bit extension (DNP): connects G%s to FPGA" % s[3:])
        else:
            two("R", "Device:R", R0603, "33R", "M_" + s, "F_" + s, "series", pos=(SERIES_X, round(y, 2)), rot=0)

    # ------------------------------------------------------------ Core socket
    core = add("J", "carrier:CORE_SODIMM_204", "carrier:DDR3-SMD_0705F0BE40F", "Tang Primer 20K Core",
               {}, "core", pos=CORE_POS, rot=270,
               comment="Sipeed footprint (LCSC C367004)", lcsc="C367004")
    for n in CORE_5V:
        core.pins[str(n)] = "+5V"
    for n in CORE_GND:
        core.pins[str(n)] = "GND"
    for net, n in CORE_PINS.items():
        core.pins[str(n)] = net
    core.pads = None

    # ------------------------------------------------------------ HDMI out
    lines = ["D2P", "D2N", "D1P", "D1N", "D0P", "D0N", "CKP", "CKN"]   # top to bottom = Core pad order = connector pad order (no crossing)
    C = {l: "HDMI_%s_C" % l for l in lines}     # after the AC coupling capacitor: ESD tap, 499R bias, HDMI connector pad (ONE net)
    hdmi = add("J", "Connector:HDMI_A", "Connector_Video:HDMI_A_Molex_208658-1001_Horizontal", "HDMI OUT",
               {"1": C["D2P"], "2": "GND", "3": C["D2N"], "4": C["D1P"], "5": "GND", "6": C["D1N"],
                "7": C["D0P"], "8": "GND", "9": C["D0N"], "10": C["CKP"], "11": "GND",
                "12": C["CKN"], "13": None, "14": None, "15": "HDMI_SCL", "16": "HDMI_SDA", "17": "GND",
                "18": "HDMI_5V", "19": "HDMI_HPD", "SH": "GND"}, "hdmi", pos=HDMI_POSE[:2], rot=HDMI_POSE[2])
    # AC coupling (100 nF) + 499R bias to GND on the connector side, as on the official Tang Primer 20K Dock
    for k, l in enumerate(lines):
        two("C", "Device:C", C0603, "100n", "HDMI_" + l, C[l], "tmdsc", pos=(TMDS_X, TMDS_Y + k * 1.5), rot=0)
        # 499R bias resistors: above the bundle for D2/D1, below it for D0/CK, so the branch off the line stays short
        rpos = (TMDS_X + 1.2 + k * 1.7, 10.2) if k < 4 else (TMDS_X - 1.2 + (k - 4) * 1.7, 26.4)
        # D1: 0402 fits the 1.17 mm space between adjacent pairs after the ESD.
        # Pad 1 taps the signal locally; pad 2 has a short return to a GND via outside the solder land.
        if l in ("D1P", "D1N"):
            two("R", "Device:R", "Resistor_SMD:R_0402_1005Metric", "499R", C[l], "GND", "tmdsc",
                pos=(110.3, 16.75 if l == "D1P" else 18.25), rot=0)
        else:
            two("R", "Device:R", R0603, "499R", C[l], "GND", "tmdsc", pos=rpos, rot=90)
    for tag, grp, y in (("a", lines[:4], 0.0), ("b", lines[4:], 14.0)):
        add("U", "carrier:RCLAMP0524P", "carrier:DFN2510-10L_RCLAMP0524P", "RCLAMP0524P",
            # I/O pins 1,2,4,5 tap the line; 6,7,9,10 are strapped to them with copper on the board (one net), so the line is
            # continuous copper and does not depend on any internal pin-to-pin connection of the part (audit item A)
            {"1": C[grp[0]], "2": C[grp[1]], "3": "GND", "4": C[grp[2]], "5": C[grp[3]],
             "6": C[grp[3]], "7": C[grp[2]], "8": "GND", "9": C[grp[1]], "10": C[grp[0]]},
            "tmdsc", pos=(TMDS_X + 8.0, 16.75 if tag == "a" else 19.75), rot=0, lcsc="C293965",   # pin pairs level with the HDMI pad pairs (straight lanes)
            comment="TMDS ESD array (DOWO DFN2510-10L): I/O 1,2,4,5, GND 3,8; the line is routed as continuous copper through strapped pads")
    add("U", "Power_Protection:SRV05-4", "Package_TO_SOT_SMD:SOT-23-6", "SRV05-4",
        {"1": None, "2": "GND", "3": "HDMI_HPD", "4": "HDMI_SCL", "5": "HDMI_5V", "6": "HDMI_SDA"}, "tmdsc",
        pos=(107.0, 24.8), rot=0, lcsc="C13612", comment="DDC/HPD ESD as on the official Dock")
    hdmi.comment = "TMDS from FPGA true-LVDS outputs (3.3V bank), AC coupled + 499R bias + ESD (official-Dock style)"
    two("F", "Device:Polyfuse", "Fuse:Fuse_1206_3216Metric", "PTC 500mA", "+5V", "HDMI_5V", "tmdsc",
        pos=(110.4, 29.3), rot=90)
    q1 = add("Q", "Transistor_FET:2N7002", "Package_TO_SOT_SMD:SOT-23", "2N7002",
             {"1": "+3V3", "2": "F_HSCL", "3": "HDMI_SCL"}, "hdmi", pos=(64.0, 25.0), rot=0,
             comment="DDC level shifter (pin1=G pin2=S pin3=D)")
    q2 = add("Q", "Transistor_FET:2N7002", "Package_TO_SOT_SMD:SOT-23", "2N7002",
             {"1": "+3V3", "2": "F_HSDA", "3": "HDMI_SDA"}, "hdmi", pos=(68.5, 25.0), rot=0)
    two("R", "Device:R", R0603, "10k", "+3V3", "F_HSCL", "hdmi", pos=(63.0, 28.5), rot=90)
    two("R", "Device:R", R0603, "10k", "+3V3", "F_HSDA", "hdmi", pos=(66.0, 28.5), rot=90)
    two("R", "Device:R", R0603, "2.2k", "HDMI_5V", "HDMI_SCL", "tmdsc", pos=(113.6, 30.8), rot=0)
    two("R", "Device:R", R0603, "2.2k", "HDMI_5V", "HDMI_SDA", "tmdsc", pos=(116.8, 30.8), rot=0)
    two("R", "Device:R", R0603, "10k", "HDMI_HPD", "F_HPD", "hdmi", pos=(70.0, 28.5), rot=90)
    two("R", "Device:R", R0603, "20k", "F_HPD", "GND", "hdmi", pos=(73.0, 28.5), rot=90)

    # ------------------------------------------------------------ PMOD x2 (left strip)
    for k, (cy, tag) in enumerate(((54.0, "P1"), (37.0, "P2"))):
        io = ["%s_%d" % (tag, i) for i in range(8)]
        pins = {"1": io[0], "2": io[1], "3": io[2], "4": io[3], "5": "GND", "6": "+3V3",
                "7": io[4], "8": io[5], "9": io[6], "10": io[7], "11": "GND", "12": "+3V3"}
        # Digilent PMOD: pins 1-4 top row (odd on the 2x6 header: 1,2,3,4 -> row A)
        add("J", "Connector_Generic:Conn_02x06_Odd_Even",
            "Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical", "PMOD%d" % (k + 1),
            {"1": io[0], "2": io[4], "3": io[1], "4": io[5], "5": io[2], "6": io[6], "7": io[3], "8": io[7],
             "9": "GND", "10": "GND", "11": "+3V3", "12": "+3V3"}, "pmod",
            pos=(112.5, cy), rot=0, dnp=True, comment="2x6 PMOD-style, 3.3V. Pads only: pin header is hand-fitted later (DNP)")

    # ------------------------------------------------------------ LEDs / buttons
    for i in range(4):
        two("R", "Device:R", R0603, "1k", "F_LED%d" % i, "LED%d_A" % i, "ui", pos=(62.0 + i * 3.2, 14.0), rot=0)
        add("D", "Device:LED", LED0603, "LED", {"1": "GND", "2": "LED%d_A" % i}, "ui",
            pos=(62.0 + i * 3.2, 17.0), rot=0)
    for i in range(1):                                  # one user button (BTN0); RESET sits next to it
        add("SW", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_EVQP0", "SW", {"1": "F_BTN%d" % i, "2": "GND"},
            "ui", pos=(30.0 + i * 10.0, 7.5), rot=0)   # two tact switches in a row left of HDMI: BTN0, RESET

    # ------------------------------------------------------------ reset / power switch / spare IO pads
    add("SW", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_EVQP0", "RESET (Tab5)", {"1": "TAB_RST", "2": "GND"},
        "ui", pos=(39.4, 7.5), rot=0, comment="pulls the M5-Bus RST/EN line (pin 6) low: resets the ESP32-P4")
    add("SW", "Switch:SW_DIP_x01", "Button_Switch_THT:SW_DIP_SPSTx01_Slide_9.78x4.72mm_W7.62mm_P2.54mm",
        "FPGA ON/OFF", {"1": "BUCK_EN", "2": "GND"}, "buck", pos=(110.0, 7.5), rot=0,
        comment="slide switch: ON = open (buck runs), OFF = short EN to GND (FPGA 5V off). Tab5 keeps its own power button. Sits in the switch row with the two tact switches, clear of the board edge")
    add("J", "Connector_Generic:Conn_01x09", "Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical",
        "GPIO pads", {"1": "+3V3", "2": "GND", "3": "GPIO0", "4": "GPIO1", "5": "GPIO2", "6": "GPIO3",
                      "7": "GPIO4", "8": "GPIO5", "9": "GPIO6"}, "gpio", pos=(121.5, 37.0), rot=0, dnp=True,
        comment="spare FPGA I/O (3.3V, bank 7): pads only, hand-fit a header or wires later")

    # ------------------------------------------------------------ mounting holes
    for (x, y) in ((4.06, 3.95), (4.06, 75.95), (51.06, 3.95), (51.06, 75.95), (124.06, 3.95), (124.06, 75.95)):   # measured on Tab5.stl
        h = add("H", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", "M3",
                {}, "mech", pos=(x, y), rot=0)
    # power input / PD / buck block: mirrored in x about x=65 (y kept: buck stays at the bottom) -> lives LEFT of the M-Bus header
    for c in comps:
        if c.block in ("power", "pd", "buck") and c.pos is not None:
            c.pos = (round(130.0 - c.pos[0], 2), round(c.pos[1], 2))
            c.rot = (c.rot + 180) % 360
    return comps


# Nets whose pcb tracks should be wide
WIDE = {"VIN": 1.5, "DC_RAW": 1.5, "DC_IN": 1.5, "VBUS_PD": 1.0, "+5V": 1.5, "BUCK_PH": 1.5, "HDMI_5V": 0.6,
        "+3V3": 0.5}
FANOUT_KEEPOUTS = [(69.0, 7.0, 77.0, 12.5),     # access to the Core +5V pads (wide +5V track)
                   (61.0, 18.0, 76.0, 61.0),     # bus channel Core pad row -> series resistors -> M-Bus header; also keeps
                                                 # the header side of the SODIMM socket free of tall parts (Core card clearance)
                   ]        # keep the +5V pads of the Core and the bottom lane free        # fan-out channel between the Core pad rows and the M5-Bus header
CARD_KEEPOUT = (76.5, 4.9, 108.7, 75.4)             # the Core card lies over this area: no parts under it
EDGE_MARGIN = 2.5        # parts other than the edge connectors (USB-C, HDMI, DC jack) keep this distance from the outline (enclosure)
HOLE_CLEARANCE = 5.0           # nothing within this distance of an M3 hole edge (screw head / driver access)
HOLE_R = 1.6
USB_SCREW_CLEARANCE = 10.0     # USB-C receptacle: keep this distance from every M3 screw (cable strain / driver access)
EDGE_CONNECTORS = ("J1", "J2", "J5")     # DC jack, USB-C, HDMI may sit on the edge
BOARD = (2.0, 1.0, 127.0, 79.0)   # x0,y0,x1,y1 outline (full Tab5 width: PMOD/JTAG moved over the battery bay)
