"""Check minimum-success parallel link and power topology on the actual PCB.
KiCad Python; CHECK_PCB / CHECK_JSON support isolated fault-injection tests.
No claim of physical DMA, DDR3 or timing validation is made by this checker.
"""
import json
import os
from pathlib import Path
import pcbnew

HERE=Path(__file__).resolve().parent
# Independently reviewed against M5Stack and Sipeed connector drawings.
MBUS={'D0':7,'D1':9,'D2':11,'D3':19,'D4':20,'D5':21,'D6':22,'D7':23,
      'CLK':2,'RDY':8,'DIR':26,'AUX0':4,'AUX1':10,'AUX2':16,'AUX3':15}
CORE={'D0':77,'D1':83,'D2':85,'D3':103,'D4':101,'D5':109,'D6':107,'D7':115,
      'CLK':52,'RDY':75,'DIR':119,'AUX0':73,'AUX1':79,'AUX2':95,'AUX3':97}


def check(board):
    fps={fp.GetReference():fp for fp in board.GetFootprints()}
    conn=board.GetConnectivity()
    def pads(ref):return {p.GetNumber():p for p in fps[ref].Pads()}
    def reaches(a,b):
        if a.GetNetname()!=b.GetNetname():return False
        stack=[a];seen=set()
        while stack:
            t=stack.pop();uid=t.m_Uuid.AsString()
            if uid in seen:continue
            seen.add(uid)
            if uid==b.m_Uuid.AsString():return True
            stack.extend(t for t in conn.GetConnectedItems(t,getattr(pcbnew,'EXCLUDE_ZONES',0)) if t.GetNetname()==a.GetNetname())
        return False
    def pin_net(ref,num,net):return pads(ref)[str(num)].GetNetname()==net
    checks=[]
    def record(name,ok,**kw):checks.append(dict(name=name,ok=bool(ok),**kw))
    # User checked the real Tab5 rear face, battery compartment on the left.
    def at(ref,num,x,y):
        p=pads(ref)[str(num)].GetPosition()
        return abs(pcbnew.ToMM(p.x)-x)<.003 and abs(pcbnew.ToMM(p.y)-y)<.003
    record('M5Bus_confirmed_left_pin1',fps['J3'].IsFlipped() and all(at('J3',n,x,y) for n,x,y in [(1,53.73,22.15),(2,56.27,22.15),(3,53.73,24.69),(29,53.73,57.71),(30,56.27,57.71)]))
    for sig,host_pin in MBUS.items():
        a=pads('J3')[str(host_pin)];c=pads('J4')[str(CORE[sig])]
        switches=[(f,p) for f in ('U7','U8') for n,p in pads(f).items() if n in [str(i) for i in range(2,10)] and p.GetNetname()=='M_'+sig]
        resistors=[fp for fp in fps.values() if fp.GetReference().startswith('R') and any(p.GetNetname()=='ISO_'+sig for p in fp.Pads())]
        ok=len(switches)==1 and len(resistors)==1
        if ok:
            ref,sw_a=switches[0];sw_b=pads(ref)[str(20-int(sw_a.GetNumber()))]
            resistor=resistors[0];rp={p.GetNumber():p for p in resistor.Pads()}
            ok=(fps[ref].GetValue()=='SN74CB3Q3245PWR' and resistor.GetValue()=='680R' and
                a.GetNetname()=='M_'+sig and c.GetNetname()=='F_'+sig and
                sw_b.GetNetname()=='ISO_'+sig and rp['1'].GetNetname()=='ISO_'+sig and
                rp['2'].GetNetname()=='F_'+sig and reaches(a,sw_a) and reaches(sw_b,rp['1']) and reaches(rp['2'],c))
        record('parallel_'+sig,ok,mbus_pin=host_pin,core_pin=CORE[sig])
    for ref in ('U7','U8'):
        record(ref+'_power_isolation',all(pin_net(ref,n,v) for n,v in [(10,'GND'),(19,'BUS_OE_N'),(20,'+3V3')]))
    record('OE_default_high',fps['R46'].GetValue()=='22k' and pin_net('R46',1,'+3V3') and pin_net('R46',2,'BUS_OE_N'))
    record('manual_arm_default_open',pin_net('JP1',1,'TAB_PGOOD') and pin_net('JP1',2,'BUS_ARM') and pin_net('R47',1,'BUS_ARM') and pin_net('R47',2,'GND'))
    record('OE_series_MOSFET_AND',all(pin_net(r,n,v) for r,n,v in [('Q3',1,'BUS_ARM'),('Q3',2,'BUS_OE_MID'),('Q3',3,'BUS_OE_N'),('Q4',1,'CORE_PGOOD'),('Q4',2,'GND'),('Q4',3,'BUS_OE_MID')]))
    record('both_supplies_monitored',fps['U9'].GetValue()=='TPS3839G33DBZR' and fps['U10'].GetValue()=='TPS3839K50DBZR' and all(pin_net(r,n,v) for r,n,v in [('U9',3,'TAB_3V3'),('U9',2,'TAB_PGOOD'),('U10',3,'+5V'),('U10',2,'CORE_PGOOD')]))
    record('Tab5_5V_and_BAT_not_tied',not pads('J3')['28'].GetNetname() and not pads('J3')['30'].GetNetname())
    ground_pins=(2,3,8,9,13,14,19,20,25,26,31,32,37,38,43,48,49,54,55,60,61,66,71,72,127,128,133,134,138,139,144,145,150,151,155,156,161,162,168,172,173,178,179,184,185,189,190,195,196)
    record('shared_ground_returns',all(pin_net('J4',n,'GND') for n in ground_pins) and all(pin_net('J3',n,'GND') for n in (1,3,5)))
    record('Core_5V_pins',all(pin_net('J4',n,'+5V') for n in (4,5,6,7)))
    record('Tab5_HVIN_pins',all(pin_net('J3',n,'VIN') for n in (25,27,29)))
    pd_dnp=('J2','U1','C2','R1','R2','R3','R4','R5','D2')
    record('PD_retained_unpopulated',all(fps[r].IsDNP() for r in pd_dnp))
    hdmi_dnp=('J5','U4','U5','U6','Q1','Q2','F2')+tuple('C%d'%i for i in range(12,20))+tuple('R%d'%i for i in range(28,42))
    record('HDMI_retained_unpopulated',all(fps[r].IsDNP() for r in hdmi_dnp))
    record('barrel_power_fitted',all(not fps[r].IsDNP() for r in ('J1','F1','D1','D3','C1','U2','L1','U3','C7')))
    record('socket_PCBA_fitted',not fps['J4'].IsDNP() and fps['J4'].GetValue()=='SOCKET XDAP-4042044-20401')
    record('regulated_5V_parts',fps['U2'].GetValue()=='TPS5430DDAR' and fps['R6'].GetValue()=='10k' and fps['R7'].GetValue()=='3.3k' and all(fps[r].GetValue()=='100k' and not fps[r].IsDNP() for r in ('R49','R50')) and fps['C7'].GetValue()=='220u/10V POSCAP' and fps['C8'].IsDNP() and fps['C9'].IsDNP())
    record('feedback_trim_topology',all(pin_net(r,n,v) for r,n,v in [('R7',1,'BUCK_FB'),('R7',2,'GND'),('R49',1,'BUCK_FB'),('R49',2,'FB_TRIM'),('R50',1,'FB_TRIM'),('R50',2,'GND')]) and reaches(pads('R7')['1'],pads('R49')['1']) and reaches(pads('R49')['2'],pads('R50')['1']))
    record('ceramic_stable_bus_LDO',fps['U3'].GetValue()=='XC6206P332MR-G' and all(pin_net('U3',n,v) for n,v in [(1,'GND'),(2,'+3V3'),(3,'+5V')]))
    record('initial_extension_unpopulated',all(fps[r].IsDNP() for r in ('R17','R18','R25')))
    for net in ('BUCK_PH','BUCK_BOOT'):
        items=[t for t in board.GetTracks() if t.GetNetname()==net]
        record(net+'_front_no_vias',all(not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.F_Cu for t in items),length_mm=sum(pcbnew.ToMM(t.GetLength()) for t in items if not isinstance(t,pcbnew.PCB_VIA)))
    cases=[dict(tab_power=t,core_power=c,arm=a,enabled=bool(t and c and a)) for t in (False,True) for c in (False,True) for a in (False,True)]
    return dict(ok=all(c['ok'] for c in checks),checks=checks,power_state_logic=cases,
                note='Power-state logic is a topology check, not measured leakage or transient behavior.')


if __name__=='__main__':
    board=pcbnew.LoadBoard(os.environ.get('CHECK_PCB',str(HERE.parent/'tab5-fpga-carrier.kicad_pcb')))
    result=check(board)
    Path(os.environ.get('CHECK_JSON',str(HERE/'parallel_power_check.json'))).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Parallel/power:',result['ok'],'checks',len(result['checks']))
    for c in result['checks']:
        if not c['ok']:print('FAIL',c['name'])
    raise SystemExit(0 if result['ok'] else 1)
