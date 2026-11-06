"""r5 manual RUN/PROGRAM selector; user-selected cost reduction2026-11-03."""
from design_r4 import *
import design_r4 as previous
import json
from pathlib import Path

PROJECT='tab5-fpga-carrier-r5l'
VARIANT='spark-full-manual-usb-jtag-r5l-switch'
CORE_PINS=dict(previous.CORE_PINS)
CORE_PINS.update({'JTAG_TMS':143,'JTAG_TDO':147,'JTAG_TCK':149,'JTAG_TDI':153})
POWER_FIXED=dict(previous.POWER_FIXED)
POWER_FIXED.update({'Y1':((19,31.5),90),'C86':((18,28),0),'C87':((16,35),0)})

def _r5_build():
    cs=[c for c in previous.build() if c.ref!='R3']
    for c in cs:
        if c.block=='buck':
            c.pins={p:('BUCK_5V' if n=='+5V' else n) for p,n in c.pins.items()}
        if c.ref=='J3':
            c.pins={p:('TAB_HVIN' if n=='VIN' else n) for p,n in c.pins.items()}
        if c.ref=='J4':
            # Official SOM-3961 schematic p1, goldfinger rows143..153:
            # these four r4-NC lands are the dedicated3.3V JTAG interface.
            c.pins.update({'143':'JTAG_TMS','147':'JTAG_TDO','149':'JTAG_TCK','153':'JTAG_TDI'})
        if c.ref=='J2':
            c.sym='Connector:USB_C_Receptacle_USB2.0_16P'
            c.fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12'
            c.value='TYPE-C-31-M-12 USB2 + PD';c.lcsc=''
            c.pins={p:'GND' for p in ('A1','A12','B1','B12','SH')}
            c.pins.update({p:'VBUS_PD' for p in ('A4','A9','B4','B9')})
            c.pins.update({'A5':'CC1','B5':'CC2','A6':'USB_DP','B6':'USB_DP','A7':'USB_DM','B7':'USB_DM','A8':None,'B8':None})
            c.comment='USB2 data and PD; PROGRAM strap requests5V; no automatic power selector'
    def add(ref,sym,fp,value,pins,block='r5power',pos=(35,35),comment=''):
        c=Comp(ref,sym,fp,value,pins,block,pos=pos,comment=comment);cs.append(c);return c
    def resistor(ref,value,a,b,pos):
        return add(ref,'Device:R',R0603,value,{'1':a,'2':b},pos=pos)
    # Three adjacent3-pin headers; ALL shunts move together, power disconnected.
    # 1-2=RUN,2-3=PROGRAM. No voltage-sensing or automatic switching IC.
    for ref,value,pins,x in [
      ('JP2','MODE POWER',{'1':'BUCK_5V','2':'+5V','3':'VBUS_PD'},39),
      ('JP3','MODE TAB5',{'1':'VIN','2':'TAB_HVIN','3':None},43),
      ('JP4','MODE PD',{'1':'GND','2':'PD_CFG1','3':'PD_VDD'},47)]:
        add(ref,'Connector_Generic:Conn_01x03','Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',value,pins,pos=(x,26),
          comment='MOVE ALL JP2/3/4 TOGETHER, ALL INPUTS UNPLUGGED. RUN1-2, PROGRAM2-3. Mixed settings can damageCore.')
    resistor('R73','100k','PD_VDD','PD_CFG1',(45,34))
    resistor('R74','100k','TAB_HVIN','GND',(48,34))
    # FT232H defaults suffice: MPSSE selected by host software; no EEPROM,
    # no PWREN-controlled Core rail, no automatic USB current selector.
    for data in json.loads((Path(__file__).parent/'usb_debugger_parts.json').read_text()):
        data=dict(data);pads=data.pop('pads',None)
        c=Comp(**data);c.pads=pads
        c.pins={p:('+5V' if n=='SYS_5V' else n) for p,n in c.pins.items()}
        if c.ref=='U17':
            for n in ('21','31','43','44','45'):c.pins[n]=None
            c.comment='Genuine FT232HL; no EEPROM; defaultVID/PID0403:6014; openFPGALoader cableft232; MPSSE selected overUSB'
        cs.append(c)
    # Two inexpensive discrete FETs hold USB interface in reset without VBUS,
    # including barrel-powered RUN. They do not select the system supply.
    resistor('R88','100k','VBUS_PD','VBUS_GATE',(34,24))
    resistor('R89','1M','VBUS_GATE','GND',(34,27))
    resistor('R90','10k','DBG_3V3','USB_ABSENT',(34,30))
    add('Q7','Transistor_FET:2N7002','Package_TO_SOT_SMD:SOT-23','2N7002',{'1':'VBUS_GATE','2':'GND','3':'USB_ABSENT'},'usbjtag',(34,33))
    add('Q8','Transistor_FET:2N7002','Package_TO_SOT_SMD:SOT-23','2N7002',{'1':'USB_ABSENT','2':'GND','3':'FT_RESET_N'},'usbjtag',(34,37))
    for c in cs:
        if c.ref in POWER_FIXED:c.pos,c.rot=POWER_FIXED[c.ref]
    return cs


# ---- r5l: JP2 and JP4 are replaced by ONE DP3T slide switch (SW4), so the dangerous
# combination "JP2=PROGRAM and JP4=RUN" can no longer be set. JP3 (VIN/TAB_HVIN) is kept.
# Part: G-Switch SS-23D03-G080 (LCSC C2848921). Assumed internal wiring (to be verified on the
# real part): pole A common=pad4, throws pad1/pad2/pad3; pole B common=pad5, throws pad8/pad7/pad6;
# pads move together as 1&8, 2&7, 3&6. Position 1=RUN, 2=middle=all open, 3=PROGRAM.
def build():
    cs=[c for c in _r5_build() if c.ref not in ('JP2','JP4')]
    # The r5 LCSC part numbers were attached to the committed r5 files by a later step that is not
    # part of this generator; carry them over from the (read-only) r5 BOM so r5l keeps them.
    import csv
    r5bom=Path(__file__).resolve().parents[5]/'usb-jtag-r5/full/design/kicad/bom-r5.csv'
    lcsc={r['Reference']:r['LCSC'] for r in csv.DictReader(r5bom.open(encoding='utf8')) if r['LCSC']}
    for c in cs:
        if not c.lcsc and c.ref in lcsc:c.lcsc=lcsc[c.ref]
    # LCSC numbers for the parts that r5 left blank. Every number below was opened on its JLCPCB
    # part page (MPN, package, Basic/Extended checked 2026-11-06); stock is NOT checked.
    by_value={('100k','R_0603_1608Metric'):'C25803',('12k 1%','R_0603_1608Metric'):'C22790',
      ('10k','R_0603_1608Metric'):'C25804',('33R','R_0603_1608Metric'):'C23140',('1M','R_0603_1608Metric'):'C22935',
      ('100n','C_0603_1608Metric'):'C14663',('4.7u','C_0603_1608Metric'):'C19666',
      ('PESD5V0U1BL','D_SOD-882'):'C3001955',('FT232HL-REEL','LQFP-48_7x7mm_P0.5mm'):'C51997',
      ('SN74LVC125APWR','TSSOP-14_4.4x5mm_P0.65mm'):'C7813',('2N7002','SOT-23'):'C8545'}
    by_ref={'J2':'C165948','JP3':'C49257','Y1':'C9002','C86':'C1663','C87':'C1663'}
    for c in cs:
        if not c.lcsc:
            c.lcsc=by_ref.get(c.ref) or by_value.get((c.value,c.fp.split(':')[-1]),'')
        if c.ref=='D10' or c.ref=='D11':
            c.comment='UMW PESD5V0U1BL (C3001955), SOD-882, extended. Nexperia original has no LCSC number; equivalence of capacitance/clamping NOT checked.'
        if c.ref=='Y1':
            c.value='12MHz CL20pF 20ppm X322512MSB4SI'
            c.comment='YXC X322512MSB4SI (C9002), 3.2x2.5mm 4-pin, Basic/SMT. Replaces FA-238V (extended, wave-solder class, stock 0). Load 20pF: C86/C87 are 33p. Land pattern fit to the LCSC footprint is checked in the order data.'
        if c.ref in ('C86','C87'):
            c.value='33p'
            c.comment='C0G 0603 33pF (C1663, Basic) for the 20pF-load crystal: CL = 33/2 + stray (about 3-5pF) = about 19.5-21.5pF'
        if c.ref=='J2':
            c.comment+=' LCSC C165948 (HRO TYPE-C-31-M-12), extended; shell stakes are through-hole (hybrid assembly).'
        if c.ref=='JP3':
            c.comment+=' LCSC C49257 is a through-hole header (wave-solder class): supplier THT option or hand solder.'
        if c.ref=='JP1':
            # r5l: JP1 (bus ARM) becomes 1x3 like JP3, so the shunt can be parked on an unconnected pin
            # when the bus must stay isolated. 1-2 = armed (TAB_PGOOD -> BUS_ARM), 2-3 = parked/off.
            c.sym='Connector_Generic:Conn_01x03'
            c.fp='Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'
            c.value='B-2100S02P-A110'.replace('B-2100S02P-A110','BUS ARM')
            c.pins={'1':'TAB_PGOOD','2':'BUS_ARM','3':None}
            c.lcsc='C49257'
            c.comment='BUS ARM: shunt on 1-2 = bus switches allowed when the Tab5 3.3V is good (TAB_PGOOD->BUS_ARM); shunt on 2-3 (pin3 NC) = parked, bus stays isolated. LCSC C49257 is through-hole (wave-solder class): supplier THT option or hand solder.'
    sw=Comp('SW4','carrier:SW_SLIDE_DP3T_SS-23D03','carrier:SW_SLIDE_DP3T_SS-23D03-G080','SS-23D03-G080',
        {'1':'BUCK_5V','2':None,'3':'VBUS_PD','4':'+5V','5':'PD_CFG1','6':None,'7':None,'8':'GND','9':'GND','10':'GND'},
        'r5power',pos=(43,26),lcsc='C2848921',
        comment='RUN/PROGRAM slide switch replacing JP2+JP4. Pos1=RUN (BUCK_5V->+5V, PD_CFG1->GND), pos2=middle=all open, pos3=PROGRAM (VBUS_PD->+5V, PD_CFG1 left open: R73 pulls it up to VHV = 5V request; pad6 is NOT connected because the CH224A CFG1 pin is limited to 3.8V). Through-hole, hand/wave solder. Pad pairing 1&8/2&7/3&6 inferred from EasyEDA symbol: VERIFY ON REAL PART. JP3 is NOT linked: set JP3 by hand (1-2 RUN, 2-3 PROGRAM).')
    cs.append(sw)
    for c in cs:
        if c.ref=='JP3':
            c.comment='MOVE JP3 BY HAND TOGETHER WITH SW4, ALL INPUTS UNPLUGGED. RUN1-2, PROGRAM2-3. SW4 does not control JP3.'
    return cs


# ---- CH224K -> CH224A (JLCPCB: CH224K out of stock). Source: WCH CH224 datasheet V2.1, chapter 7.
#   pin 1 is VHV (4..30 V, abs max 32 V) instead of VDD (3.6 V): R1 = 0R; the VBUS pin must be shorted to VHV:
#   R2 = 0R. CFG1 abs max is 3.8 V (K: 8 V): CFG1 high only through 100k to VHV (R73) -> SW4 pad6 is open.
#   12 V request (CFG1=0, CFG2=0, CFG3=1) is the same in the I/O-level tables of both chips; CFG3 has an
#   internal pull-up on the A (R4 stays unfitted); CFG2 is tied to GND by R5 (0R).
_r5l_build = build
def build():
    cs=_r5l_build()
    for c in cs:
        if c.ref=='U1':
            c.sym='carrier:CH224A';c.value='CH224A';c.lcsc='C42459160'
            c.comment=('WCH CH224A (ESSOP-10, pin-compatible with CH224K), 12V request: CFG1=0 CFG2=0 CFG3=1(internal PU). '
                       'Pin 1 = VHV, pin 8 VBUS must be shorted to VHV (R1, R2 = 0R). CFG1 max 3.8V: only R73 (100k to VHV) may pull it up.')
        if c.ref in ('R1','R2'):
            c.value='0R';c.lcsc='C21189'
            c.comment=('0R for the CH224A: '+('VHV supply directly from VBUS' if c.ref=='R1' else 'VBUS detect pin shorted to VHV')
                       +' (CH224K needed 10k / 1k here). WCH CH224 datasheet V2.1 chapter 7.2.')
        if c.ref=='R73':
            c.comment='CFG1 pull-up to VHV through 100k (WCH datasheet 5.2.2 / 6.1.2): requests 5V when SW4 pad8 (GND) is not selected.'
    return cs


# ---- r5l: SW4 switches SIGNALS only; the +5V current goes through P-MOSFET load switches.
# Reason: SS-23D03-G080 is rated 0.3 A / 50 V DC (manufacturer datasheet; LCSC lists 1 A) while the +5V rail
# feeds the Core, the 3.3V LDO, the FT232H and HDMI 5V (F2 = 500 mA PTC). See docs/r5s_SW4ロードスイッチ式の検討_2026-11-06.md
# and sim-spice/ (generic models, NOT hardware verified).
#   RUN path: Q11/Q12 back-to-back P-MOS, drains BUCK_5V / +5V, common source LS_SCR, gate RUN_G.
#   PGM path: Q13/Q14 back-to-back P-MOS, drains VBUS_PD / +5V, common source LS_SCP, gate PGM_G.
#   Gates are pulled up to the common source by 100k (off) and pulled to GND through 4.7k by SW4 (on).
#   Over-voltage guard on the PGM path: Q15 (P-MOS, source LS_SCP, drain PGM_G, gate LS_KG), 10k LS_SCP-LS_KG,
#   zener 6.2V LS_KG-GND: when VBUS exceeds about 7V Q15 pulls PGM_G up and the PGM path turns off.
_r5l_ch224_build = build
def build():
    cs=_r5l_ch224_build()
    for c in cs:
        if c.ref=='SW4':
            c.pins={'1':'SW_RUN','2':None,'3':'SW_PGM','4':'GND','5':'PD_CFG1','6':None,'7':None,'8':'GND','9':'GND','10':'GND'}
            c.comment=('RUN/PROGRAM slide switch, SIGNALS ONLY (rated 0.3 A: it no longer carries the +5V current). Pole A common (pad4) = GND; '
                       'pos1=RUN: pad1 (SW_RUN) to GND turns the BUCK_5V load switch on and pad5 (PD_CFG1) to GND requests 12V; pos2=middle=all open (both load switches off, '
                       'PD requests 5V via R73); pos3=PROGRAM: pad3 (SW_PGM) to GND turns the VBUS_PD load switch on (PD_CFG1 left open = 5V request; pad6 stays NC: CH224A CFG1 max 3.8V). '
                       'Pad pairing 1&8/2&7/3&6 confirmed against the G-Switch circuit drawing (two bars move together); which lever end is RUN/PGM must still be checked on a real part. JP3 is NOT linked.')
    def add(ref,sym,fp,value,pins,lcsc,comment=''):
        cs.append(Comp(ref,sym,fp,value,pins,'r5power',pos=(40,18),lcsc=lcsc,comment=comment))
    sot='Package_TO_SOT_SMD:SOT-23'
    def pm(ref,drain,gate,source,comment):
        add(ref,'Transistor_FET:AO3401A',sot,'AO3401A',{'1':gate,'2':source,'3':drain},'C15127',comment)
    pm('Q11','BUCK_5V','RUN_G','LS_SCR','RUN load switch, BUCK_5V side. Back-to-back with Q12 (sources tied): no reverse current either way; the common source is the higher of BUCK_5V and +5V.')
    pm('Q12','+5V','RUN_G','LS_SCR','RUN load switch, +5V side (see Q11).')
    pm('Q13','VBUS_PD','PGM_G','LS_SCP','PROGRAM load switch, VBUS_PD side. Back-to-back with Q14: VBUS_PD may be 12V while the path is off and never drives +5V; +5V never drives VBUS_PD.')
    pm('Q14','+5V','PGM_G','LS_SCP','PROGRAM load switch, +5V side (see Q13).')
    pm('Q15','PGM_G','LS_KG','LS_SCP','PROGRAM over-voltage guard: turns Q13/Q14 off when VBUS_PD exceeds about 7V (insurance for the 12V -> PROGRAM transition; generic-model SPICE only).')
    add('D12','Device:D_Zener','Diode_SMD:D_SOD-123','BZT52C6V2',{'1':'LS_KG','2':'GND'},'C19077403','Guard zener 6.2V: cathode on LS_KG, anode GND. extended part (JLCPCB)')
    def r(ref,value,a,b,lcsc,comment=''):
        add(ref,'Device:R','Resistor_SMD:R_0603_1608Metric',value,{'1':a,'2':b},lcsc,comment)
    r('R91','100k','LS_SCR','RUN_G','C25803','RUN gate pull-up to the common source (switch off)')
    r('R92','4.7k','RUN_G','SW_RUN','C23162','RUN gate pull-down through SW4 (switch on)')
    r('R93','100k','LS_SCP','PGM_G','C25803','PROGRAM gate pull-up to the common source (switch off)')
    r('R94','4.7k','PGM_G','SW_PGM','C23162','PROGRAM gate pull-down through SW4 (switch on)')
    r('R95','10k','LS_SCP','LS_KG','C25804','Guard: sets the Q15 turn-on with the zener (10k, not 100k: zener leakage must not trip at VBUS 5.5V)')
    return cs
