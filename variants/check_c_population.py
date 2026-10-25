"""Check the C population policy against the preserved circuit, not a board release.

This deliberately does not claim that replacement footprints, routing, regulator
thermal performance, firmware or Core DDR3 operation have been validated.
"""
import copy
import csv
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'variants/lite-c-dnp'
PD = {'J2', 'U1', 'C2', 'R1', 'R2', 'R3', 'R4', 'R5', 'D2'}
HDMI = {'J5', 'U4', 'U5', 'U6', 'Q1', 'Q2', 'F2'} | {
    f'C{i}' for i in range(12, 20)} | {f'R{i}' for i in range(28, 42)}
UNFIT = PD | HDMI


def load_base():
    spec = importlib.util.spec_from_file_location('preserved_design', ROOT / 'kicad/gen/design.py')
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    return model, model.build()


def population(comps):
    result = copy.deepcopy(comps)
    for c in result:
        if c.ref in UNFIT:
            c.dnp = True
    return result


def check(model, comps):
    parts = {c.ref: c for c in comps}
    rows = []

    def require(name, ok):
        rows.append({'name': name, 'ok': bool(ok)})

    def fitted(ref, pins=None):
        c = parts.get(ref)
        return c is not None and not c.dnp and (pins is None or all(c.pins.get(k) == v for k, v in pins.items()))

    require('all_PD_and_HDMI_lands_retained', UNFIT <= parts.keys())
    require('all_PD_and_HDMI_parts_DNP', all(parts[r].dnp for r in UNFIT if r in parts))
    require('HDMI_groups_have_no_fitted_parts', all(c.dnp for c in comps if c.block in ('hdmi', 'tmdsc')))
    require('PD_group_has_no_fitted_parts', all(c.dnp for c in comps if c.block == 'pd'))
    require('barrel_is_12V_input', fitted('J1', {'1': 'DC_RAW', '2': 'GND'}))
    require('barrel_fuse_and_forward_diode', fitted('F1', {'1': 'DC_RAW', '2': 'DC_IN'}) and fitted('D1', {'1': 'VIN', '2': 'DC_IN'}))
    require('TVS_and_bulk_capacitor', fitted('D3', {'1': 'VIN', '2': 'GND'}) and fitted('C1', {'1': 'VIN', '2': 'GND'}))
    require('buck_VIN_PH_inductor_path', fitted('U2', {'7': 'VIN', '8': 'BUCK_PH', '6': 'GND'}) and fitted('L1', {'1': 'BUCK_PH', '2': '+5V'}))
    require('buck_catch_boot_and_output_capacitor', fitted('D4', {'1': 'BUCK_PH', '2': 'GND'}) and fitted('C3', {'1': 'BUCK_BOOT', '2': 'BUCK_PH'}) and fitted('C7', {'1': '+5V', '2': 'GND'}))
    require('buck_feedback_and_enable_parts', all(fitted(r) for r in ('R6', 'R7', 'R8', 'R9')))
    require('LDO_5V_to_3V3', fitted('U3', {'1': 'GND', '2': '+3V3', '3': '+5V'}) and fitted('C10') and fitted('C11'))
    require('socket_fitted_and_Core_5V_pins', fitted('J4') and all(parts['J4'].pins.get(str(p)) == '+5V' for p in (4, 5, 6, 7)))
    require('Core_ground_pins', all(parts['J4'].pins.get(str(p)) == 'GND' for p in model.CORE_GND))
    require('M5Bus_HVIN_and_output_rails', fitted('J3') and all(parts['J3'].pins.get(str(p)) == 'VIN' for p in (25, 27, 29)) and all(parts['J3'].pins.get(str(p)) is None for p in (28, 30)))
    require('supervisors_and_arm', fitted('U9', {'3': 'TAB_3V3', '2': 'TAB_PGOOD'}) and fitted('U10', {'3': '+5V', '2': 'CORE_PGOOD'}) and all(fitted(r) for r in ('Q3', 'Q4', 'JP1', 'R46', 'R47', 'R48')))
    for sig in model.SERIES:
        switches = [c for c in comps if c.ref in ('U7', 'U8') and not c.dnp and 'M_' + sig in c.pins.values() and 'ISO_' + sig in c.pins.values() and c.pins.get('20') == '+3V3' and c.pins.get('19') == 'BUS_OE_N']
        resistors = [c for c in comps if c.ref.startswith('R') and not c.dnp and c.value == '33R' and set(c.pins.values()) == {'ISO_' + sig, 'F_' + sig}]
        require('parallel_' + sig, len(switches) == 1 and len(resistors) == 1 and parts['J4'].pins.get(str(model.CORE_PINS['F_' + sig])) == 'F_' + sig and 'M_' + sig in parts['J3'].pins.values())
    return rows


def main():
    model, original = load_base()
    selected = population(original)
    rows = check(model, selected)
    assert all(r['ok'] for r in rows), rows
    fault_results = []
    for ref in ('F1', 'D1', 'L1', 'U3', 'J4', 'U7', 'U10'):
        faulty = copy.deepcopy(selected)
        next(c for c in faulty if c.ref == ref).dnp = True
        caught = not all(r['ok'] for r in check(model, faulty))
        assert caught, ref
        fault_results.append({'fault': ref + ' accidentally DNP', 'caught': caught})
    faulty = copy.deepcopy(selected)
    next(c for c in faulty if c.ref == 'J3').pins['30'] = '+5V'
    assert not all(r['ok'] for r in check(model, faulty))
    fault_results.append({'fault': 'VBAT_OUT incorrectly tied to Core 5V', 'caught': True})
    policy = {'PD_DNP': sorted(PD), 'HDMI_DNP': sorted(HDMI), 'socket_must_be_PCBA': 'J4', 'manual_required_for_barrel_power': 'J1', 'core_module': 'user supplied; not in PCBA BOM'}
    (OUT / 'population-policy.json').write_text(json.dumps(policy, indent=2) + '\n', encoding='utf-8')
    with (OUT / 'population-policy.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Reference', 'Action', 'Scope'])
        for ref in sorted(UNFIT):
            w.writerow([ref, 'DNP - retain circuit and footprint', 'USB PD' if ref in PD else 'HDMI'])
    report = {'status': 'PASS: DNP policy circuit-topology check only; NOT fabrication release', 'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'checked_model': 'preserved circuit plus C population policy; new component and PCB validation pending', 'checks': rows, 'fault_detection': fault_results, 'open_gates': ['replacement socket footprint and PCBA availability', 'Basic resistor network and new LDO validation', 'replacement inductor footprint and power margins', 'new board DRC and BOM/CPL reconciliation', 'physical Tab5 link and Core DDR3 bringup']}
    (OUT / 'population-topology-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'policy_checks': len(rows), 'passed': all(r['ok'] for r in rows), 'injected_faults_caught': len(fault_results), 'scope': report['checked_model']}))


if __name__ == '__main__':
    main()
