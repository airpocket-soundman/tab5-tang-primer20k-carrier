"""Consistency checks of the r5l order data (normal python). Exit != 0 on any failure.

BOM / CPL reference sets, CPL ranges, Gerber zip contents, board hash, ERC/DRC results.
This is NOT a factory acceptance: see order/README.md.
"""
import csv, hashlib, json, zipfile
from pathlib import Path
H = Path(__file__).resolve().parents[1]
ROOT = H.parents[2]
ORDER = ROOT / 'order'
PCB = H / 'tab5-fpga-carrier-r5l.kicad_pcb'

bom = list(csv.DictReader((ORDER / 'jlc-bom.csv').open(encoding='utf8')))
cpl = list(csv.DictReader((ORDER / 'jlc-cpl.csv').open(encoding='utf8')))
bom_refs = [r for row in bom for r in row['Designator'].split(',')]
cpl_refs = [r['Designator'] for r in cpl]
assert len(bom_refs) == len(set(bom_refs)), 'duplicate designator in BOM'
assert len(cpl_refs) == len(set(cpl_refs)), 'duplicate designator in CPL'
assert set(bom_refs) == set(cpl_refs), ('BOM/CPL differ', sorted(set(bom_refs) ^ set(cpl_refs)))
assert all(row['LCSC Part #'] for row in bom), 'BOM row without LCSC number'
for r in cpl:
    x, y, rot = float(r['Mid X']), float(r['Mid Y']), r['Rotation']
    assert r['Layer'].lower() == 'top', r
    assert -2 <= x <= 127 and -2 <= y <= 80, ('outside the board area', r)
    assert rot.lstrip('-').isdigit() and 0 <= int(rot) < 360, ('rotation', r)

# the BOM of the schematic and the order BOM agree on part numbers
full = {r['Reference']: r for r in csv.DictReader((H / 'bom-r5l.csv').open(encoding='utf8'))}
for row in bom:
    for ref in row['Designator'].split(','):
        assert full[ref]['LCSC'] == row['LCSC Part #'], (ref, full[ref]['LCSC'], row['LCSC Part #'])
excluded = {r for r in full if r not in set(bom_refs)}
expected_excluded = {r for r, v in full.items() if v['DNP'] == 'True' or r == 'J3' or r.startswith('H')}
assert excluded == expected_excluded, sorted(excluded ^ expected_excluded)

# Gerber package
z = zipfile.ZipFile(ORDER / 'gerbers.zip')
names = z.namelist()
for suffix in ('-F_Cu.gtl', '-In1_Cu.g1', '-In2_Cu.g2', '-B_Cu.gbl', '-F_Mask.gts', '-B_Mask.gbs',
               '-F_Silkscreen.gto', '-F_Paste.gtp', '-Edge_Cuts.gm1', '-PTH.drl', '-NPTH.drl'):
    assert any(n.endswith(suffix) for n in names), ('missing in gerbers.zip', suffix)

# board hash = the one used for the corrections
rec = json.loads((ORDER / 'placement-corrections.json').read_text(encoding='utf8'))
sha = hashlib.sha256(PCB.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
board_sha = rec.get('board_sha256')
assert board_sha == sha, ('placement-corrections.json was computed for another board file', board_sha, sha)
gx = json.loads((ORDER / 'gerber-export.json').read_text(encoding='utf8'))
assert gx['source_pcb_sha256'] == sha, 'gerbers were exported from another board file'

erc = json.loads((H / 'sim/erc.json').read_text(encoding='utf8'))
errs = [x for s in erc['sheets'] for x in s['violations'] if x['severity'] == 'error']
drc = json.loads((H / 'sim/drc.json').read_text(encoding='utf8'))
assert not errs and not drc['violations'] and not drc['unconnected_items']
print(json.dumps({'pcba_designators': len(bom_refs), 'bom_rows': len(bom), 'cpl_rows': len(cpl),
                  'excluded': sorted(excluded), 'gerber_files': len(names),
                  'board_sha256': sha, 'erc_errors': 0, 'drc_violations': 0, 'drc_unconnected': 0}, indent=1))
