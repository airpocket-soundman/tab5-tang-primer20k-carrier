"""Build/run the actual RV32 firmware in a pinned, test-only MMIO ISA harness.

This never accesses hardware. RV32 software executes graph/quantization/math;
the accelerator endpoint is a host INT64 oracle, not an FPGA performance model.
The upstream interpreter's user RAM fast path is redirected through callbacks
only in the ignored build checkout, so MMIO accesses cannot bypass the oracle.
"""
from pathlib import Path
import argparse, hashlib, json, os, shlex, subprocess, sys

ROOT = Path(__file__).resolve().parents[3]
PIN = 'ffb041bab9d1513e5329f25f486378778dceed13'
URL = 'https://github.com/sysprog21/rv32emu.git'
INSTALLER = '''
/* AUTONOMOUS_ISA_TEST_ONLY: pinned internal callback installer */
void rv32emu_autonomous_install(rv32emu_t *,const riscv_io_t *,riscv_io_t *);
void rv32emu_autonomous_install(rv32emu_t *emu,const riscv_io_t *io,riscv_io_t *saved)
{
 *saved=emu->cpu->io;
 emu->cpu->io.mem_ifetch=io->mem_ifetch;
 emu->cpu->io.mem_read_w=io->mem_read_w;
 emu->cpu->io.mem_read_s=io->mem_read_s;
 emu->cpu->io.mem_read_b=io->mem_read_b;
 emu->cpu->io.mem_write_w=io->mem_write_w;
 emu->cpu->io.mem_write_s=io->mem_write_s;
 emu->cpu->io.mem_write_b=io->mem_write_b;
}
'''


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def posix(p):
    p = p.resolve()
    if os.name != 'nt':
        return str(p)
    return '/mnt/' + p.drive[0].lower() + str(p)[2:].replace('\\', '/')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--emulator-source', type=Path, default=ROOT/'build/rv32emu-upstream')
    p.add_argument('--fetch', action='store_true', help='fetch the pinned official source when absent')
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--skip-build', action='store_true')
    p.add_argument('--distro', default='Ubuntu-24.04')
    p.add_argument('--deadline-seconds', type=int, default=10860)
    a = p.parse_args()
    if a.output.exists():
        p.error('Fresh output directory required; preserve previous evidence')
    a.output.mkdir(parents=True)
    source = a.emulator_source.resolve()
    commands = []

    def command(args, log, timeout=300):
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        commands.append({'command': args, 'returncode': r.returncode})
        (a.output/log).write_text(r.stdout+r.stderr, encoding='utf-8')
        (a.output/'commands.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
        if r.returncode:
            raise RuntimeError(f'{log}: exit {r.returncode}')
        return r.stdout

    def linux(shell, log, timeout=300):
        args = ['sh', '-lc', shell]
        if os.name == 'nt':
            args = ['wsl', '-d', a.distro, '--', *args]
        return command(args, log, timeout)

    if not source.exists():
        if not a.fetch:
            p.error('Pinned source absent; use --fetch to bootstrap')
        command(['git', 'clone', '--no-checkout', URL, str(source)], 'clone.log')
        command(['git', '-C', str(source), 'checkout', '--detach', PIN], 'checkout.log')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert head == PIN, 'Refuse an unpinned emulator checkout'
    if not a.skip_build:
        for name in ['src/api.c', 'src/rv32_template.c']:
            original = subprocess.check_output(['git', '-C', str(source), 'show', PIN+':'+name]).decode('utf-8')
            patched = original
            if name.endswith('api.c'):
                patched += INSTALLER
            else:
                for width in ['W', 'S', 'B']:
                    low = width.lower()
                    old = f'#define MEM_READ_{width}(rv, addr) ram_read_{low}(rv, addr)'
                    assert patched.count(old) == 1
                    patched = patched.replace(old, f'#define MEM_READ_{width}(rv, addr) ((rv)->io.mem_read_{low}(rv, addr))')
                    old = f'#define MEM_WRITE_{width}(rv, addr, val) ram_write_{low}(rv, addr, val)'
                    assert patched.count(old) == 1
                    patched = patched.replace(old, f'#define MEM_WRITE_{width}(rv, addr, val) ((rv)->io.mem_write_{low}(rv, addr, val))')
            target = source/name
            current = target.read_text(encoding='utf-8')
            assert current in [original, patched], 'Refuse unrelated changes in test checkout '+name
            if current != patched:
                target.write_text(patched, encoding='utf-8')
        linux('cd '+shlex.quote(posix(source))+' && make mini_defconfig', 'configure.log')
        linux('cd '+shlex.quote(posix(source))+' && make -j4 -f Makefile -f '+
              shlex.quote(posix(ROOT/'fpga/npu/tests/autonomous_iss.mk'))+' '+
              shlex.quote('AUTONOMOUS_CARRIER_ROOT='+posix(ROOT))+' build/autonomous_iss_runner', 'build.log')
    config = (source/'.config').read_text()
    assert '# CONFIG_EXT_F is not set' in config and '# CONFIG_JIT is not set' in config
    executable = source/'build/autonomous_iss_runner'
    inputs = {'firmware': a.firmware.resolve(), 'package': a.package.resolve(), 'image': a.image.resolve()}
    hashes = {k: sha(v) for k, v in inputs.items()}
    provenance = {'hardware_access': False, 'upstream': URL, 'upstream_commit': PIN,
                  'test_only_interpreter_modifications': ['api callback installer', 'six user RAM callback macros'],
                  'ISA_scope': 'Actual RV32 firmware; integer accelerator MMIO oracle. Not physical FPGA execution/performance.',
                  'inputs_sha256': hashes, 'emulator_binary_sha256': sha(executable),
                  'sources_sha256': {str(x.relative_to(ROOT)): sha(x) for x in [
                      ROOT/'fpga/npu/tests/autonomous_iss_runner.c', ROOT/'fpga/npu/tests/autonomous_iss.mk',
                      ROOT/'fpga/npu/tests/run_autonomous_iss.py']},
                  'patched_upstream_sources_sha256': {n: sha(source/n) for n in ['src/api.c', 'src/rv32_template.c', '.config']},
                  'smoke': a.smoke}
    (a.output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')
    shell = 'ulimit -c 0; timeout --signal=TERM '+str(max(1, a.deadline_seconds-30))+' '+ ' '.join(shlex.quote(x) for x in [posix(executable),
        posix(a.firmware), posix(a.package), posix(a.image), posix(a.output/'output.f32'),
        posix(a.output/'result.json'), *(['--smoke'] if a.smoke else [])])
    # Keep the root executable path stable; no concurrent rebuild while a run is active.
    args = ['sh', '-lc', shell]
    if os.name == 'nt':
        args = ['wsl', '-d', a.distro, '--', *args]
    with (a.output/'runner.log').open('w', encoding='utf-8') as log:
        r = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=a.deadline_seconds)
    commands.append({'command': args, 'returncode': r.returncode})
    (a.output/'commands.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    if r.returncode:
        raise RuntimeError(f'runner.log: exit {r.returncode}; preserve raw result')
    result = json.loads((a.output/'result.json').read_text())
    assert result['execution_completed'] is True
    assert all(sha(path) == hashes[key] for key, path in inputs.items()), 'Input changed during execution'
    print(json.dumps({'ISA_execution_completed': True, 'hardware_access': False,
                      'integer_accelerator_is_host_oracle': True, 'result': str(a.output/'result.json')}))


if __name__ == '__main__':
    main()
