"""r5l: build the EasyEDA Pro importer-compatibility copies of the KiCad sources (normal python).

Same idea as spark/lcsc-priority/design/make_import_compat.py (r4), adapted to r5l:
  * PCB: KiCad 10 writes named-only net references; the EasyEDA Pro importer silently loses them and the
    tracks. The copy carries explicit numbered nets. Geometry is NOT changed.
  * Schematic: power symbols are replaced by ordinary net labels (the importer infers power symbols badly).
The authoritative KiCad sources are never modified.
Usage: python make_import_compat.py [OUTPUT_DIR]   (default: ./import-compat next to this file; not committed)
"""
from pathlib import Path
import sys, json, hashlib, shutil, zipfile, uuid
H = Path(__file__).resolve().parent
K = H.parent / 'full/design/kicad'
sys.path.insert(0, str(K / 'gen'))
import sexp
S = sexp.Str
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else H / 'import-compat'
OUT.mkdir(parents=True, exist_ok=True)
PROJ = 'tab5-fpga-carrier-r5l'

# ---------------------------------------------------------------- PCB with numbered nets
source = K / f'{PROJ}.kicad_pcb'
tree = sexp.parse(source.read_text(encoding='utf8'))
names = set()
def collect(n):
    if not isinstance(n, list) or not n: return
    if n[0] == 'net' and len(n) == 2: names.add(str(n[1]))
    for c in n: collect(c)
collect(tree)
ids = {n: i + 1 for i, n in enumerate(sorted(names))}; ids[''] = 0
def rewrite(n, parent=None):
    if not isinstance(n, list) or not n: return n
    if n[0] == 'net' and len(n) == 2:
        name = str(n[1])
        return ['net', str(ids[name]), sexp.Str(name)] if parent == 'pad' else ['net', str(ids[name])]
    out = [rewrite(c, n[0]) for c in n]
    if n[0] == 'zone':
        net = sexp.first(n, 'net')
        if net is not None and len(net) == 2: out.append(['net_name', sexp.Str(str(net[1]))])
    if n[0] == 'version': return ['version', '20241229']
    return out
converted = rewrite(tree)
index = next(i for i, c in enumerate(converted) if isinstance(c, list) and c and c[0] == 'footprint')
for name, i in reversed(sorted(ids.items(), key=lambda item: item[1])):
    converted.insert(index, ['net', str(i), sexp.Str(name)])
pcb_dir = OUT / 'pcb'
pcb_dir.mkdir(exist_ok=True)
(pcb_dir / source.name).write_text(sexp.dump(converted) + '\n', encoding='utf8')
for name in (f'{PROJ}.kicad_pro', f'{PROJ}.kicad_sch', 'fp-lib-table', 'sym-lib-table'):
    shutil.copyfile(K / name, pcb_dir / name)
shutil.copytree(K / 'lib', pcb_dir / 'lib', dirs_exist_ok=True)
with zipfile.ZipFile(OUT / 'r5l-kicad-compat-import.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in pcb_dir.rglob('*'):
        if p.is_file(): z.write(p, p.relative_to(pcb_dir))

# ---------------------------------------------------------------- schematic with labels instead of power symbols
t = sexp.parse((K / f'{PROJ}.kicad_sch').read_text(encoding='utf8')); out = []; count = 0
for n in t:
    if not isinstance(n, list) or not n or n[0] != 'symbol': out.append(n); continue
    props = {p[1]: p[2] for p in sexp.find(n, 'property')}
    if not props.get('Reference', '').startswith('#'): out.append(n); continue
    if props['Reference'].startswith('#PWR'):
        pos = sexp.first(n, 'at'); net = props['Value']
        out.append(['label', S(net), ['at', pos[1], pos[2], '0'], ['effects', ['font', ['size', '1.27', '1.27']], ['justify', 'left', 'bottom']], ['uuid', S(str(uuid.uuid4()))]])
    count += 1
uuid_map = {}
def gather(n):
    if not isinstance(n, list): return
    if n and n[0] == 'uuid': uuid_map[str(n[1])] = str(uuid.uuid4())
    for c in n: gather(c)
gather(out)
def reidentify(n):
    if not isinstance(n, list): return
    if n and n[0] == 'uuid': n[1] = S(uuid_map[str(n[1])])
    if n and n[0] == 'path' and len(n) > 1 and str(n[1]).startswith('/'):
        for old, new in uuid_map.items():
            if str(n[1]) == '/' + old: n[1] = S('/' + new); break
    for c in n: reidentify(c)
reidentify(out)
(OUT / 'r5l-label-power.kicad_sch').write_text(sexp.dump(out) + '\n', encoding='utf8')
report = {'source_pcb_file_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'named_nets': len(names),
          'power_symbols_replaced_by_labels': count, 'geometry_change': False,
          'purpose': 'EasyEDA Pro importer compatibility only; the KiCad files are authoritative'}
(OUT / 'import-compat-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
print(json.dumps(report))
