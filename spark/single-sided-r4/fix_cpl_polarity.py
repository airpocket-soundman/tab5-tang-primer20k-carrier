"""Fix the CPL rotation of the polarity-sensitive diodes D1-D8 of both r4 variants (full, lite-a).

Why: the r4 corrections fitted the LCSC footprint to the KiCad footprint by pad NUMBER. For the SS54
(D1,D2,D4), SMBJ15A (D3) and LED (D5-D8) the pad numbers mean opposite functions in the two libraries
(KiCad pad1 = cathode, LCSC pad1 = anode), so the published rotations were 180 degrees off and would
mount the parts reversed. Both libraries have the cathode on the same physical side at rotation 0,
so the polarity-correct CPL rotation equals the KiCad rotation. Positions are unchanged (symmetric parts).
See docs/r4_CPLダイオード極性調査_2026-11-06.md.

Idempotent. Only touches: assembly-placement-corrections.json, each variant's jlc-cpl.csv,
package-check.json (via finalize_placement.py) and the jlc-cpl.csv hash in order-profile.json.
It never touches a PCB file. Usage (normal python):  python fix_cpl_polarity.py
"""
import csv, glob, hashlib, json
from pathlib import Path
import finalize_placement

ROOT = Path(__file__).resolve().parent
REFS = ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8']
NOTE = ('2026-11-06 polarity fix: rotation set to the KiCad rotation (pin-function match). '
        'The earlier value came from a pad-number match and was 180 degrees off for diodes/LEDs.')

def main():
    path = ROOT / 'assembly-placement-corrections.json'
    raw = path.read_text(encoding='utf8')
    data = json.loads(raw)
    assert json.dumps(data, indent=2, ensure_ascii=False) + '\n' == raw or json.dumps(data, indent=2, ensure_ascii=False) == raw, \
        'unexpected JSON formatting: refusing to rewrite'
    changed = {}
    for variant, rec in data['variants'].items():
        folder = Path(glob.glob(str(ROOT / variant / 'design/manufacturing/*single-sided-r4*'))[0])
        kicad = {r['Ref']: r for r in csv.DictReader((folder / 'kicad-position.csv').open(encoding='utf8'))}
        for ref in REFS:
            p = rec['placements'][ref]
            want = int(round(float(kicad[ref]['Rot']))) % 360
            if p.get('polarity_fix'):
                continue
            p['previous_before_polarity_fix'] = p['angle_deg']
            p['angle_deg'] = want
            p['polarity_fix'] = NOTE
            changed.setdefault(variant, []).append((ref, p['previous_before_polarity_fix'], want))
    if changed:
        data['polarity_fix_2026-11-06'] = ('D1-D8 rotations of both variants were set to the KiCad rotation; see '
                                           'docs/r4_CPLダイオード極性調査_2026-11-06.md')
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    # regenerate each variant's jlc-cpl.csv and package-check.json (checks the board hash first)
    for variant in data['variants']:
        n = finalize_placement.apply(variant)
        print(variant, 'CPL rows rewritten:', n)
        folder = Path(glob.glob(str(ROOT / variant / 'design/manufacturing/*single-sided-r4*'))[0])
        new_sha = hashlib.sha256((folder / 'jlc-cpl.csv').read_bytes()).hexdigest()
        prof = ROOT / variant / 'order-profile.json'
        if prof.exists():
            text = prof.read_text(encoding='utf8')
            obj = json.loads(text)
            art = obj.get('artifacts', {}).get('jlc-cpl.csv')
            if art and art.get('sha256') != new_sha:
                art['sha256'] = new_sha
                prof.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
                print('  order-profile.json: jlc-cpl.csv hash updated')
    for v, rows in changed.items():
        print(v, rows)

if __name__ == '__main__':
    main()
