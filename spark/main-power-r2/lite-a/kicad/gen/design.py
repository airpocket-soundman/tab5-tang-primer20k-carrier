from design_variant import *

# BEGIN PoC parallel 680R qualification
_build_before_series_680 = build
def build():
    cs = _build_before_series_680()
    changed = []
    for c in cs:
        if not c.ref.startswith('R') or len(c.pins) != 2:
            continue
        nets = set(c.pins.values())
        iso = next((n for n in nets if n and n.startswith('ISO_')), None)
        if iso and nets == {iso, 'F_' + iso[4:]}:
            assert c.value in ('33R','330R','680R') and not c.dnp, (c.ref, c.value)
            c.value = '680R'
            c.lcsc = 'C23228'
            c.comment = 'PoC 1MHz, 680ohm series damping; >=250ns DATA setup/hold, weak drive/SLOW; qualified distributed-RLC sensitivity'
            changed.append(c.ref)
    assert len(changed) == 15, changed
    return cs
# END PoC parallel 680R qualification

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

# Akizuki TS-06104 hand-solder buttons, manufacturer drawing p8.
_build_before_akizuki_buttons = build
def build():
    cs = _build_before_akizuki_buttons()
    for c in cs:
        if c.ref in ('SW1','SW2'):
            c.fp='carrier:SW_TS_06104_HandSolder';c.value='TS-06104';c.lcsc=''
            c.pos=((59.9 if c.ref=='SW1' else 70.5),6.5);c.rot=0
            c.comment='Manual assembly; Akizuki115969; TS-06104 H4.3mm; dedicated manufacturer p8 lands; pads1=A/B and2=C/D'
    return cs

# LCSC LITE A REVISION
_build_before_lcsc=build
def build():
    cs=_build_before_lcsc()
    selected={'J1': ('DC-005-5A-2.0', 'C381116', 'carrier:BarrelJack_XKB_C381116', 'LCSC/JLC wave-solder candidate; stabilized12V center positive; XKB drawing A1; actual plug fit pending.'), 'J3': ('2.54-2*15P', 'C56496', None, 'Bottom2x15 male; LCSC/JLC wave-solder candidate;6mm mating,3mm tails,2.54mm insulator. Preserve mirrored pinout; physical fit pending.'), 'JP1': ('B-2100S02P-A110', 'C124375', None, 'LCSC/JLC wave-solder candidate;C5305 shunt supplied separately, initially absent.'), 'SW3': ('DS-02BLP', 'C692500', 'carrier:SW_XKB_DS02BLP_C692500', 'LCSC/JLC wave-solder candidate; first physical pole only; localCAD1-4, supplier diagram1-3. Both OFF initially=FPGA runs.'), 'SW1': ('TS-1187A-B-A-B', 'C318884', 'carrier:SW_XKB_TS1187A_C318884', 'LCSC/JLC SMT;H1.5mm; custom footprint90deg relative to datasheet: A/B common contacts on CAD left numbered1, C/D on right numbered2. Manufacturer rotation preview required.'), 'SW2': ('TS-1187A-B-A-B', 'C318884', 'carrier:SW_XKB_TS1187A_C318884', 'LCSC/JLC SMT;H1.5mm; custom footprint90deg relative to datasheet: A/B common contacts on CAD left numbered1, C/D on right numbered2. Manufacturer rotation preview required.')}
    for c in cs:
        if c.ref in selected:
            c.value,c.lcsc,fp,c.comment=selected[c.ref]
            if fp:c.fp=fp
        if c.ref=="SW3":
            c.sym="Switch:SW_DIP_x02"
            c.pins={"1":"BUCK_EN","4":"GND","2":None,"3":None};c.pads=None
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
