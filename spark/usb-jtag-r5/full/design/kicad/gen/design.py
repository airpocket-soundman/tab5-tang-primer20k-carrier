"""r5 manual RUN/PROGRAM selector; user-selected cost reduction2026-11-03."""
from design_r4 import *
import design_r4 as previous
import json
from pathlib import Path

PROJECT='tab5-fpga-carrier-r5'
VARIANT='spark-full-manual-usb-jtag-r5'
CORE_PINS=dict(previous.CORE_PINS)
CORE_PINS.update({'JTAG_TMS':143,'JTAG_TDO':147,'JTAG_TCK':149,'JTAG_TDI':153})
POWER_FIXED=dict(previous.POWER_FIXED)
POWER_FIXED.update({'Y1':((19,31.5),90),'C86':((18,28),0),'C87':((16,35),0)})

def build():
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
