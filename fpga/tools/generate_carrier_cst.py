"""Generate the carrier-board .cst from kicad/core_pin_assignment.csv (offline, no programming).

Chain: carrier signal -> SODIMM pin (kicad/core_pin_assignment.csv, equal to the PCB pad nets)
       -> FPGA ball (docs/reference/tang-primer-20k/core_sodimm_pinmap.csv, 3rd field)
       -> IO name and bank (constraints/carrier/gw2a18_pg256_ball_table.json, from Apicula).
The bank/IO text in the Sipeed pin map is NOT used: four of its labels are stale.

Port names follow the Dock bench (bus_clk, dir, ready, data[n], aux[n], led[n]).
HDMI (TMDS, HPD/HSCL/HSDA) and DDR3 signals are excluded by design. Anything that cannot be
derived from the repository (bank VCCO, LED polarity, ...) is emitted as a TODO, never guessed.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = ROOT / 'kicad/core_pin_assignment.csv'
PINMAP = ROOT / 'docs/reference/tang-primer-20k/core_sodimm_pinmap.csv'
CARRIER_DIR = ROOT / 'fpga/constraints/carrier'
BALL_TABLE = CARRIER_DIR / 'gw2a18_pg256_ball_table.json'
OUTPUT = CARRIER_DIR / 'tab5_carrier_link.cst'
PACKAGE = 'GW2A-LV18PG256C8/I7'

EXCLUDED = re.compile(r'^(HDMI_|F_HPD$|F_HSCL$|F_HSDA$)')

# Carrier signal -> port name (same names as fpga/constraints/dock/tab5_dock_link_v0.cst where one exists).
FIXED = {'F_CLK': 'bus_clk', 'F_DIR': 'dir', 'F_RDY': 'ready', 'F_BTN0': 'btn[0]',
         'F_EXT35': 'ext35', 'F_EXT37': 'ext37', 'F_EXT38': 'ext38'}
INDEXED = (('F_D', 'data'), ('F_AUX', 'aux'), ('F_LED', 'led'), ('P1_', 'pmod1'), ('P2_', 'pmod2'), ('GPIO', 'gpio'))

# Attributes copied from the Dock bench file. They are bench values, not carrier-verified.
DOCK_ATTRS = {'bus_clk': 'PULL_MODE=DOWN', 'dir': 'PULL_MODE=DOWN', 'ready': 'PULL_MODE=DOWN DRIVE=8'}
DOCK_DATA_ATTRS = 'PULL_MODE=NONE DRIVE=8'
# Bank VCCO on the carrier. SODIMM 164/166 (VCCO0&1) and 170/174 (VCCO7) are unconnected on the PCB,
# so banks 0/1/7 are 3.3 V only if the Core resistors R5 / R9 are fitted. Banks 2/3 are fixed 3.3 V on the Core.
BANK_VCCO = {
    0: ('3.3', 'unverified: needs Core R5 -> +3V3 (SODIMM 164/166 open on the carrier)'),
    1: ('3.3', 'unverified: needs Core R5 -> +3V3 (SODIMM 164/166 open on the carrier)'),
    7: ('3.3', 'unverified: needs Core R9 -> +3V3 (SODIMM 170/174 open on the carrier)'),
}
CORE_RESOURCES = (
    '// Core resource, identical on the Dock bench (Sipeed dk_video.cst): 27 MHz oscillator.\n'
    'IO_LOC  "sys_clk" H11;\n'
    'IO_PORT "sys_clk" IO_TYPE=LVCMOS33 PULL_MODE=UP;\n'
)


def port_name(signal):
    if signal in FIXED:
        return FIXED[signal]
    for prefix, name in INDEXED:
        if signal.startswith(prefix) and signal[len(prefix):].isdigit():
            return f'{name}[{int(signal[len(prefix):])}]'
    raise ValueError(f'no port name rule for {signal}')


def load_assignment(path=ASSIGNMENT):
    with open(path, encoding='utf-8') as f:
        return {r['signal']: r['sodimm_pin'] for r in csv.DictReader(f)}


def load_pinmap(path=PINMAP):
    """sodimm pin -> FPGA ball (3rd field of the label; bank and IO text of the label are ignored)."""
    result = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            parts = row['bank/io/ball_label'].split('/')
            result[row['sodimm_pin']] = parts[2] if len(parts) == 3 else None
    return result


def load_ball_table(path=BALL_TABLE):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def refresh_ball_table(path=BALL_TABLE):
    """Rebuild the ball table from the Apicula chip database (needs apycula; not used by tests)."""
    import os
    from importlib.metadata import version
    import apycula
    from apycula import chipdb
    db_path = os.path.join(os.path.dirname(apycula.__file__), 'GW2A-18C.msgpack.xz')
    db = chipdb.load_chipdb(db_path)
    package = db.packages[PACKAGE][0]
    table = {ball: {'io': io, 'bank': db.pin_bank[io], 'functions': funcs}
             for ball, (io, funcs) in db.pinout['GW2A-18C'][package].items()}
    out = {'source': 'Apicula chipdb', 'apycula_version': version('apycula'),
           'chipdb_sha256': hashlib.sha256(Path(db_path).read_bytes()).hexdigest(),
           'package': PACKAGE, 'balls': dict(sorted(table.items()))}
    Path(path).write_text(json.dumps(out, indent=1, sort_keys=False) + '\n', encoding='utf-8')
    return out


def resolve(assignment=None, pinmap=None, balls=None):
    """Return a list of dicts (port, signal, sodimm, ball, io, bank, functions) for the in-scope signals."""
    assignment = assignment or load_assignment()
    pinmap = pinmap or load_pinmap()
    balls = balls or load_ball_table()['balls']
    rows = []
    for signal, sodimm in assignment.items():
        if EXCLUDED.match(signal):
            continue
        ball = pinmap.get(sodimm)
        if not ball or ball not in balls:
            raise ValueError(f'{signal}: SODIMM {sodimm} has no resolvable FPGA ball')
        b = balls[ball]
        rows.append(dict(port=port_name(signal), signal=signal, sodimm=sodimm, ball=ball,
                         io=b['io'], bank=b['bank'], functions=b['functions']))
    return sorted(rows, key=lambda r: (r['port'].split('[')[0], int(re.findall(r'\d+', r['port'])[-1]) if re.findall(r'\d+', r['port']) else 0))


def io_attrs(row):
    port = row['port']
    base = port.split('[')[0]
    if base in DOCK_ATTRS:
        return DOCK_ATTRS[base], 'attributes carried over from the Dock bench'
    if base == 'data':
        return DOCK_DATA_ATTRS, 'attributes carried over from the Dock bench'
    return None, 'TODO: pull/drive not decided for the carrier'


def render(rows):
    lines = [
        '// Tab5 M5-Bus <-> Tang Primer 20K Core on the CARRIER BOARD (DRAFT, generated; do not edit).',
        '// Generator: fpga/tools/generate_carrier_cst.py  Inputs: kicad/core_pin_assignment.csv,',
        '//   docs/reference/tang-primer-20k/core_sodimm_pinmap.csv, constraints/carrier/gw2a18_pg256_ball_table.json',
        f'// Package: {PACKAGE}. HDMI (TMDS, HPD/HSCL/HSDA) and DDR3 signals are NOT in this file.',
        '// Not for the Dock jumper bench: use constraints/dock/tab5_dock_link_v0.cst there (different balls and banks).',
        '// STATUS: no ball has been checked on a built board. See docs/キャリア制約_cst_sdc生成.md for open items.',
        '//',
        '// Bank VCCO (carrier has SODIMM 164/166/170/174 unconnected):',
    ]
    used = sorted({r['bank'] for r in rows})
    for bank in used:
        text = BANK_VCCO.get(bank)
        lines.append(f'//   bank {bank}: ' + (f'{text[0]} V, {text[1]}' if text else 'TODO: voltage source not established'))
    lines += ['', CORE_RESOURCES.rstrip('\n'),
              '// TODO(reset_n): Dock Key_0 (T10) does not exist on the carrier; F_BTN0 (btn[0]) is the only button.',
              '// TODO(arm_sw): Dock DIP SW0 (C7) does not exist on the carrier; bus ARM is hardware (JP1), no FPGA pin.', '']
    for row in rows:
        port, bank = row['port'], row['bank']
        attrs, attr_note = io_attrs(row)
        vcco = BANK_VCCO.get(bank)
        io_type = 'LVCMOS33' if vcco and vcco[0] == '3.3' else None
        funcs = ','.join(row['functions'])
        lines.append(f'// {row["signal"]} SODIMM {row["sodimm"]} {row["io"]} bank{bank}' + (f' [{funcs}]' if funcs else '') + f'; {attr_note}')
        lines.append(f'IO_LOC  "{port}" {row["ball"]};')
        if io_type:
            lines.append(f'IO_PORT "{port}" IO_TYPE={io_type}' + (f' {attrs}' if attrs else '') + ';')
        else:
            lines.append(f'// TODO: IO_PORT "{port}" (bank {bank} voltage unknown)')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true', help='fail if the committed output differs')
    parser.add_argument('--refresh-ball-table', action='store_true', help='rebuild the ball table with apycula')
    parser.add_argument('--require-verified', action='store_true', help='refuse while any bank VCCO is unverified')
    args = parser.parse_args(argv)
    if args.refresh_ball_table:
        refresh_ball_table()
    if args.require_verified and any('unverified' in v[1] for v in BANK_VCCO.values()):
        sys.exit('REFUSED: bank VCCO of banks 0/1/7 is unverified (Core R5/R9 population, SODIMM 164/166/170/174 open)')
    text = render(resolve())
    if args.check:
        if args.output.read_text(encoding='utf-8') != text:
            sys.exit(f'{args.output} is out of date; run the generator')
        return 0
    args.output.write_text(text, encoding='utf-8')
    print(f'wrote {args.output} ({text.count("IO_LOC")} ports)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
