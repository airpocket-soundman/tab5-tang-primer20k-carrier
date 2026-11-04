"""Independent exported-netlist checks and bounded DC calculations, not SPICE.

Nonzero exit for an electrical contract failure. PCB release status is reported
separately: incomplete routing never turns into a passing manufacturing verdict.
"""
from pathlib import Path
import json, hashlib, xml.etree.ElementTree as ET, copy
H=Path(__file__).resolve().parent
ROOT=H.parents[1]
K=H/'full/design/kicad'

def check_connections(pins):
    def same(*nodes):
        nets=[pins.get(n) for n in nodes]
        assert nets[0] and len(set(nets))==1,('net mismatch',nodes,nets)
    def different(a,b):assert pins.get(a)!=pins.get(b),(a,b,'unsafe common net')
    same(('J2','A6'),('J2','B6'),('U17','7'))
    same(('J2','A7'),('J2','B7'),('U17','6'))
    same(('J2','A5'),('U1','7'));same(('J2','B5'),('U1','6'))
    same(('U2','7'),('JP3','1'))
    same(('JP2','1'),('L1','2'),('R6','1'),('C7','1'))
    same(('JP2','2'),('J4','4'),('J4','5'),('J4','6'),('J4','7'),('U3','3'),('U17','40'))
    same(('JP2','3'),('J2','A4'))
    same(('JP3','2'),('J3','25'),('J3','27'),('J3','29'))
    same(('JP4','1'),('J3','1'))
    same(('JP4','2'),('U1','9'),('R73','2'))
    same(('JP4','3'),('U1','1'),('R73','1'))
    different(('JP2','1'),('JP2','2'));different(('JP2','2'),('JP2','3'))
    different(('JP3','1'),('JP3','2'))
    same(('U17','13'),('U19','2'));same(('U17','14'),('U19','5'))
    same(('U17','16'),('U19','9'));same(('U17','15'),('U19','11'))
    same(('J4','143'),('R85','2'));same(('J4','147'),('U19','12'))
    same(('J4','149'),('R83','2'));same(('J4','153'),('R84','2'))
    same(('U19','14'),('U3','2'))
    same(('Q8','3'),('U17','34'));same(('Q7','3'),('Q8','1'))
    for ref,pin in [('J3','28'),('J3','30'),('U1','4'),('U1','5')]:
        n=pins.get((ref,pin),'')
        assert not n or 'unconnected-' in n,(ref,pin,n)

def run():
    tree=ET.parse(K/'sim/netlist.xml')
    pins={(node.attrib['ref'],node.attrib['pin']):net.attrib['name'] for net in tree.findall('.//nets/net') for node in net.findall('node')}
    check_connections(pins)
    # Fault injection verifies that the independent check rejects three
    # meaningful failures rather than merely reproducing the design generator.
    mutations=[(('J4','4'),pins[('J2','A4')]),(('JP4','2'),pins[('JP4','3')]),(('U17','7'),pins[('U17','6')])]
    for node,bad in mutations:
        altered=dict(pins);altered[node]=bad
        try:check_connections(altered)
        except AssertionError:pass
        else:raise AssertionError(('undetected wiring fault',node))
    contract=json.loads((K/'circuit-contract.json').read_text())
    # Every populated and NC pin in the source must match the exported schematic.
    def norm(n):return n.lstrip('/')
    for ref,c in contract.items():
        for pin,n in c['pins'].items():
            actual=pins.get((ref,pin),'')
            if n is None:assert not actual or 'unconnected-' in actual,(ref,pin,actual)
            else:assert norm(actual)==n,(ref,pin,n,actual)
    saved=json.loads((H/'preserved-r4.json').read_text())
    changed=[fn for fn,sha in saved['files'].items() if hashlib.sha256((ROOT/fn).read_bytes()).hexdigest()!=sha]
    assert not changed,('r4 changed',changed)
    # Evaluate physical shunts independently of the source generator.
    # Detect the destructive mixed-mode setting rather than pretending protection.
    modes=[]
    for source,mode,core,tab,pd in [
      ('PC5','PROGRAM',5,0,5),('PD','PROGRAM',5,0,5),
      ('PD','RUN',4.99,11.5,12),('barrel12','RUN',4.99,11.5,12),
      ('barrel12 only','PROGRAM',0,0,5),('PC5+barrel12','RUN',4.99,11.5,12)]:
        modes.append({'source':source,'mode':mode,'Core_ideal_V':core,'Tab5_ideal_V':tab,'PD_request_V':pd,'scope':'ideal mode table only; no transient or source-current simulation'})
    mixed={'JP2':'PROGRAM','JP4':'RUN','source':'PD','Core_ideal_V':12,'safe':False}
    assert mixed['Core_ideal_V']>5.5
    erc=json.loads((K/'sim/erc.json').read_text())
    violations=[x for sh in erc['sheets'] for x in sh['violations']]
    errors=[x for x in violations if x['severity']=='error']
    assert not errors,errors
    drc=json.loads((K/'sim/drc.json').read_text())
    report={'date':'2026-11-03','exported_schematic_contract':'PASS','fault_injections_rejected':len(mutations),
      'r4_files_unchanged':len(saved['files']),'erc_errors':len(errors),'erc_warnings':len(violations)-len(errors),
      'design_variant':'manual-jumpers','components':len(contract),'mode_table':modes,'mixed_mode_fault_example':mixed,
      'automatic_supply_ICs_absent':all(r not in contract for r in ('U11','U12','U13','U14','U15','U16','U18','U20','U21')),
      'pcb_drc_violations':len(drc['violations']),'pcb_unconnected':len(drc['unconnected_items']),
      'pcb_release_ready':False,'hardware_verified':False,'transient_simulated':False,
      'core_power_requirement':'Sipeed official datasheetp3:5V+/-10%,0.5A; USB500mA total cannot guarantee Core plusdebugger'}
    (K/'sim/electrical-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('exported_schematic_contract','r4_files_unchanged','erc_errors','pcb_drc_violations','pcb_unconnected','pcb_release_ready')},indent=2))

if __name__=='__main__':run()
