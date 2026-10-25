"""Independent re-run of the fabrication candidate for the consolidated PCB report.
System Python orchestrates kicad-cli and KiCad Python; `--board` is the KiCad Python
part that measures the board itself. Writes pcb_report_review_2026-10-25.json and
the 3D renders. Nothing here edits the design; a changed check output is a failure.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'kicad/sim'
PCB = ROOT/'kicad/tab5-fpga-carrier.kicad_pcb'
SCH = ROOT/'kicad/tab5-fpga-carrier.kicad_sch'
KICAD = Path(os.environ.get('KICAD_BIN', 'C:/Program Files/KiCad/10.0/bin'))
OUT = HERE/'pcb_report_review_2026-10-25.json'
TMP = HERE/'_review_tmp'
CHECKS = ['check_continuity', 'check_negative', 'check_classification', 'check_esd_footprint', 'check_d1_bias',
          'check_ground_reference', 'check_parallel_power', 'check_power_dc', 'check_mbus_revision',
          'test_classification_check', 'test_d1_bias_check', 'test_esd_check', 'test_parallel_power_check']
# Re-running the model must reproduce these files byte for byte.
MODEL_OUTPUTS = ['tmds_geom.json', 'tmds_roles.json', 'pair_lengths.json', 'tmds_summary.json', 'tmds_sparam.json',
                 'report_sparam.json', 'report_matrix.json', 'report_variants.json', 'report_sensitivity.json']
RENDERS = {'top': ['--side', 'top'], 'bottom': ['--side', 'bottom'],
           'iso': ['--side', 'top', '--perspective', '--rotate', '-40,0,25', '--zoom', '0.9']}


def board_facts():
    import pcbnew
    b = pcbnew.LoadBoard(str(PCB))
    mm = pcbnew.ToMM
    bb = b.GetBoardEdgesBoundingBox()
    w = mm(next(d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts).GetWidth())/2
    left, top, right, bottom = mm(bb.GetLeft())+w, mm(bb.GetTop())+w, mm(bb.GetRight())-w, mm(bb.GetBottom())-w
    holes, tht_top, sides = [], [], {'top': 0, 'bottom': 0}
    for f in b.GetFootprints():
        ref = f.GetReference()
        if ref.startswith('H'):
            pad = next(iter(f.Pads()))
            x, y, r = mm(f.GetPosition().x), mm(f.GetPosition().y), mm(pad.GetDrillSize().x)/2
            holes.append(dict(ref=ref, x_mm=round(x, 2), y_mm=round(y, 2), drill_mm=round(2*r, 2),
                              min_web_mm=round(min(x-r-left, right-x-r, y-r-top, bottom-y-r), 2)))
            continue
        sides['bottom' if f.IsFlipped() else 'top'] += 1
        # Leads of top-side THT parts point at the Tab5 back; thermal vias are not leads.
        if not f.IsFlipped() and any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and mm(p.GetDrillSize().x) >= 0.6 for p in f.Pads()):
            tht_top.append(ref)
    tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
    return dict(size_mm=[round(right-left, 2), round(bottom-top, 2)], copper_layers=b.GetCopperLayerCount(),
                thickness_mm=mm(b.GetDesignSettings().GetBoardThickness()), footprints_by_side=sides,
                holes=sorted(holes, key=lambda h: h['ref']), tht_leads_toward_tab5=sorted(tht_top),
                tracks=len(tracks), vias=sum(isinstance(t, pcbnew.PCB_VIA) for t in b.GetTracks()),
                track_length_m=round(sum(mm(t.GetLength()) for t in tracks)/1000, 2),
                nets=len([n for n in b.GetNetsByName().keys() if str(n)]))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def cli(*args):
    return subprocess.run([str(KICAD/'kicad-cli'), *map(str, args)], capture_output=True, text=True, encoding='utf-8')


def parity():
    """Schematic parity, separating KiCad's naming noise from real differences."""
    drc = TMP/'drc.json'
    cli('pcb', 'drc', '--severity-all', '--all-track-errors', '--schematic-parity', '--format', 'json', '-o', drc, PCB)
    d = json.loads(drc.read_text(encoding='utf-8'))
    cats = {}
    for v in d['schematic_parity']:
        text = v['description']
        m = re.search(r'\((.*?)\).*?\((.*?)\)', text)
        if v['type'] == 'net_conflict' and m and m.group(2).lstrip('/') == m.group(1):
            key = 'net name differs only by the hierarchical "/" prefix'
        elif v['type'] == 'net_conflict' and 'unconnected-' in text:
            key = 'schematic no-connect pin, unnumbered pad without net on the PCB'
        elif v['type'] == 'footprint_symbol_mismatch' and re.match(r'(\S+) .*\( \S+:\1 \)', text):
            key = 'footprint library nickname differs, footprint name equal'
        elif v['type'] == 'footprint_symbol_field_mismatch':
            key = 'LCSC/Comment fields only in the schematic'
        elif v['type'] == 'footprint_symbol_mismatch':
            key = 'mounting holes: exclude-from-BOM attribute differs'
        else:
            key = 'other: ' + text + ' ' + ' '.join(i['description'] for i in v['items'])
        cats[key] = cats.get(key, 0) + 1
    erc = TMP/'erc.json'
    cli('sch', 'erc', '--severity-all', '--format', 'json', '-o', erc, SCH)
    e = json.loads(erc.read_text(encoding='utf-8'))
    warnings = {}
    for s in e['sheets']:
        for v in s['violations']:
            k = v['severity']+':'+v['type']
            warnings[k] = warnings.get(k, 0)+1
    return dict(drc_violations=len(d['violations']), unconnected=len(d['unconnected_items']),
                parity_total=len(d['schematic_parity']), parity_categories=cats, erc_all_severities=warnings)


def netlist_compare():
    net = TMP/'net.net'
    cli('sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', net, SCH)
    text = net.read_text(encoding='utf-8')
    sch = {}
    for chunk in re.split(r'\n\t\t\(net\n', text[text.index('(nets'):])[1:]:
        name = re.search(r'\(name "([^"]*)"\)', chunk).group(1).lstrip('/')
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', chunk):
            sch[(ref, pin)] = name
    pcb = {}
    board = PCB.read_text(encoding='utf-8')
    for fm in re.finditer(r'\n\t\(footprint "[^"]+"(.*?)\n\t\)', board, re.S):
        ref = re.search(r'\(property "Reference" "([^"]+)"', fm.group(1)).group(1)
        for pm in re.finditer(r'\(pad "([^"]+)" .*?(?=\n\t\t\(pad |\Z)', fm.group(1), re.S):
            n = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', pm.group(0))
            pcb.setdefault((ref, pm.group(1)), set()).add(n.group(1) if n else '')
    diffs = []
    for k, v in sorted(sch.items()):
        got = pcb.get(k, {None})
        if (v.startswith('unconnected-') and got - {''}) or (not v.startswith('unconnected-') and got != {v}):
            diffs.append(dict(pad='.'.join(k), schematic=v, pcb=sorted(map(str, got))))
    extra = [dict(pad='.'.join(k), schematic=None, pcb=sorted(v)) for k, v in sorted(pcb.items()) if k not in sch and v - {''}]
    single = sorted({n for n in sch.values() if not n.startswith('unconnected-') and list(sch.values()).count(n) == 1})
    return dict(schematic_pins=len(sch), pcb_pads=len(pcb), nets=len(set(sch.values())),
                differences=diffs, pcb_only_nets=extra, single_pin_nets=single)


def run_checks():
    py = str(KICAD/'python.exe')
    out = {}
    for name in CHECKS:
        r = subprocess.run([py, '-X', 'utf8', str(HERE/(name+'.py'))], capture_output=True, text=True, cwd=ROOT,
                           encoding='utf-8', errors='replace')
        out[name] = r.returncode
    return out


def reproduce_model():
    before = {f: sha(HERE/f) for f in MODEL_OUTPUTS}
    steps = [[str(KICAD/'python.exe'), '-X', 'utf8', 'kicad/sim/tmds_channel.py', '--extract'],
             [sys.executable, '-X', 'utf8', 'kicad/sim/tmds_channel.py'],
             [sys.executable, '-X', 'utf8', 'kicad/sim/tmds_sparam.py'],
             [sys.executable, '-X', 'utf8', 'kicad/sim/make_report_figs.py']]
    codes = [subprocess.run(s, cwd=ROOT, capture_output=True).returncode for s in steps]
    after = {f: sha(HERE/f) for f in MODEL_OUTPUTS}
    return dict(exit_codes=codes, identical=[f for f in MODEL_OUTPUTS if before[f] == after[f]],
                changed=[f for f in MODEL_OUTPUTS if before[f] != after[f]])


def verify_manifest():
    sys.path.insert(0, str(HERE))
    from make_manifest import sha as manifest_sha
    m = json.loads((HERE/'manifest_r3.json').read_text(encoding='utf-8'))
    bad = [k for k, v in m['files'].items() if manifest_sha(str(ROOT/k)) != v['sha256']]
    return dict(files=len(m['files']), mismatched=bad)


def render():
    from PIL import Image
    for name, args in RENDERS.items():
        png = ROOT/f'site/img/render_{name}_poc.png'
        cli('pcb', 'render', '-o', png, '-w', 1800, '-h', 1150, '--quality', 'high', '--background', 'transparent', *args, PCB)
        im = Image.open(png).convert('RGBA')
        # Drop the faint shadow/reflection planes so only the board and parts remain.
        alpha = im.getchannel('A').point(lambda a: a if a > 200 else 0)
        im.putalpha(alpha)
        im.crop(alpha.getbbox()).save(png, optimize=True)


def main():
    if '--board' in sys.argv:
        print(json.dumps(board_facts()))
        return
    TMP.mkdir(exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    facts = json.loads(subprocess.check_output([str(KICAD/'python.exe'), '-X', 'utf8', __file__, '--board'], cwd=ROOT))
    result = dict(reviewed_commit=head, pcb_sha256=sha(PCB), kicad=cli('version').stdout.strip(), board=facts,
                  drc_erc=parity(), netlist=netlist_compare(), checks=run_checks(), model=reproduce_model(),
                  manifest=verify_manifest())
    render()
    for p in TMP.iterdir():
        p.unlink()
    TMP.rmdir()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    ok = (not result['drc_erc']['drc_violations'] and not result['drc_erc']['unconnected']
          and not result['netlist']['differences'] and not any(result['checks'].values())
          and not result['model']['changed'] and not result['manifest']['mismatched'])
    print('review', 'ok' if ok else 'FAILED', OUT.name)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
