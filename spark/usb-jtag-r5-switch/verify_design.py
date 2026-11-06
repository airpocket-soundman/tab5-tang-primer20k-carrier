"""r5s: exported-netlist checks (no SPICE) for the SW4 slide-switch variant.

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
POSITIONS={1:{'4':'1','5':'8'},2:{},3:{'4':'3','5':'6'}}

def check_connections(pins):
    def same(*nodes):
        nets=[pins.get(n) for n in nodes]
        assert nets[0] and len(set(nets))==1,('net mismatch',nodes,nets)
    same(('J2','A6'),('J2','B6'),('U17','7'))
    same(('J2','A7'),('J2','B7'),('U17','6'))
    same(('U2','7'),('JP3','1'))
    same(('SW4','1'),('L1','2'),('R6','1'),('C7','1'))
    same(('SW4','4'),('J4','4'),('J4','5'),('J4','6'),('J4','7'),('U3','3'),('U17','40'))
    same(('SW4','3'),('J2','A4'))
    same(('JP3','2'),('J3','25'),('J3','27'),('J3','29'))
    same(('SW4','8'),('J3','1'))
    same(('SW4','5'),('U1','9'),('R73','2'))
    same(('SW4','6'),('U1','1'),('R73','1'))
    same(('SW4','9'),('SW4','10'),('SW4','8'))
    for pad in ('2','7'):
        assert 'unconnected-' in pins.get(('SW4',pad),''),('SW4 middle pad must be NC',pad)
    for ref in ('JP2','JP4'):
        assert not any(k[0]==ref for k in pins),(ref,'must be removed')
    assert pins[('SW4','1')]!=pins[('SW4','4')]!=pins[('SW4','3')]

def position_model(pins):
    """Net pairs joined by SW4 in each slider position, and the forbidden-combination check."""
    out={}
    for pos,m in POSITIONS.items():
        out[pos]=sorted((pins[('SW4',c)],pins[('SW4',t)]) for c,t in m.items())
    # the dangerous r5 combination (VBUS_PD -> +5V together with PD_CFG1 -> GND) must not occur
    for pos,pairs in out.items():
        assert not ((('+5V','VBUS_PD') in pairs or ('VBUS_PD','+5V') in pairs) and (('PD_CFG1','GND') in pairs or ('GND','PD_CFG1') in pairs)),pos
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
      'jp3_linked_to_sw4':False,'switch_pad_pairing_verified_on_real_part':False,
      'pcb_release_ready':False,'hardware_verified':False}
    (K/'sim/electrical-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=1))

if __name__=='__main__':run()
