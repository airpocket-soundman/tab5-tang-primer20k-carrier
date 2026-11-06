"""r5c (VBUS over-voltage cut-off) design checks. Exit != 0 on any failure.

Checks the exported schematic netlist, the difference to the current r5 contract, the saved
ERC/DRC reports and the r4 preservation hashes. It is NOT a simulation: see sim-spice/.
Usage (normal python):  python verify_design.py
"""
from pathlib import Path
import json, hashlib, xml.etree.ElementTree as ET
H = Path(__file__).resolve().parent
ROOT = H.parents[1]
K = H / 'full/design/kicad'
R5 = ROOT / 'spark/usb-jtag-r5/full/design/kicad'

tree = ET.parse(K / 'sim/netlist.xml')
pins = {(n.attrib['ref'], n.attrib['pin']): net.attrib['name'].lstrip('/')
        for net in tree.findall('.//nets/net') for n in net.findall('node')}

def same(*nodes):
    nets = [pins.get(n) for n in nodes]
    assert nets[0] and len(set(nets)) == 1, ('net mismatch', nodes, nets)
def different(a, b):
    assert pins.get(a) != pins.get(b), (a, b, 'unexpectedly the same net')

# --- over-voltage cut-off topology
same(('Q9', '3'), ('JP2', '3'))                                   # VBUS_PGM: P-MOS drain -> JP2 pin3
same(('Q9', '2'), ('J2', 'A4'), ('J2', 'B9'), ('D2', '2'), ('D12', '1'), ('R91', '1'), ('R92', '1'), ('R1', '1'), ('R88', '1'))  # upstream VBUS_PD
same(('Q9', '1'), ('Q10', '3'), ('R91', '2'))                      # OVP_G
same(('Q10', '1'), ('Q11', '3'), ('R92', '2'))                     # OVP_NG
same(('Q11', '1'), ('R93', '2'), ('R94', '1'))                     # OVP_B
same(('D12', '2'), ('R93', '1'))                                   # OVP_Z
same(('Q10', '2'), ('Q11', '2'), ('R94', '2'), ('JP4', '1'))       # GND
different(('JP2', '3'), ('Q9', '2'))                               # the only path VBUS -> JP2.3 is through Q9
assert pins[('JP2', '3')] == 'VBUS_PGM'
# --- unchanged r5 function
same(('JP2', '1'), ('L1', '2'), ('R6', '1'), ('C7', '1'))
same(('JP2', '2'), ('J4', '4'), ('J4', '5'), ('J4', '6'), ('J4', '7'), ('U3', '3'), ('U17', '40'))
same(('JP3', '2'), ('J3', '25'), ('J3', '27'), ('J3', '29'))
same(('JP4', '2'), ('U1', '9'), ('R73', '2'))
same(('JP4', '3'), ('U1', '1'), ('R73', '1'))
same(('J4', '143'), ('R85', '2')); same(('J4', '147'), ('U19', '12'))
same(('J4', '149'), ('R83', '2')); same(('J4', '153'), ('R84', '2'))
same(('Q7', '3'), ('Q8', '1')); same(('Q8', '3'), ('U17', '34'))

# --- contract difference to the current r5: exactly the 8 new parts and JP2 pin3
new = json.loads((K / 'circuit-contract.json').read_text())
old = json.loads((R5 / 'circuit-contract.json').read_text())
added = sorted(set(new) - set(old))
assert added == sorted(['Q9', 'Q10', 'Q11', 'D12', 'R91', 'R92', 'R93', 'R94']), added
assert not (set(old) - set(new)), 'parts removed'
changed = []
for ref in old:
    if old[ref] != new[ref]:
        changed.append(ref)
assert changed == ['JP2'], changed
assert {p for p in old['JP2']['pins'] if old['JP2']['pins'][p] != new['JP2']['pins'][p]} == {'3'}

# --- BOM: every new part has an LCSC number
import csv
bom = {r['Reference']: r for r in csv.DictReader((K / 'bom-r5c.csv').open(encoding='utf8'))}
for ref in added:
    assert bom[ref]['LCSC'], ('no LCSC number', ref)

# --- saved ERC/DRC reports
erc = json.loads((K / 'sim/erc.json').read_text(encoding='utf8'))
viol = [x for s in erc['sheets'] for x in s['violations']]
erc_err = [x for x in viol if x['severity'] == 'error']
assert not erc_err, erc_err[:3]
drc = json.loads((K / 'sim/drc.json').read_text(encoding='utf8'))
assert not drc['violations'] and not drc['unconnected_items'], (len(drc['violations']), len(drc['unconnected_items']))

# --- r4 preservation (same list as r5)
saved = json.loads((R5.parent.parent.parent / 'preserved-r4.json').read_text())
# The r4 CPL polarity fix (2026-11-06, docs/r4_CPLダイオード極性調査_2026-11-06.md) changed exactly these
# r4 files on purpose; every other preserved r4 file must still match. No PCB/schematic file is in this set.
INTENTIONAL_R4_CPL_FIX = {
    'spark/single-sided-r4/assembly-placement-corrections.json',
    'spark/single-sided-r4/full/order-profile.json',
    'spark/single-sided-r4/lite-a/order-profile.json',
    'spark/single-sided-r4/full/design/manufacturing/spark-lcsc-review-single-sided-r4-2026-10-26/jlc-cpl.csv',
    'spark/single-sided-r4/full/design/manufacturing/spark-lcsc-review-single-sided-r4-2026-10-26/package-check.json',
    'spark/single-sided-r4/lite-a/design/manufacturing/spark-lite-a-lcsc-review-single-sided-r4-2026-10-26/jlc-cpl.csv',
    'spark/single-sided-r4/lite-a/design/manufacturing/spark-lite-a-lcsc-review-single-sided-r4-2026-10-26/package-check.json',
}
bad = [f for f, sha in saved['files'].items()
       if hashlib.sha256((ROOT / f.replace(chr(92), '/')).read_bytes()).hexdigest() != sha
       and f.replace(chr(92), '/') not in INTENTIONAL_R4_CPL_FIX]
assert not bad, ('r4 changed', bad[:3])

print(json.dumps({'netlist_topology': 'PASS', 'added_parts': added, 'changed_parts_vs_r5': changed,
                  'erc_errors': len(erc_err), 'erc_warnings': len(viol) - len(erc_err),
                  'pcb_drc_violations': len(drc['violations']), 'pcb_unconnected': len(drc['unconnected_items']),
                  'r4_files_unchanged': len(saved['files']) - len(INTENTIONAL_R4_CPL_FIX),
                  'r4_files_changed_on_purpose_cpl_polarity_fix': len(INTENTIONAL_R4_CPL_FIX)}, indent=2))
