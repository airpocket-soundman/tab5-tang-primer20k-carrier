"""Design data model for the Tab5 x Tang Primer 20K carrier (v0.1).

Single source of truth: the schematic and the PCB are both generated from here.
Coordinates are millimetres in the Tab5 rear-view frame (origin = Tab5 top-left,
x to the right, y down), i.e. the view onto the carrier's outer (non Tab5) face.
"""
from collections import OrderedDict

PROJECT = "tab5-fpga-carrier"

# ---------------------------------------------------------------- Core pin map
# Verified visually against Sipeed SOM-3961 schematic (docs/reference/tang-primer-20k).
CORE_PINS = {
    # Odd SODIMM pins sit on the left pad row (Tab5 / PMOD side), even pins on the right row (HDMI / UI side).
    # 8-bit bus (bank0/1, 3.3V)
    "F_D0": 73, "F_D1": 75, "F_D2": 77, "F_D3": 79, "F_D4": 83, "F_D5": 85, "F_D6": 89, "F_D7": 91,
    "F_CLK": 80,   # K13 = GCLKT_1 (even pin: crosses under the socket)
    "F_RDY": 95, "F_DIR": 97,
    "F_AUX0": 101, "F_AUX1": 103, "F_AUX2": 107, "F_AUX3": 109,
    # 16-bit extension lines (via DNP 0R)
    "F_EXT35": 113, "F_EXT37": 115, "F_EXT38": 119,
    # HDMI TMDS (TX1..TX4 true-LVDS pairs): P / N
    "HDMI_D0P": 140, "HDMI_D0N": 142,
    "HDMI_D1P": 130, "HDMI_D1N": 132,
    "HDMI_D2P": 68, "HDMI_D2N": 70,
    "HDMI_CKP": 64, "HDMI_CKN": 62,
    # HDMI sideband (3.3V side)
    "F_HSCL": 152, "F_HSDA": 154, "F_HPD": 78,
    # LEDs / buttons
    "F_LED0": 50, "F_LED1": 52, "F_LED2": 56, "F_LED3": 58,
    "F_BTN0": 74, "F_BTN1": 76,
    # PMOD1 (left strip)
    "P1_0": 121, "P1_1": 123, "P1_2": 125, "P1_3": 129, "P1_4": 131, "P1_5": 84, "P1_6": 44, "P1_7": 46,
    # PMOD2 (left strip)
    "P2_0": 28, "P2_1": 30, "P2_2": 34, "P2_3": 36, "P2_4": 40, "P2_5": 42, "P2_6": 148, "P2_7": 146,
    # JTAG
    "JT_TMS": 143, "JT_TDO": 147, "JT_TCK": 149, "JT_TDI": 153,
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


def build():
    comps.clear()
    _counters.clear()

    # ------------------------------------------------------------ power input
    jdc = add("J", "Connector:Barrel_Jack", "Connector_BarrelJack:BarrelJack_Horizontal", "DC 12-24V",
              {"1": "DC_RAW", "2": "GND"}, "power", pos=(113.0, 48.0), rot=180)
    jdc.pads = {"1": "DC_RAW", "2": "GND", "3": "GND"}
    jdc.comment = "DC barrel jack, centre positive (THT, hand assembly)"
    two("F", "Device:Polyfuse", "Fuse:Fuse_1812_4532Metric", "PTC 3A hold", "DC_RAW", "DC_IN", "power",
        pos=(106.0, 44.5), rot=90)
    add("D", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", {"1": "VIN", "2": "DC_IN"}, "power",
        pos=(100.5, 49.5), rot=90, comment="reverse-polarity + OR (DC jack)")
    add("D", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS54", {"1": "VIN", "2": "VBUS_PD"}, "power",
        pos=(100.5, 54.5), rot=90, comment="OR (USB-C PD)")
    add("D", "Device:D_TVS", "Diode_SMD:D_SMB", "SMBJ24A (to be selected)", {"1": "VIN", "2": "GND"}, "power",
        pos=(111.0, 57.5), rot=0, comment="24V-class TVS; clamp vs MP4560/TPS5430 abs-max TBD")
    add("C", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", "100u/35V", {"1": "VIN", "2": "GND"}, "power",
        pos=(100.0, 64.0), rot=0)

    usb = add("J", "Connector:USB_C_Receptacle_PowerOnly_6P",
              "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x-0190_6P_TopMnt_Horizontal", "USB-C PD in",
              {"A5": "CC1", "A9": "VBUS_PD", "A12": "GND", "B5": "CC2", "B9": "VBUS_PD", "B12": "GND",
               "SH": "GND"}, "power", pos=(123.0, 32.5), rot=90)
    usb.comment = "power-only USB-C 6P receptacle"

    # ------------------------------------------------------------ PD sink
    add("U", "Interface_USB:CH224K", "Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm", "CH224K",
        {"1": "PD_VDD", "2": "PD_CFG2", "3": "PD_CFG3", "4": None, "5": None, "6": "CC2", "7": "CC1",
         "8": "PD_VBUS_S", "9": "PD_CFG1", "10": "PD_PG", "11": "GND"}, "pd", pos=(110.5, 31.0), rot=0,
        comment="PD sink, 20V request: CFG1=0 CFG2=1(internal PU) CFG3=0")
    two("R", "Device:R", R0603, "10k", "VBUS_PD", "PD_VDD", "pd", pos=(105.0, 29.0), rot=90)
    two("C", "Device:C", C0603, "1u/50V", "PD_VDD", "GND", "pd", pos=(105.0, 32.5), rot=90)
    two("R", "Device:R", R0603, "1k", "VBUS_PD", "PD_VBUS_S", "pd", pos=(105.0, 26.0), rot=90)
    two("R", "Device:R", R0603, "0R", "PD_CFG1", "GND", "pd", pos=(115.0, 28.0), rot=90,
        comment="CFG1 low (fit)")
    two("R", "Device:R", R0603, "0R", "PD_CFG3", "GND", "pd", pos=(115.0, 31.0), rot=90,
        comment="CFG3 low (fit) -> 20V; DNP -> 15V")
    two("R", "Device:R", R0603, "0R", "PD_CFG2", "GND", "pd", pos=(115.0, 34.0), rot=90, dnp=True,
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
    two("C", "Device:C", C1206, "47u/10V", "+5V", "GND", "buck", pos=(113.5, 71.0), rot=90)
    two("C", "Device:C", C1206, "47u/10V", "+5V", "GND", "buck", pos=(116.5, 76.0), rot=0)

    # ------------------------------------------------------------ 3V3 LDO
    add("U", "Regulator_Linear:AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "AMS1117-3.3",
        {"1": "GND", "2": "+3V3", "3": "+5V"}, "ldo", pos=(105.5, 41.0), rot=0)
    two("C", "Device:C", C1206, "10u/16V", "+5V", "GND", "ldo", pos=(101.0, 42.0), rot=90)
    two("C", "Device:C", C1206, "22u/10V", "+3V3", "GND", "ldo", pos=(110.0, 42.0), rot=90)

    # ------------------------------------------------------------ M5-Bus header (Tab5-facing side)
    pins = OrderedDict((str(k), v) for k, v in sorted(MBUS.items()))
    add("J", "Connector_Generic:Conn_02x15_Odd_Even", "Connector_PinHeader_2.54mm:PinHeader_2x15_P2.54mm_Vertical",
        "M5-BUS (to Tab5)", pins, "mbus", pos=(56.77, 21.21), rot=180, side="B",
        comment="male header on Tab5-facing side; pin-1 orientation to be confirmed on the real Tab5")
    # series resistors M_x -> F_x (33R); placed in one column left of the socket
    # series resistors: one per signal, horizontal, y aligned with the matching Core pad (min pitch 1.5mm)
    names = [(CORE_PINS["F_" + s], s, 0) for s in SERIES] + [(CORE_PINS["F_" + s], s, 1) for s in EXT]
    names.sort()
    CORE_Y = 39.8
    targets = [CORE_Y + core_pad_x(n) for (n, _, _) in names]
    ys = list(targets)
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + 1.5)
    shift = (sum(targets) - sum(ys)) / len(ys)          # re-centre
    ys = [y + shift for y in ys]
    for (n, s, ext), y in zip(names, ys):
        if ext:
            two("R", "Device:R", R0603, "0R", "M_" + s, "F_" + s, "series", pos=(62.0, round(y, 2)), rot=0,
                dnp=True, comment="16-bit extension (DNP): connects G%s to FPGA" % s[3:])
        else:
            two("R", "Device:R", R0603, "33R", "M_" + s, "F_" + s, "series", pos=(62.0, round(y, 2)), rot=0)

    # ------------------------------------------------------------ Core socket
    core = add("J", "carrier:CORE_SODIMM_204", "carrier:DDR3-SMD_0705F0BE40F", "Tang Primer 20K Core",
               {}, "core", pos=(71.5, 39.8), rot=270,
               comment="Sipeed footprint (LCSC C367004)", lcsc="C367004")
    for n in CORE_5V:
        core.pins[str(n)] = "+5V"
    for n in CORE_GND:
        core.pins[str(n)] = "GND"
    for net, n in CORE_PINS.items():
        core.pins[str(n)] = net
    core.pads = None

    # ------------------------------------------------------------ HDMI out
    hdmi = add("J", "Connector:HDMI_A", "Connector_Video:HDMI_A_Molex_208658-1001_Horizontal", "HDMI OUT",
               {"1": "HDMI_D2P", "2": "GND", "3": "HDMI_D2N", "4": "HDMI_D1P", "5": "GND", "6": "HDMI_D1N",
                "7": "HDMI_D0P", "8": "GND", "9": "HDMI_D0N", "10": "HDMI_CKP", "11": "GND",
                "12": "HDMI_CKN", "13": None, "14": None, "15": "HDMI_SCL", "16": "HDMI_SDA", "17": "GND",
                "18": "HDMI_5V", "19": "HDMI_HPD", "SH": "GND"}, "hdmi", pos=(119.0, 16.5), rot=0)
    hdmi.comment = "TMDS driven directly by FPGA true-LVDS outputs (3.3V bank)"
    two("F", "Device:Polyfuse", "Fuse:Fuse_1206_3216Metric", "PTC 500mA", "+5V", "HDMI_5V", "hdmi",
        pos=(105.0, 8.5), rot=90)
    q1 = add("Q", "Transistor_FET:2N7002", "Package_TO_SOT_SMD:SOT-23", "2N7002",
             {"1": "+3V3", "2": "F_HSCL", "3": "HDMI_SCL"}, "hdmi", pos=(105.0, 12.5), rot=0,
             comment="DDC level shifter (pin1=G pin2=S pin3=D)")
    q2 = add("Q", "Transistor_FET:2N7002", "Package_TO_SOT_SMD:SOT-23", "2N7002",
             {"1": "+3V3", "2": "F_HSDA", "3": "HDMI_SDA"}, "hdmi", pos=(105.0, 16.5), rot=0)
    two("R", "Device:R", R0603, "10k", "+3V3", "F_HSCL", "hdmi", pos=(100.5, 12.5), rot=90)
    two("R", "Device:R", R0603, "10k", "+3V3", "F_HSDA", "hdmi", pos=(100.5, 16.5), rot=90)
    two("R", "Device:R", R0603, "2.2k", "HDMI_5V", "HDMI_SCL", "hdmi", pos=(109.5, 12.5), rot=90)
    two("R", "Device:R", R0603, "2.2k", "HDMI_5V", "HDMI_SDA", "hdmi", pos=(109.5, 16.5), rot=90)
    two("R", "Device:R", R0603, "10k", "HDMI_HPD", "F_HPD", "hdmi", pos=(105.0, 21.0), rot=90)
    two("R", "Device:R", R0603, "20k", "F_HPD", "GND", "hdmi", pos=(105.0, 23.5), rot=90)

    # ------------------------------------------------------------ PMOD x2 (left strip)
    for k, (cy, tag) in enumerate(((46.0, "P1"), (10.5, "P2"))):
        io = ["%s_%d" % (tag, i) for i in range(8)]
        pins = {"1": io[0], "2": io[1], "3": io[2], "4": io[3], "5": "GND", "6": "+3V3",
                "7": io[4], "8": io[5], "9": io[6], "10": io[7], "11": "GND", "12": "+3V3"}
        # Digilent PMOD: pins 1-4 top row (odd on the 2x6 header: 1,2,3,4 -> row A)
        add("J", "Connector_Generic:Conn_02x06_Odd_Even",
            "Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical", "PMOD%d" % (k + 1),
            {"1": io[0], "2": io[4], "3": io[1], "4": io[5], "5": io[2], "6": io[6], "7": io[3], "8": io[7],
             "9": "GND", "10": "GND", "11": "+3V3", "12": "+3V3"}, "pmod",
            pos=(49.4, cy), rot=0, comment="2x6 PMOD-style, 3.3V")

    # ------------------------------------------------------------ JTAG header
    add("J", "Connector_Generic:Conn_01x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
        "FPGA JTAG", {"1": "JT_TMS", "2": "JT_TCK", "3": "JT_TDI", "4": "JT_TDO", "5": "+3V3", "6": "GND"},
        "jtag", pos=(49.4, 28.0), rot=0)

    # ------------------------------------------------------------ LEDs / buttons
    for i in range(4):
        two("R", "Device:R", R0603, "1k", "F_LED%d" % i, "LED%d_A" % i, "ui", pos=(101.0 + i * 3.2, 46.8), rot=0)
        add("D", "Device:LED", LED0603, "LED", {"1": "GND", "2": "LED%d_A" % i}, "ui",
            pos=(101.0 + i * 3.2, 49.0), rot=0)
    for i in range(2):
        add("SW", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_EVQP0", "SW", {"1": "F_BTN%d" % i, "2": "GND"},
            "ui", pos=(101.0 + i * 6.0, 55.0), rot=0)

    # ------------------------------------------------------------ mounting holes
    for (x, y) in ((51.0, 4.0), (51.0, 76.0), (124.0, 4.0), (124.0, 76.0)):
        h = add("H", "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3", "M3",
                {}, "mech", pos=(x, y), rot=0)
    return comps


# Nets whose pcb tracks should be wide
WIDE = {"VIN": 1.5, "DC_RAW": 1.5, "DC_IN": 1.5, "VBUS_PD": 1.0, "+5V": 1.5, "BUCK_PH": 1.5, "HDMI_5V": 0.6,
        "+3V3": 0.5}
BOARD = (46.0, 1.0, 127.0, 79.0)   # x0,y0,x1,y1 outline
