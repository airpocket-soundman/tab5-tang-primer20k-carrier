"""Local Windows Dock development commands. No global PATH changes."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('setup', help='Install pinned tools into ignored fpga/build')
    commands.add_parser('doctor', help='Check local build tools and programmer')
    commands.add_parser('test', help='Run host tests for build and programming tools')
    build = commands.add_parser('build')
    build.add_argument('variant', choices=['link', 'gfx', 'triangle'])
    detect = commands.add_parser('detect')
    detect.add_argument('--serial')
    program = commands.add_parser('program', help='Load a validated build into FPGA SRAM')
    program.add_argument('variant', choices=['link', 'gfx', 'triangle'])
    program.add_argument('--dry-run', action='store_true')
    program.add_argument('--serial')
    args = parser.parse_args()
    tools = ROOT/'build/oss-env/Scripts'
    build_tools = {name:tools/exe for name, exe in (
        ('yosys', 'yowasp-yosys.exe'), ('nextpnr', 'yowasp-nextpnr-himbaechel-gowin.exe'),
        ('pack', 'gowin_pack.exe'))}
    loader = ROOT/'build/windows-tools/oss-cad-suite/bin/openFPGALoader.exe'
    def run(command):
        subprocess.run([str(x) for x in command], check=True, cwd=ROOT.parent)
    try:
        if args.action == 'setup':
            run([sys.executable, ROOT/'tools/setup_dock_windows.py'])
        elif args.action == 'build':
            command = [sys.executable, ROOT/'builds/dock/build_oss.py', args.variant]
            for name, path in build_tools.items():
                command += ['--'+name, path]
            run(command)
        elif args.action == 'test':
            for directory in ('builds/dock/tests', 'tools/tests'):
                run([sys.executable, '-m', 'unittest', 'discover', '-s', ROOT/directory, '-v'])
        else:
            if args.action == 'doctor':
                for name, path in build_tools.items():
                    if not path.is_file():
                        raise OSError(f'{name} missing: run setup first ({path})')
                    print(f'{name}: {path}', flush=True)
                    run([path, '--help' if name == 'pack' else '--version'])
            command = [sys.executable, ROOT/'tools/dock_program.py', '--loader', loader, args.action]
            if args.action == 'program':
                command += ['--variant', args.variant]
                if args.dry_run:
                    command += ['--dry-run']
            if getattr(args, 'serial', None):
                command += ['--serial', args.serial]
            run(command)
        return 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
