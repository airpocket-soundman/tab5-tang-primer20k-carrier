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

_build_before_hdmi_pcba = build
def build():
    cs=_build_before_hdmi_pcba()
    c=next(c for c in cs if c.ref=='J5');c.lcsc='C916313'
    c.comment='MOLEX2086581001 PCBA mandatory including19 SMT contacts and all4 SH shell tabs; confirm supplier preview'
    return cs
