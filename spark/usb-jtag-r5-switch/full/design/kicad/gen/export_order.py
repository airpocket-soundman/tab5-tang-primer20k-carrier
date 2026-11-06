"""r5s: export Gerber / drill / KiCad position / netlist-check files for a PoC PCB order (KiCad python).

Modeled on spark/design/kicad/gen/export_poc_package.py (the r4 PoC flow). Writes only to
spark/usb-jtag-r5-switch/order/. It re-runs ERC and DRC first and stops on any error.
This produces ORDER CANDIDATE data only: it is not a release. See order/README.md.
Run:  "C:/Program Files/KiCad/10.0/bin/python.exe" export_order.py
"""
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path
K = Path(__file__).resolve().parents[1]
ROOT = K.parents[2]                      # spark/usb-jtag-r5-switch
OUT = ROOT / 'order'
PCB = K / 'tab5-fpga-carrier-r5s.kicad_pcb'
SCH = K / 'tab5-fpga-carrier-r5s.kicad_sch'
CLI = Path(sys.executable).parent / 'kicad-cli.exe'

def run(*args):
    subprocess.run([str(CLI), *map(str, args)], check=True)

def main():
    OUT.mkdir(exist_ok=True)
    g = OUT / 'gerbers'
    g.mkdir(exist_ok=True)
    # 1. checks (stop on error)
    run('sch', 'erc', '--severity-all', '--format', 'json', '-o', K / 'sim/erc.json', SCH)
    run('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', K / 'sim/netlist.xml', SCH)
    run('pcb', 'drc', '--severity-all', '--format', 'json', '--schematic-parity', '-o', K / 'sim/drc.json', PCB)
    erc = json.loads((K / 'sim/erc.json').read_text(encoding='utf8'))
    errors = [x for s in erc['sheets'] for x in s['violations'] if x['severity'] == 'error']
    drc = json.loads((K / 'sim/drc.json').read_text(encoding='utf8'))
    assert not errors, ('ERC errors', len(errors))
    assert not drc['violations'] and not drc['unconnected_items'], ('DRC', len(drc['violations']), len(drc['unconnected_items']))
    # 2. fabrication files (same options as the r4 PoC export; origin = board lower-left (2,79))
    run('pcb', 'export', 'gerbers', '-l',
        'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
        '--subtract-soldermask', '--use-drill-file-origin', '-o', str(g) + '/', PCB)
    run('pcb', 'export', 'drill', '--drill-origin', 'plot', '--excellon-separate-th', '--generate-report', '-o', str(g) + '/', PCB)
    run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--exclude-dnp', '--use-drill-file-origin',
        '-o', OUT / 'kicad-position.csv', PCB)
    run('pcb', 'export', 'ipcd356', '-o', OUT / 'connectivity.d356', PCB)
    with zipfile.ZipFile(OUT / 'gerbers.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(g.iterdir()):
            z.write(p, p.name)
    info = {
        'source_pcb_sha256': hashlib.sha256(PCB.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        'erc_errors': 0, 'pcb_drc_violations': 0, 'pcb_unconnected': 0,
        'origin_mm': [2, 79], 'board_mm': [125, 78], 'layers': 4,
        'gerber_files': sorted(p.name for p in g.iterdir()),
    }
    (OUT / 'gerber-export.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in info.items() if k != 'gerber_files'}, indent=1))

if __name__ == '__main__':
    main()
