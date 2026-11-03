#!/usr/bin/env python3
"""Build a Dock LINK or GFX image using already-installed OSS FPGA tools."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [ROOT / p for p in ('link/rtl/link_bringup.v', 'gfx/rtl/gfx_bench.v',
           'platform/dock/tab5_dock_top.v', 'platform/dock/tab5_dock_gfx_top.v',
           'platform/dock/tab5_dock_triangle_top.v', 'gfx/rtl/triangle_tile.v',
           'gfx/rtl/triangle_fragment.v', 'gfx/rtl/triangle_coverage.v', 'gfx/rtl/triangle_depth.v',
           'platform/dock/dock_pll54.v', 'platform/dock/tab5_dock_triangle54_top.v',
           'link/rtl/link_reply_raw.v', 'platform/dock/tab5_dock_triangle54_fast_top.v')]
CST = ROOT / 'constraints/dock/tab5_dock_link_v0.cst'
DEVICE = 'GW2A-LV18PG256C8/I7'
FAMILY = 'GW2A-18'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def yosys_quote(path):
    # Yosys script parsing, not shell parsing. Forward slashes work on Windows.
    return '"' + str(path).replace('\\', '/').replace('"', '\\"') + '"'


def build(variant, yosys, nextpnr, pack, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_dir = output / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12])
    run_dir.mkdir(parents=True)
    manifest_file = output / 'manifest.json'
    manifest = {'variant': variant, 'device': DEVICE, 'family': FAMILY, 'target_mhz': 54 if variant in ('triangle54','triangle54fast') else 27,
                'input_clock_mhz':27,
                'clock_constraints':({'sys_clk_mhz':27,'core_clk_mhz':54,'external_bus_target_mhz':40 if variant=='triangle54fast' else None,'format':'explicit nextpnr SDC create_clock'} if variant in ('triangle54','triangle54fast') else {'sys_clk_mhz':27}),
                'hardware_access': 'none', 'status': 'running', 'run_dir': str(run_dir),
                'sources': {}, 'tools': {}, 'stages': {k: {'status': 'not_run'} for k in ('synthesis', 'pnr', 'pack')},
                'artifacts': {}}
    def save():
        manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    save()
    try:
        for source in [*SOURCES, CST, Path(__file__).resolve(),
                       *([ROOT/('constraints/dock/triangle54fast.sdc' if variant=='triangle54fast' else 'constraints/dock/triangle54.sdc'),ROOT/('constraints/dock/triangle54fast_reference.sdc' if variant=='triangle54fast' else 'constraints/dock/triangle54_reference.sdc')] if variant in ('triangle54','triangle54fast') else [])]:
            manifest['sources'][str(source)] = digest(source)
        executables = {'yosys': str(Path(yosys).resolve()), 'nextpnr': str(Path(nextpnr).resolve()), 'pack': str(Path(pack).resolve())}
        for name, exe in executables.items():
            entry = {'path': exe}
            if Path(exe).is_file():
                entry['sha256'] = digest(Path(exe))
            try:
                result = subprocess.run([exe, '--version'], capture_output=True, text=True, errors='replace', timeout=180)
                entry.update(version=(result.stdout + result.stderr).strip(), version_exit_code=result.returncode)
            except (OSError, subprocess.SubprocessError) as exc:
                entry['version_error'] = str(exc)
            manifest['tools'][name] = entry
        save()
        netlist = run_dir / 'synth.json'
        routed = run_dir / 'output.pnr.json'
        image = run_dir / 'output.fs'
        top = {'gfx':'tab5_dock_gfx_top', 'triangle':'tab5_dock_triangle_top', 'link':'tab5_dock_top','triangle54':'tab5_dock_triangle54_top','triangle54fast':'tab5_dock_triangle54_fast_top'}[variant]
        script = 'read_verilog ' + ' '.join(yosys_quote(p) for p in SOURCES)
        script += '; synth_gowin -family gw2a -top ' + top + ' -json ' + yosys_quote(netlist)
        commands = [
            ('synthesis', [executables['yosys'], '-p', script], netlist),
            ('pnr', [executables['nextpnr'], '--json', netlist.as_posix(), '--write', routed.as_posix(),
                     '--device', DEVICE, '--vopt', 'family='+FAMILY, '--vopt', 'cst='+CST.as_posix(), '--freq', str(manifest['target_mhz']),
                     *(['--sdc',(ROOT/('constraints/dock/triangle54fast.sdc' if variant=='triangle54fast' else 'constraints/dock/triangle54.sdc')).as_posix()] if variant in ('triangle54','triangle54fast') else [])], routed),
            # Key_0/T10 is SI/D2: release SSPI pins to user GPIO after config.
            # Keep JTAG, MSPI and RECONFIG dedicated for programming/recovery.
            ('pack', [executables['pack'], '-d', FAMILY, '--sspi_as_gpio', str(routed), '-o', str(image)], image),
        ]
        for stage, command, artifact in commands:
            entry = manifest['stages'][stage]
            entry.update(status='running', command=command, log=str(run_dir / (stage+'.log')))
            save()
            try:
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
                Path(entry['log']).write_text(result.stdout or '', encoding='utf-8')
                entry['exit_code'] = result.returncode
                if result.returncode != 0:
                    raise RuntimeError(f'{stage} failed with exit code {result.returncode}')
                if not artifact.is_file() or artifact.stat().st_size == 0:
                    raise RuntimeError(f'{stage} did not produce a nonempty {artifact.name}')
                if stage=='synthesis' and variant in ('triangle54','triangle54fast'):
                    synthesized=json.loads(artifact.read_text(encoding='utf-8'))
                    names=synthesized['modules'][top]['netnames']
                    if 'sys_clk' not in names or 'core_clk' not in names:
                        raise RuntimeError('Required explicit oscillator/PLL clock net missing from netlist')
                if stage=='pnr' and variant in ('triangle54','triangle54fast') and 'matched no objects' in (result.stdout or ''):
                    raise RuntimeError('Explicit clock SDC matched no objects; refusing unconstrained image')
                entry['status'] = 'passed'
                manifest['artifacts'][stage] = {'path': str(artifact), 'sha256': digest(artifact)}
                save()
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                entry.update(status='failed', error=str(exc))
                raise
        manifest['status'] = 'passed'
        save()
        return 0
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        manifest.update(status='failed', error=str(exc))
        save()
        print(str(exc), file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('link', 'gfx', 'triangle','triangle54','triangle54fast'))
    parser.add_argument('--yosys', required=True, help='Path to an existing Yosys executable')
    parser.add_argument('--nextpnr', required=True, help='Path to an existing nextpnr-himbaechel executable')
    parser.add_argument('--pack', required=True, help='Path to an existing gowin_pack executable')
    parser.add_argument('--output', type=Path, help='Output directory (default fpga/build/dock-oss-<variant>)')
    args = parser.parse_args()
    return build(args.variant, args.yosys, args.nextpnr, args.pack,
                 args.output or ROOT / 'build' / ('dock-oss-' + args.variant))


if __name__ == '__main__':
    raise SystemExit(main())
