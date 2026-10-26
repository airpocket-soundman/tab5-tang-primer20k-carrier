"""Apply audited supplier-library frames to CPL, never to physical copper.

Idempotent absolute coordinates; refuses a changed board or reference/SKU set.
"""
from pathlib import Path
import csv, hashlib, json

ROOT = Path(__file__).resolve().parent

def apply(variant):
    home = ROOT / variant / 'design'
    folder = next((home / 'manufacturing').glob('*single-sided-r4*'))
    audit = json.loads((ROOT / 'assembly-placement-corrections.json').read_text(encoding='utf8'))
    record = audit['variants'][variant]
    board = home / 'kicad/tab5-fpga-carrier.kicad_pcb'
    assert hashlib.sha256(board.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == record['board_sha256']
    with (folder / 'jlc-cpl.csv').open(encoding='utf8', newline='') as f:
        rows = list(csv.DictReader(f))
    assert {r['Designator'] for r in rows} == set(record['placements'])
    for row in rows:
        p = record['placements'][row['Designator']]
        row.update({'Mid X': f"{p['x_mm']:.6f}", 'Mid Y': f"{p['y_mm']:.6f}", 'Rotation': str(p['angle_deg'])})
        assert row['Layer'].lower() == 'top'
    with (folder / 'jlc-cpl.csv').open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['Designator','Mid X','Mid Y','Layer','Rotation'])
        writer.writeheader(); writer.writerows(rows)
    check_path = folder / 'package-check.json'
    check = json.loads(check_path.read_text(encoding='utf8'))
    check['status'] = 'PoC manufacturing data checked; supplier preview/assembly acceptance and hardware validation remain order/build steps.'
    check['cpl_coordinates'] = 'Gerber plot origin, +X right +Y up; supplier footprint frame fitted by numbered pads; see assembly-placement-corrections.json. J3 excluded.'
    check['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file() and p.name != 'package-check.json'}
    check.pop('source_erc_errors', None)
    check_path.write_text(json.dumps(check, indent=2)+'\n', encoding='utf8')
    return len(rows)

if __name__ == '__main__':
    for name in ['full','lite-a']:
        print(name, apply(name))
