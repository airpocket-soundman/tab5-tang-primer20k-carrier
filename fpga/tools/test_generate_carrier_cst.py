"""Offline checks for the carrier .cst: it must agree with the KiCad pin table and the PCB itself."""
import csv
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_carrier_cst as gen
from kicad_pcb_nets import core_socket_nets

ROOT = gen.ROOT
CST = gen.OUTPUT
SDC = gen.CARRIER_DIR / 'tab5_carrier_link.sdc'
DOCK_CST = ROOT / 'fpga/constraints/dock/tab5_dock_link_v0.cst'
VCCO_PADS = ('164', '166', '170', '174')
# Sipeed pin-map labels whose IO name is stale (ball and bank are right): checked, not trusted.
STALE_LABEL_PINS = {'50', '52', '77', '79'}


def parse_cst(path):
    text = Path(path).read_text(encoding='utf-8')
    locs = dict((m.group(1), m.group(2)) for m in re.finditer(r'^IO_LOC\s+"([^"]+)"\s+(\w+);', text, re.M))
    ports = dict((m.group(1), m.group(2)) for m in re.finditer(r'^IO_PORT\s+"([^"]+)"\s+([^;]*);', text, re.M))
    return locs, ports


class CarrierCstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assignment = gen.load_assignment()
        with open(gen.PINMAP, encoding='utf-8') as f:
            cls.pinmap_rows = {r['sodimm_pin']: r for r in csv.DictReader(f)}
        cls.balls = gen.load_ball_table()['balls']
        cls.locs, cls.ports = parse_cst(CST)

    def test_committed_cst_is_current(self):
        self.assertEqual(CST.read_text(encoding='utf-8'), gen.render(gen.resolve()))

    def test_every_in_scope_signal_matches_kicad_table_and_pinmap(self):
        # Independent re-derivation from the raw CSV rows, not through gen.resolve().
        expected = {}
        for signal, sodimm in self.assignment.items():
            if re.match(r'^(HDMI_|F_HPD$|F_HSCL$|F_HSDA$)', signal):
                continue
            expected[gen.port_name(signal)] = self.pinmap_rows[sodimm]['bank/io/ball_label'].split('/')[2]
        for port, ball in expected.items():
            self.assertEqual(self.locs.get(port), ball, port)
        self.assertEqual(set(self.locs) - {'sys_clk'}, set(expected))

    def test_kicad_pin_table_equals_pcb_pad_nets(self):
        nets = core_socket_nets(ROOT / 'kicad/tab5-fpga-carrier.kicad_pcb')
        diffs = {p: (s, nets.get(p)) for s, p in self.assignment.items() if nets.get(p) != s}
        self.assertEqual(diffs, {})

    def test_balls_and_ports_are_unique(self):
        balls = list(self.locs.values())
        self.assertEqual(len(balls), len(set(balls)))
        self.assertTrue(all(b in self.balls for b in balls if b != 'H11'))

    def test_hdmi_and_ddr_signals_are_excluded(self):
        for name in self.locs:
            self.assertFalse(re.search(r'hdmi|tmds|hpd|hscl|hsda|ddr', name, re.I), name)
        text = CST.read_text(encoding='utf-8')
        self.assertNotRegex(text, r'IO_LOC\s+"[^"]*(hdmi|ddr)', )

    def test_dock_port_names_are_reused(self):
        dock_locs, _ = parse_cst(DOCK_CST)
        carrier = set(self.locs)
        for name in ['bus_clk', 'dir', 'ready'] + [f'data[{i}]' for i in range(8)] + [f'aux[{i}]' for i in range(4)] + [f'led[{i}]' for i in range(4)]:
            self.assertIn(name, dock_locs, name)
            self.assertIn(name, carrier, name)

    def test_carrier_is_not_the_dock_bench(self):
        dock_locs, _ = parse_cst(DOCK_CST)
        self.assertEqual(self.locs['bus_clk'], 'K14')       # GCLKT_1 on the carrier
        self.assertEqual(dock_locs['bus_clk'], 'T7')        # GCLKT_3 on the Dock bench
        self.assertEqual(self.balls['K14']['functions'], ['GCLKT_1'])
        for port in ('data[0]', 'data[7]', 'dir', 'ready'):
            self.assertNotEqual(self.locs[port], dock_locs[port], port)

    def test_pinmap_labels_agree_with_chip_database(self):
        stale = set()
        with open(gen.ASSIGNMENT, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            label = self.pinmap_rows[row['sodimm_pin']]['bank/io/ball_label'].split('/')
            bank, io, ball = int(label[0]), label[1], label[2]
            self.assertEqual(self.balls[ball]['bank'], bank, row['sodimm_pin'])   # bank labels are right
            if self.balls[ball]['io'] != io:
                stale.add(row['sodimm_pin'])
        self.assertEqual(stale, STALE_LABEL_PINS)

    def test_io_type_only_where_bank_voltage_is_recorded(self):
        for port, attrs in self.ports.items():
            if port == 'sys_clk':
                continue
            self.assertIn('IO_TYPE=LVCMOS33', attrs)
        for row in gen.resolve():
            self.assertIn(row['bank'], gen.BANK_VCCO, f'bank {row["bank"]} has no recorded VCCO source')

    def test_bank_vcco_pads_are_open_on_the_pcb(self):
        # If these pads get connected, BANK_VCCO must be re-derived (this test then fails on purpose).
        nets = core_socket_nets(ROOT / 'kicad/tab5-fpga-carrier.kicad_pcb')
        for pad in VCCO_PADS:
            self.assertIsNone(nets[pad], f'SODIMM {pad} is now connected: update BANK_VCCO in generate_carrier_cst.py')

    def test_require_verified_refuses_while_unverified(self):
        done = subprocess.run([sys.executable, str(Path(gen.__file__)), '--require-verified', '--output', str(CST)],
                              capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('REFUSED', done.stderr)

    def test_sdc_has_no_active_guessed_constraints(self):
        active = [l for l in SDC.read_text(encoding='utf-8').splitlines() if l.strip() and not l.lstrip().startswith('#')]
        self.assertEqual(len(active), 1)
        self.assertIn('create_clock -name sys_clk -period 37.037', active[0])


if __name__ == '__main__':
    unittest.main()
