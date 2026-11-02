"""Compare the recorded synthesized GFX netlist with the PC oracle; no hardware."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reference.gfx_bench import GfxBench
from tools.dock_gfx_demo import exercise


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_defects(text):
    # Detect the specific incomplete models shipped by Yosys. This is not a
    # certification of any other model; caller must provide a trusted one.
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    def body(name):
        match = re.search(r'\bmodule\s+' + name + r'\b(.*?)\bendmodule\b', text, re.S)
        return match.group(1) if match else None
    defects = []
    ram = body('SPX9')
    if ram is None or not re.search(r'\b(always|initial|assign|memory|function|task)\b', ram):
        defects.append('SPX9 missing or empty blackbox; no RAM behavior')
    io = body('IOBUF')
    if io is None or (re.search(r'\bassign\s+I\s*=\s*IO\s*;', io) and not re.search(r'\bassign\s+O\s*=', io)):
        defects.append('IOBUF missing or drives input I from IO without driving O')
    return defects


def overlay_models(base, overlay):
    """Replace only bounded bench primitives; never modify installed libraries."""
    names = ['SPX9', 'IOBUF']
    if re.search(r'\bmodule\s+ALU\b', overlay):
        names.append('ALU')
    for name in names:
        pattern = r'\bmodule\s+' + name + r'\b.*?\bendmodule\b'
        replacements = list(re.finditer(pattern, overlay, re.S))
        originals = list(re.finditer(pattern, base, re.S))
        if len(replacements) != 1 or len(originals) != 1:
            raise ValueError(f'expected exactly one {name} in base and overlay')
        base = re.sub(pattern, lambda _: replacements[0].group(), base, flags=re.S)
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cells-sim', type=Path, default=ROOT/'build/oss-env/Lib/site-packages/yowasp_yosys/share/gowin/cells_sim.v', help='Trusted Gowin behavioral model')
    parser.add_argument('--model-overlay', type=Path, help='Explicit test-only SPX9/IOBUF overlay; see simulation/README.md')
    parser.add_argument('--yosys', type=Path, default=ROOT/'build/oss-env/Scripts/yowasp-yosys.exe')
    parser.add_argument('--iverilog', type=Path, default=ROOT/'build/iverilog/wrappers/iverilog')
    parser.add_argument('--vvp', type=Path, default=ROOT/'build/iverilog/wrappers/vvp')
    parser.add_argument('--wsl', default='Ubuntu-24.04', help='WSL distribution for Icarus')
    args = parser.parse_args()
    out = ROOT/'build/synth-bench'
    out.mkdir(parents=True, exist_ok=True)
    status_path = out/'status.json'
    report = {'status':'not_run', 'hardware_access':'none', 'model':str(args.cells_sim), 'sources':{},
              'test_sources':{str(p):sha(p) for p in (Path(__file__), ROOT/'gfx/tests/tb_synth_bench.v',
                              ROOT/'reference/gfx_bench.py', ROOT/'tools/dock_gfx_demo.py')}}
    def save(): status_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    try:
        manifest = json.loads((ROOT/'build/dock-oss-gfx/manifest.json').read_text(encoding='utf-8'))
        netlist = Path(manifest['artifacts']['synthesis']['path'])
        report.update(synthesis_run_dir=manifest['run_dir'], netlist=str(netlist), netlist_sha256=sha(netlist))
        if report['netlist_sha256'] != manifest['artifacts']['synthesis']['sha256']:
            raise ValueError('synthesis artifact hash mismatch')
        for name, digest in manifest['sources'].items():
            actual = sha(Path(name))
            report['sources'][name] = actual
            if actual != digest:
                raise ValueError(f'synthesis source hash mismatch: {name}')
        report['model_sha256'] = sha(args.cells_sim)
        model_path = args.cells_sim
        model_text = model_path.read_text(encoding='utf-8')
        if args.model_overlay:
            report.update(model_overlay=str(args.model_overlay), model_overlay_sha256=sha(args.model_overlay),
                          scope='test-only functional primitive overlay; no vendor or physical timing validation')
            model_text = overlay_models(model_text, args.model_overlay.read_text(encoding='utf-8'))
            model_path = out/'combined_cells_sim.v'
            model_path.write_text(model_text, encoding='utf-8')
            report['combined_model_sha256'] = sha(model_path)
        defects = model_defects(model_text)
        if defects:
            report.update(status='blocked', reason='model_unavailable', details=defects)
            save()
            print('BLOCKED: ' + '; '.join(defects))
            return 2
        model = GfxBench()
        vectors = []
        def exchange(frame):
            reply = model.exchange(frame)
            vectors.append((frame, reply))
            return reply
        exercise(exchange)
        (out/'vectors.txt').write_text(''.join(' '.join(f'{b:02x}' for b in q+r)+'\n' for q,r in vectors), encoding='ascii')
        converted = out/'synth.v'
        subprocess.run([str(args.yosys), '-Q', '-T', '-p', f'read_json "{netlist.as_posix()}"; write_verilog -noattr "{converted.as_posix()}"'], check=True)
        def linux(path):
            p = path.as_posix()
            if p.startswith('/'):
                return p
            return subprocess.check_output(['wsl', '-d', args.wsl, '--', 'wslpath', '-a', p], text=True).strip()
        exe = out/'bench.vvp'
        subprocess.run(['wsl', '-d', args.wsl, '--', linux(args.iverilog), '-g2012', '-s', 'tb_synth_bench', '-o', linux(exe), linux(model_path), linux(converted), linux(ROOT/'gfx/tests/tb_synth_bench.v')], check=True)
        subprocess.run(['wsl', '-d', args.wsl, '--', linux(args.vvp), linux(exe), '+vectors='+linux(out/'vectors.txt')], check=True, timeout=180)
        report.update(status='passed', transactions=len(vectors), pixels=1024)
        save()
        print(f'PASS synthesized netlist: {len(vectors)} oracle transactions, 1024 pixels; no hardware')
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report.update(status='failed', reason=str(exc))
        save()
        print(f'FAILED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
