"""Inspect or program the Tang Primer 20K Dock with openFPGALoader.

Program mode loads SRAM only. It never writes flash. No loader is invoked in
--dry-run mode. Image and source hashes are checked before programming.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOADER = ROOT/'build/windows-tools/oss-cad-suite/bin/openFPGALoader.exe'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(path, variant):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('status') != 'passed' or manifest.get('variant') != variant:
        raise ValueError('manifest status or variant mismatch')
    if any(manifest.get('stages', {}).get(stage, {}).get('status') != 'passed'
           for stage in ('synthesis', 'pnr', 'pack')):
        raise ValueError('synthesis, place-and-route, and pack must have passed')
    sources = manifest.get('sources')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('manifest has no source hashes')
    for name, expected in sources.items():
        if digest(Path(name)) != expected:
            raise ValueError(f'source hash mismatch: {name}')
    artifact = manifest['artifacts']['pack']
    image = Path(artifact['path'])
    if image.suffix.lower() != '.fs' or digest(image) != artifact['sha256']:
        raise ValueError('packed .fs image hash mismatch')
    return manifest, image


def run(argv=None, root=ROOT, invoke=subprocess.run):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path, default=DEFAULT_LOADER)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('doctor', help='Query loader version, help, and supported boards')
    detect = sub.add_parser('detect', help='Detect FPGA using the Tang Primer 20K board profile')
    detect.add_argument('--serial', help='USB adapter serial number')
    program = sub.add_parser('program', help='Load validated bitstream into SRAM')
    program.add_argument('--variant', choices=['link', 'gfx'], required=True)
    program.add_argument('--dry-run', action='store_true')
    program.add_argument('--serial', help='USB adapter serial number')
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    logdir = root/'build/programming'
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir/(now.strftime('%Y%m%dT%H%M%S.%fZ')+'-'+uuid.uuid4().hex[:8]+'.json')
    record = {'started_utc':now.isoformat(), 'action':args.action, 'loader':str(args.loader),
              'board':'tangprimer20k', 'status':'started', 'commands':[]}
    def save(): log.write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    try:
        loader = str(args.loader)
        if args.loader.is_file():
            record['loader_sha256'] = digest(args.loader)
        elif not (args.action == 'program' and args.dry_run):
            raise FileNotFoundError(f'loader not found: {args.loader}')
        select = ['--usb-serial-num', args.serial] if getattr(args, 'serial', None) else []
        if args.action == 'program':
            manifest_path = root/'build'/f'dock-oss-{args.variant}'/'manifest.json'
            manifest, image = validate_manifest(manifest_path, args.variant)
            record.update(variant=args.variant, manifest=str(manifest_path), manifest_sha256=digest(manifest_path),
                          sources=manifest['sources'], image=str(image), image_sha256=digest(image),
                          synthesis_run_dir=manifest.get('run_dir'), mode='sram', dry_run=args.dry_run)
            commands = [[loader, '-b', 'tangprimer20k', *select, '-m', str(image)]]
        elif args.action == 'detect':
            commands = [[loader, '-b', 'tangprimer20k', *select, '--detect']]
        else:
            commands = [[loader, '--version'], [loader, '--help'], [loader, '--list-boards']]
        if args.action == 'program' and args.dry_run:
            record['commands'] = [{'argv':commands[0], 'result':'not_invoked'}]
            record['status'] = 'dry_run'
            save()
            print(json.dumps({'status':'dry_run', 'command':commands[0], 'log':str(log)}, ensure_ascii=False))
            return 0
        for command in commands:
            try:
                result = invoke(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=False, timeout=120)
            except subprocess.TimeoutExpired as exc:
                def decode(value):
                    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
                record['commands'].append({'argv':command, 'result':'timeout', 'timeout_seconds':120,
                                           'stdout':decode(exc.stdout), 'stderr':decode(exc.stderr)})
                raise
            entry = {'argv':command, 'returncode':result.returncode, 'stdout':result.stdout, 'stderr':result.stderr}
            record['commands'].append(entry)
            save()
            if result.stdout: print(result.stdout, end='')
            if result.stderr: print(result.stderr, end='', file=sys.stderr)
            if result.returncode:
                record['status'] = 'failed'
                record['error'] = f'loader exit code {result.returncode}'
                save()
                return result.returncode if result.returncode > 0 else 1
        record['status'] = 'passed'
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        record['status'] = 'failed'
        record['error'] = str(exc)
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    finally:
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    sys.exit(run())
