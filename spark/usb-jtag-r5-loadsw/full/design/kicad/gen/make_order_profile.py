"""r5l: write order/order-profile.json with the file hashes (normal python). Run after export_order.py,
make_order_bom.py and make_cpl.py, and after check_order.py has passed."""
import hashlib, json
from pathlib import Path
H = Path(__file__).resolve().parents[1]
ORDER = H.parents[2] / 'order'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
pcb = H / 'tab5-fpga-carrier-r5l.kicad_pcb'
profile = {
    'revision': 'r5l: USB-JTAG manual mode, SW4 slide switch replaces JP2+JP4, JP1 1x3',
    'date': '2026-11-06',
    'status': 'ORDER CANDIDATE for a PoC. Not ordered. Not hardware-verified. Not a release (see README.md).',
    'board': {
        'dimensions_mm': [125, 78], 'layers': 4, 'material': 'FR-4', 'stackup': 'JLC04161H-7628',
        'finished_thickness_mm': 1.6, 'copper': {'outer_finished_um': 35, 'inner_um': 15.2},
        'note': 'Same stackup as the r4 PoC profile; do not change it without re-checking the impedance-controlled traces.',
        'origin_mm': [2, 79],
    },
    'assembly': {
        'SMT_side': 'top only',
        'pcba_designators': 134, 'pcba_bom_rows': 54,
        'manual_not_in_pcba': ['J3 (2x15 header, bottom side, LCSC C56496)', 'H1-H6 mounting holes'],
        'not_fitted_DNP': ['R4', 'R17', 'R18', 'R25', 'C8', 'C9', 'J6', 'J7', 'J8'],
        'through_hole_candidates_in_pcba_files': {
            'SW4': 'C2848921 (extended, wave-solder class)', 'JP1': 'C49257 (extended, wave-solder class)',
            'JP3': 'C49257 (extended, wave-solder class)', 'J1': 'C381116 (extended)'},
        'through_hole_fallback': 'If the supplier cannot assemble a through-hole part, buy the same LCSC part separately and hand solder; remove it from the PCBA order to avoid duplicate procurement (see lcsc-separate-order.csv group B).',
        'hybrid': ['J2: SMT contacts + through-hole shell stakes', 'J5: SMT contacts + through-hole shell tabs'],
        'separate_accessories': ['C5305 shunt x2 (JP1, JP3)'],
        'user_supplied': ['Tab5', 'Tang Primer 20K Core', 'M3 hardware'],
    },
    'placement': {
        'basis': 'LCSC/EasyEDA footprint frames fitted by numbered pads; polarity-sensitive diodes D1-D8 fitted by pin FUNCTION (see README: differs from r4).',
        'record': 'placement-corrections.json',
        'cpl_coordinates': 'Gerber plot origin = board lower-left (2,79), +X right, +Y up, mm',
        'supplier_review': 'The correction is to the supplier library frame, not a confirmation of tape/reel orientation. Check polarity and pin 1 in the order preview before paying.',
    },
    'source_pcb_sha256': hashlib.sha256(pcb.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
    'artifacts': {p.name: sha(p) for p in sorted(ORDER.iterdir()) if p.is_file() and p.name not in ('order-profile.json',)},
    'verification': {'ERC_errors': 0, 'PCB_DRC_violations': 0, 'PCB_unconnected': 0, 'BOM_CPL_reference_sets_equal': True,
                     'scope': 'Data consistency only. Not factory acceptance, not physical validation.'},
}
(ORDER / 'order-profile.json').write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
print('wrote order-profile.json,', len(profile['artifacts']), 'artifact hashes')
