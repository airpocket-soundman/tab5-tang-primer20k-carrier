"""Spark full-size125x78 candidate. KiCad engineering reference, not an eligible EasyEDA entry yet."""
from design_base import *
import design_base as base
import json
from pathlib import Path
BOARD=(2.,1.,127.,79.)
VARIANT='spark-full-pcba'
POSE=json.loads((Path(__file__).parent/'full-placement.json').read_text())
def build():
    cs=base.build()
    for c in cs:
        if c.ref in POSE:c.pos,c.rot=tuple(POSE[c.ref][0]),POSE[c.ref][1]
        nets=set(c.pins.values())
        iso=next((n for n in nets if n and n.startswith('ISO_')),None)
        if iso and nets=={iso,'F_'+iso[4:]}:
            c.value='680R';c.lcsc='C23228'
            c.comment='Initial PoC1MHz; DATA setup/hold>=250ns; DIR deadtime>=500ns; weak drive/SLOW. New full-size routing must be re-evaluated.'
        if c.ref=='J4':
            c.fp='carrier:DDR3_XDAP_4042044_20401';c.value='SOCKET XDAP-4042044-20401';c.lcsc='C22471982'
            c.comment='PCBA mandatory; socket only, Core module supplied by user; confirm stock/fixture'
    return cs

# BEGIN qualified low-profile HDMI and isolated active-low HPD
_build_before_hdmi_revision = build
def build():
    cs=_build_before_hdmi_revision();lookup={c.ref:c for c in cs}
    for i in range(12,20):
        c=lookup['C'+str(i)];c.fp='Capacitor_SMD:C_0402_1005Metric';c.lcsc='C1525'
        c.comment='100nF AC coupling; low-profile 0402 under Core'
    u=lookup['U6'];u.sym='carrier:RCLAMP0524P';u.fp='carrier:DFN2510-10L_RCLAMP0524P';u.value='RCLAMP0524P';u.lcsc='C293965'
    u.pins={'1':'HDMI_SDA','10':'HDMI_SDA','2':'HDMI_5V','9':'HDMI_5V','4':'HDMI_SCL','7':'HDMI_SCL','5':'HDMI_HPD','6':'HDMI_HPD','3':'GND','8':'GND'}
    u.comment='Independent ground-referenced ESD channels, no shared VCC steering; NC counterpart lands externally copper strapped'
    for ref,val,lcsc,pins in [('R40','47k','C25819',{'1':'HDMI_HPD','2':'HPD_B'}),('R41','100k','C25803',{'1':'HPD_B','2':'GND'})]:
        c=lookup[ref];c.value=val;c.lcsc=lcsc;c.pins=pins
    new=[
      Comp('Q5','Transistor_BJT:MMBT3904','Package_TO_SOT_SMD:SOT-23','MMBT3904',{'1':'HPD_B','2':'GND','3':'HPD_BUF'},'hdmi',pos=(61,55),lcsc='C20526'),
      Comp('R51','Device:R',R0603,'47k',{'1':'+3V3','2':'HPD_BUF'},'hdmi',pos=(60,58),lcsc='C25819'),
      Comp('R52','Device:R',R0603,'10k',{'1':'HPD_BUF','2':'F_HPD'},'hdmi',pos=(68,55),lcsc='C25804'),
      Comp('C24','Device:C',C0603,'100n',{'1':'HPD_BUF','2':'GND'},'hdmi',pos=(65,55),lcsc='C14663')]
    for c in new:
        c.dnp=False;c.comment='Active-low HPD; input only, invert and debounce >=10ms; R52 limits off-bank charge injection, no hotplug guarantee'
    cs.extend(new);return cs
# END qualified low-profile HDMI and isolated active-low HPD

# HDMI connector is assembled by JLCPCB; footprint and copper are unchanged.
_build_before_hdmi_pcba = build
def build():
    cs = _build_before_hdmi_pcba()
    hdmi = next(c for c in cs if c.ref == 'J5')
    hdmi.lcsc = 'C916313'
    hdmi.comment = 'MOLEX 2086581001; PCBA required including four through-hole shell tabs; no customer HDMI soldering. Confirm full connector assembly in supplier preview.'
    return cs

# Spark-only manufacturer-assembled tactile buttons, source drawing C480272.
_build_before_spark_controls=build
def build():
    cs=_build_before_spark_controls()
    for c in cs:
        if c.ref in ('SW1','SW2'):
            c.fp='carrier:SW_XKB_TS1102S_C480272'
            c.value='TS-1102S-B-D-B';c.lcsc='C480272'
            c.pos=(14.,11.) if c.ref=='SW1' else (29.,11.)
            c.rot=0
            c.comment='PCBA SMT; XKB C480272 H5.5mm; manufacturer12x5.9mm lands; confirm contact grouping and mechanical fit in assembly preview'
        elif c.ref=='SW3':
            c.pos=(45.5,15.);c.sym='Switch:SW_DIP_x02'
            c.fp='carrier:SW_OTAX_KSD22_Akizuki108922';c.value='KSD22';c.lcsc=''
            c.pins={'1':'BUCK_EN','4':'GND','2':None,'3':None};c.pads=None
            c.comment='Akizuki108922 manual assembly; local logical poles1-4/2-3, second pole NC; closed first pole stops FPGA power, open runs. Not a load power switch.'
        elif c.ref=='J1':
            c.fp='carrier:BarrelJack_MJ179PH_Akizuki106568';c.value='MJ-179PH';c.lcsc=''
            c.comment='Akizuki106568 manual assembly; center positive stabilized12V only; manufacturer slot drawing adapted; pad2/3 grounded'
    return cs






# LCSC PRIORITY REVISION
_build_before_lcsc=build
def build():
    cs=_build_before_lcsc()
    selected={'J1': ('DC-005-5A-2.0', 'C381116', 'carrier:BarrelJack_XKB_C381116', 'LCSC/JLC wave-solder candidate; center-positive stabilized12V only; XKB drawing A1 2025-04-22. 5A connector rating is not board current rating. Verify actual power plug fit.'), 'SW3': ('DS-02BLP', 'C692500', 'carrier:SW_XKB_DS02BLP_C692500', 'LCSC/JLC wave-solder candidate; local KiCad DIP numbering1-4/2-3; supplier diagram aligned numbering1-3/2-4. First pole closes BUCK_EN to GND to stop FPGA; second unused. Both OFF initially.'), 'J3': ('2.54-2*15P', 'C56496', None, 'LCSC/JLC wave-solder candidate; bottom male2x15,6mm mating pins,3mm solder tails,2.54mm insulator; preserve user-confirmed mirrored pin assignment; fit and two-sided process pending.'), 'JP1': ('B-2100S02P-A110', 'C124375', None, 'LCSC/JLC wave-solder candidate; 1x2 male2.54mm,6mm mating pins,3mm solder tails; C5305 shunt supplied separately and initially absent.')}
    for c in cs:
        if c.ref in selected:
            c.value,c.lcsc,fp,c.comment=selected[c.ref]
            if fp:c.fp=fp
    return cs

# MAIN POWER R2 CIRCUIT CANDIDATE: not a fabrication release.
_build_before_main_power_r2=build
def build():
    cs=_build_before_main_power_r2()
    for c in cs:
        if c.ref in ('D1','D2','D3','C1'):
            c.pins={p:('VIN_OR' if net=='VIN' else net) for p,net in c.pins.items()}
        if c.ref=='SW3':
            c.sym='Switch:SW_SPDT';c.fp='' # Manufacturer footprint audit and PCB placement pending
            c.value='XKB5858-Z-TP-75';c.lcsc='C692487';c.block='mainpower';c.rot=0
            c.pins={'1':None,'2':'VIN_OR','3':'MAIN_ON'};c.pads=None
            c.comment='Latching main-power control candidate. Released 1-2=OFF, latched 2-3=ON. Second physical pole4/5/6 unused. 100mA contacts carry enable current only. PCB placement/land audit pending.'
    cs.extend([
      Comp('U11','Power_Management:TPS22810DRV','Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm','TPS22810DRVT',{'1':'VIN','2':None,'3':'MAIN_CT','4':'GND','5':'MAIN_EN','6':'VIN_OR','7':'GND'},'mainpower',lcsc='C2653758',comment='CANDIDATE ONLY. WSON3A, operating2.7-18V; no reverse blocking claim. QOD disabled. Existing TVS clamp is not adequate as guaranteed overvoltage protection. Surge/inrush/thermal validation pending.'),
      Comp('R53','Device:R',R0603,'10k',{'1':'MAIN_ON','2':'MAIN_EN'},'mainpower',lcsc='C25804',comment='Enable series resistor; power contact current is not load current.'),
      Comp('R54','Device:R',R0603,'100k',{'1':'MAIN_EN','2':'GND'},'mainpower',lcsc='C25803',comment='Default EN low when switch open; no floating EN.'),
      Comp('C25','Device:C',C0603,'1u/50V',{'1':'VIN_OR','2':'GND'},'mainpower',lcsc='C15849',comment='Local load-switch input bypass; placement pending.'),
      Comp('C26','Device:C',C0603,'10n',{'1':'MAIN_CT','2':'GND'},'mainpower',lcsc='C57112',comment='Provisional slew capacitor; typical12V10-90% rise2.085ms, not a worst-case guarantee. Load/inrush simulation pending.')
    ])
    return cs
