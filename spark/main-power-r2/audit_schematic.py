"""Check exported circuit connectivity. Run once per variant after CLI netlist export."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

variant = sys.argv[1]
assert variant in ('full', 'lite-a')
root = Path(__file__).resolve().parent / variant / 'kicad'
sys.path.insert(0, str(root / 'gen'))
import design

nets = {}
for net in ET.parse(root / 'sim/netlist.xml').findall('.//nets/net'):
    name = net.attrib['name'].removeprefix('/')
    for node in net.findall('node'):
        nets[(node.attrib['ref'], node.attrib['pin'])] = name

errors = []
checked = 0
components = design.build()
for c in components:
    for pin, expected in c.pins.items():
        actual = nets.get((c.ref, pin))
        if expected is not None:
            checked += 1
            if actual != expected:
                errors.append([c.ref, pin, expected, actual])
        elif actual and not actual.startswith('unconnected-'):
            errors.append([c.ref, pin, 'NC', actual])

report = {
    'ok': not errors,
    'scope': 'R2 candidate schematic connectivity only; no PCB or transient validation',
    'variant': variant,
    'components': len(components),
    'connected_pins_checked': checked,
    'errors': errors,
    'fabrication_released': False,
}
(root / 'sim/schematic-model-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['ok'] else 1)
