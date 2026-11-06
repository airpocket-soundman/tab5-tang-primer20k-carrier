"""r5l: exported-netlist checks (no SPICE) for the SW4 signal-switch + P-MOS load-switch variant (derived from r5s).

Reads full/design/kicad/sim/{netlist.xml,erc.json,drc.json}; the r4 file hashes are taken from the
read-only r5 record ../usb-jtag-r5/preserved-r4.json. The slider-position model below is an ASSUMPTION
(pad pairing 1&8 / 2&7 / 3&6 inferred from the EasyEDA symbol) that must be confirmed on a real part.
"""
from pathlib import Path
import json, hashlib, xml.etree.ElementTree as ET
H=Path(__file__).resolve().parent
ROOT=H.parents[1]
K=H/'full/design/kicad'

# slider position -> {common pad: connected throw pad}; position 2 connects nothing (pads 2,7 are NC)
# CH224A change: pole B pad 6 (PROGRAM) is NOT connected, so in position 3 PD_CFG1 is only pulled up by R73.
POSITIONS={1:{'4':'1','5':'8'},2:{},3:{'4':'3'}}

def check_connections(pins):
    def same(*nodes):
        nets=[pins.get(n) for n in nodes]
        assert nets[0] and len(set(nets))==1,('net mismatch',nodes,nets)
    same(('J2','A6'),('J2','B6'),('U17','7'))
    same(('J2','A7'),('J2','B7'),('U17','6'))
    same(('U2','7'),('JP3','1'))
    # r5l: the three power trunks reach the load switches, not SW4
    same(('Q11','3'),('L1','2'),('R6','1'),('C7','1'))                                                # BUCK_5V
    same(('Q12','3'),('Q14','3'),('J4','4'),('J4','5'),('J4','6'),('J4','7'),('U3','3'),('U17','40'))   # +5V
    same(('Q13','3'),('J2','A4'))                                                                      # VBUS_PD
    same(('JP3','2'),('J3','25'),('J3','27'),('J3','29'))
    same(('SW4','8'),('J3','1'))
    same(('SW4','4'),('SW4','8'))                                                                      # pole A common = GND
    same(('SW4','5'),('U1','9'),('R73','2'))
    same(('U1','1'),('R73','1'))                       # CH224A VHV pin = the node that pulls CFG1 up through R73
    same(('SW4','9'),('SW4','10'),('SW4','8'))
    for pad in ('2','6','7'):
        assert 'unconnected-' in pins.get(('SW4',pad),''),('SW4 pad must be NC (middle position / CFG1 safety)',pad)
    for ref in ('JP2','JP4'):
        assert not any(k[0]==ref for k in pins),(ref,'must be removed')
    # --- load switches (docs/r5s_SW4ロードスイッチ式の検討_2026-11-06.md)
    assert pins[('Q11','3')]=='BUCK_5V' and pins[('Q12','3')]=='+5V' and pins[('Q13','3')]=='VBUS_PD' and pins[('Q14','3')]=='+5V'
    same(('Q11','2'),('Q12','2'),('R91','1'))                              # LS_SCR: common source of the RUN pair
    same(('Q11','1'),('Q12','1'),('R91','2'),('R92','1'))                  # RUN_G
    same(('R92','2'),('SW4','1'))                                          # SW_RUN
    same(('Q13','2'),('Q14','2'),('Q15','2'),('R93','1'),('R95','1'))      # LS_SCP: common source of the PROGRAM pair
    same(('Q13','1'),('Q14','1'),('Q15','3'),('R93','2'),('R94','1'))      # PGM_G
    same(('R94','2'),('SW4','3'))                                          # SW_PGM
    same(('Q15','1'),('R95','2'),('D12','1'))                              # LS_KG: guard
    assert pins[('D12','2')]=='GND'
    assert len({pins[('Q11','2')],pins[('Q13','2')],pins[('SW4','1')],pins[('SW4','3')]})==4,'common sources / SW nets must be distinct'
    # SW4 no longer carries any power net (it is rated 0.3 A)
    for pad in ('1','3','4','5','8','9','10'):
        assert pins[('SW4',pad)] in ('SW_RUN','SW_PGM','GND','PD_CFG1'),('SW4 carries a power net',pad,pins[('SW4',pad)])

def position_model(pins):
    """Net pairs joined by SW4 in each slider position, and the forbidden-combination check."""
    out={}
    for pos,m in POSITIONS.items():
        out[pos]=sorted((pins[('SW4',c)],pins[('SW4',t)]) for c,t in m.items())
    # the dangerous r5 combination (PROGRAM load switch on, i.e. SW_PGM to GND, together with PD_CFG1 -> GND = 12V request) must not occur;
    # the two load switches are never on together
    def has(pairs,a,b): return (a,b) in pairs or (b,a) in pairs
    for pos,pairs in out.items():
        assert not (has(pairs,'GND','SW_PGM') and has(pairs,'PD_CFG1','GND')),pos
        assert not (has(pairs,'GND','SW_PGM') and has(pairs,'GND','SW_RUN')),pos
    assert has(out[1],'GND','SW_RUN') and has(out[1],'PD_CFG1','GND') and has(out[3],'GND','SW_PGM') and not out[2]
    # CH224A: CFG1 (abs max 3.8 V) may only ever be joined to GND by the switch; never to PD_VDD / VBUS_PD
    for pos,pairs in out.items():
        for a,b in pairs:
            if 'PD_CFG1' in (a,b):
                assert {a,b}=={'PD_CFG1','GND'},('CFG1 joined to a non-GND net',pos,a,b)
    return out

def run():
    tree=ET.parse(K/'sim/netlist.xml')
    pins={(node.attrib['ref'],node.attrib['pin']):net.attrib['name'].lstrip('/') for net in tree.findall('.//nets/net') for node in net.findall('node')}
    check_connections(pins)
    model=position_model(pins)
    contract=json.loads((K/'circuit-contract.json').read_text())
    for ref,c in contract.items():
        for pin,n in c['pins'].items():
            actual=pins.get((ref,pin),'')
            if n is None:assert not actual or 'unconnected-' in actual,(ref,pin,actual)
            else:assert actual==n,(ref,pin,n,actual)
    # CH224A (WCH CH224 datasheet V2.1, chapter 7): VHV supplied through R1 = 0R, VBUS pin shorted to VHV through R2 = 0R
    assert contract['U1']['value']=='CH224A' and contract['U1']['pins']['1']=='PD_VDD' and contract['U1']['pins']['8']=='PD_VBUS_S'
    for ref in ('R1','R2'):
        assert contract[ref]['value']=='0R',(ref,contract[ref]['value'])
        assert contract[ref]['pins']['1']=='VBUS_PD',(ref,'must be fed from VBUS_PD')
    assert contract['R1']['pins']['2']=='PD_VDD' and contract['R2']['pins']['2']=='PD_VBUS_S'
    assert contract['R5']['value']=='0R' and contract['R5']['pins']=={'1':'PD_CFG2','2':'GND'},'CFG2 must stay tied to GND by R5'
    assert contract['R4']['dnp'] and contract['R4']['pins']['1']=='PD_CFG3','CFG3 must stay open (internal pull-up)'
    saved=json.loads((H.parent/'usb-jtag-r5/preserved-r4.json').read_text())
    # The r4 CPL polarity fix (2026-11-06, docs/r4_CPLダイオード極性調査_2026-11-06.md) changed exactly these
    # r4 files on purpose; every other preserved r4 file must still match. No PCB/schematic file is in this set.
    INTENTIONAL_R4_CPL_FIX={
        'spark/single-sided-r4/assembly-placement-corrections.json',
        'spark/single-sided-r4/full/order-profile.json',
        'spark/single-sided-r4/lite-a/order-profile.json',
        'spark/single-sided-r4/full/design/manufacturing/spark-lcsc-review-single-sided-r4-2026-10-26/jlc-cpl.csv',
        'spark/single-sided-r4/full/design/manufacturing/spark-lcsc-review-single-sided-r4-2026-10-26/package-check.json',
        'spark/single-sided-r4/lite-a/design/manufacturing/spark-lite-a-lcsc-review-single-sided-r4-2026-10-26/jlc-cpl.csv',
        'spark/single-sided-r4/lite-a/design/manufacturing/spark-lite-a-lcsc-review-single-sided-r4-2026-10-26/package-check.json'}
    changed=[fn for fn,sha in saved['files'].items() if hashlib.sha256((ROOT/fn).read_bytes()).hexdigest()!=sha
             and fn.replace(chr(92),'/') not in INTENTIONAL_R4_CPL_FIX]
    assert not changed,('r4 changed',changed)
    erc=json.loads((K/'sim/erc.json').read_text(encoding='utf8'))
    violations=[x for sh in erc['sheets'] for x in sh['violations']]
    errors=[x for x in violations if x['severity']=='error']
    assert not errors,errors
    drc=json.loads((K/'sim/drc.json').read_text(encoding='utf8'))
    report={'exported_schematic_contract':'PASS','slider_position_model':{str(k):v for k,v in model.items()},
      'dangerous_combination_possible_with_SW4':False,'r4_files_unchanged':len(saved['files'])-len(INTENTIONAL_R4_CPL_FIX),'r4_files_changed_on_purpose_cpl_polarity_fix':len(INTENTIONAL_R4_CPL_FIX),
      'erc_errors':len(errors),'erc_warnings':len(violations)-len(errors),'components':len(contract),
      'pcb_drc_violations':len(drc['violations']),'pcb_unconnected':len(drc['unconnected_items']),
      'jp3_linked_to_sw4':False,'sw4_carries_power':False,'load_switch_checked_with_generic_spice_models_only':True,
      'switch_pad_pairing_verified_on_real_part':False,
      'pcb_release_ready':False,'hardware_verified':False}
    (K/'sim/electrical-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=1))

if __name__=='__main__':run()
