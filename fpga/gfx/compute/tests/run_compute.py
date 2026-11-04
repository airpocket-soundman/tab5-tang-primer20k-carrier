"""Offline ISA/oracle/RTL campaign and optional GW2A component synthesis.

No hardware or network access. All build artifacts go under fpga/build.
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

COMPUTE = Path(__file__).resolve().parents[1]
FPGA = COMPUTE.parents[1]
sys.path.insert(0, str(COMPUTE))
from model import OPS, affine_program, encode, execute, julia_oracle, julia_program, signed


def run_tool(command, **kwargs):
    # OSS CAD Suite Windows DLLs live in lib/. Change only the child PATH.
    binary = Path(shutil.which(command[0]) or command[0]).resolve()
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join((str(binary.parent),str(binary.parent.parent/'lib'),env.get('PATH','')))
    return subprocess.run(command,env=env,**kwargs)


def hexfile(path, values, size=None):
    values = list(values)
    if size is not None:
        values += [0] * (size-len(values))
    path.write_text(''.join(f'{(x or 0) & 0xffffffff:08x}\n' for x in values), encoding='ascii')


def cases(lanes):
    rng = random.Random(20261104)
    points = [(0, 0), (8192, 0), (-4096, 0), (-2579, -693), (4096, 4096),
              (-1, -1), (-6144, 2048), (0, 4096)]
    points += [(rng.randrange(-7000, 7001), rng.randrange(-5000, 5001)) for _ in range(16)]
    for group in range(0, len(points), lanes):
        memory = [0] * 256
        for lane, (x, y) in enumerate(points[group:group+lanes]):
            memory[lane], memory[lane+32] = x, y
        program = julia_program(iterations=32)
        oracle = [julia_oracle(memory[i], memory[i+32], limit=32) for i in range(lanes)]
        assert execute(program, memory, lanes).memory[64:64+lanes] == oracle
        yield dict(name=f'julia-{group}', program=program, memory=memory, oracle=oracle)
    for group in range(4):
        memory = [signed(rng.getrandbits(32)) for _ in range(256)]
        scale, bias = rng.randrange(-32768, 32768), rng.randrange(-32768, 32768)
        program = affine_program(scale, bias)
        base = group * lanes
        expected = [signed((memory[base+i]*scale)//4096+bias) for i in range(lanes)]
        result = execute(program, memory, lanes, base)
        assert result.memory[base+64:base+64+lanes] == expected
        yield dict(name=f'affine-{group}', program=program, memory=memory, base=base, oracle=expected)
    # Random arithmetic with signed extremes, variable shifts, and an independent
    # ISA interpreter; all lane registers and all memory words are compared.
    for trial in range(6):
        program = [encode('LOAD', dst=2, a=1), encode('LOAD', dst=3, a=1, imm=32)]
        for _ in range(40):
            op = rng.choice(('ADD', 'SUB', 'MUL', 'MULQ', 'LT', 'AND', 'XOR', 'SHL', 'SAR'))
            program.append(encode(op, dst=rng.randrange(0,16), a=rng.randrange(16),
                                  b=rng.randrange(16), pred=bool(rng.randrange(2))))
        program += [encode('STORE', dst=2, a=0, imm=100), encode('HALT')]
        memory = [signed(rng.getrandbits(32)) for _ in range(256)]
        memory[:4] = [0x7fffffff, -0x80000000, -1, 1]
        yield dict(name=f'arithmetic-{trial}', program=program, memory=memory)
    empty = [0] * 256
    negative = [encode('LDI', dst=2, imm=-1), encode('LDI', dst=3, imm=1),
                encode('MULQ', dst=4, a=2, b=3), encode('STORE', dst=4, a=1, imm=64), encode('HALT')]
    assert execute(negative, empty, lanes).memory[64:64+lanes] == [-1]*lanes
    yield dict(name='negative-floor', program=negative, memory=empty)
    masked = [encode('LOAD', dst=2, a=1, imm=0, pred=True),
              encode('STORE', dst=2, a=1, imm=-1, pred=True), encode('HALT')]
    yield dict(name='masked-no-access', program=masked, memory=empty)
    # Mask only alternating lanes, including loads/stores and r15 updates.
    memory = empty.copy()
    for i in range(lanes): memory[i] = i % 2
    yield dict(name='masked-memory', memory=memory, program=[
        encode('LOAD',dst=15,a=1),encode('LDI',dst=2,imm=-17,pred=True),
        encode('STORE',dst=2,a=1,imm=64,pred=True),
        encode('LOAD',dst=3,a=1,imm=64,pred=True),encode('HALT')])
    for name, program, extra in (
        ('bad-op', [63 << 26], {}),
        ('bad-pred-flow', [encode('HALT') | (1 << 25)], {}),
        ('bad-pred-jump', [encode('JMP') | (1 << 25)], {}),
        ('bad-pred-any', [encode('ANY') | (1 << 25)], {}),
        ('unloaded', [], {}),
        ('hole', [encode('JMP',imm=2), encode('HALT'), None], {}),
        ('branch-range', [encode('JMP',imm=256)], {}),
        ('fallthrough-range', [None]*255 + [encode('LDI',dst=2,imm=1)], {'entry':255}),
        ('entry-range', [encode('HALT')], {'entry':256}),
        ('zero-budget', [encode('HALT')], {'budget':0}),
        ('infinite-loop', [encode('JMP')], {'budget':17}),
        ('budget-exact', [encode('LDI',dst=2,imm=3),encode('HALT')], {'budget':2}),
        ('budget-short', [encode('LDI',dst=2,imm=3),encode('HALT')], {'budget':1}),
        ('load-error', [encode('LOAD',dst=2,a=1),encode('HALT')], {'fault_address':lanes-1}),
        ('store-error', [encode('STORE',dst=1,a=1),encode('HALT')], {'fault_address':lanes-1}),
        ('address-underflow', [encode('LOAD',dst=2,a=0,imm=-1),encode('HALT')], {}),
        ('base-wrap', [encode('STORE',dst=1,a=1,imm=1),encode('HALT')], {'base':0xffffffff}),
    ):
        yield dict(name=name,program=program,memory=empty,**extra)


def pk565(u):
    u &= 0xffffffff
    return ((u >> 19 & 31) << 11) | ((u >> 10 & 63) << 5) | (u >> 3 & 31)


def up565(u):
    r, g, b = u >> 11 & 31, u >> 5 & 63, u & 31
    return ((r << 3 | r >> 2) << 16) | ((g << 2 | g >> 4) << 8) | (b << 3 | b >> 2)


def extension_cases(lanes):
    """Cases for MIN/MAX/ABS/SAT8/PK565/UP565 and byte/halfword access.

    Uses its own RNG so the original campaign stays bit-identical.
    """
    rng = random.Random(20261105)
    alu = ('MIN', 'MAX', 'ABS', 'SAT8', 'PK565', 'UP565', 'ADD', 'SUB', 'SAR', 'LT')
    for trial in range(6):
        program = [encode('LOAD', dst=2, a=1), encode('LOAD', dst=3, a=1, imm=32)]
        for _ in range(40):
            program.append(encode(rng.choice(alu), dst=rng.randrange(16), a=rng.randrange(16),
                                  b=rng.randrange(16), pred=bool(rng.randrange(2))))
        program += [encode('STORE', dst=2, a=0, imm=100), encode('HALT')]
        memory = [signed(rng.getrandbits(32)) for _ in range(256)]
        memory[:4] = [-0x80000000, 0x7fffffff, -1, 0]
        yield dict(name=f'ext-alu-{trial}', program=program, memory=memory)
    # Independent oracles for the scalar semantics, one value per lane.
    values = [0, -1, 255, 256, -0x80000000, 0x7fffffff, 0x00ffffff, 0x00abcdef,
              0x00f8fcf8, 0x12345678, 40, -7]
    memory = [0] * 256
    for i, v in enumerate(values): memory[i] = v
    program = [encode('LOAD', dst=2, a=1), encode('ABS', dst=3, a=2), encode('SAT8', dst=4, a=2),
               encode('MIN', dst=5, a=2, b=3), encode('MAX', dst=6, a=2, b=3),
               encode('PK565', dst=7, a=2), encode('UP565', dst=8, a=7)]
    for k, reg in enumerate((3, 4, 5, 6, 7, 8)):
        program.append(encode('STORE', dst=reg, a=1, imm=32 + 16 * k))
    program.append(encode('HALT'))
    for base in range(0, len(values), lanes):
        if base + lanes > len(values): break
        ids = range(base, base + lanes)
        expected = []
        for reg in range(6):
            for i in ids:
                v = signed(values[i])
                expected.append([signed(abs(v)), min(max(v, 0), 255), signed(min(v, signed(abs(v)))),
                                 signed(max(v, signed(abs(v)))), pk565(v), up565(pk565(v))][reg])
        result = execute(program, memory, lanes, base)
        got = [result.memory[32 + 16 * k + i] for k in range(6) for i in ids]
        assert got == expected, (base, got, expected)
        yield dict(name=f'ext-scalar-{base}', program=program, memory=memory, base=base)
    # RGB888 -> RGB565 store with STH, then LDH/UP565 round trip.
    memory = [0] * 256
    for i in range(32): memory[i] = rng.getrandbits(24)
    program = [encode('LOAD', dst=2, a=1), encode('PK565', dst=3, a=2), encode('ADD', dst=4, a=1, b=1),
               encode('STH', dst=3, a=4, imm=512), encode('LDH', dst=5, a=4, imm=512),
               encode('UP565', dst=6, a=5), encode('STORE', dst=6, a=1, imm=64), encode('HALT')]
    for base in (0, lanes):
        result = execute(program, memory, lanes, base)
        for i in range(lanes):
            assert result.memory[64 + base + i] == up565(pk565(memory[base + i]))
            half = (result.memory[128 + (base + i) // 2] >> (16 * ((base + i) & 1))) & 0xffff
            assert half == pk565(memory[base + i])
        yield dict(name=f'pixel-pack-{base}', program=program, memory=memory, base=base)
    # Byte/halfword accesses against a little-endian byte-array oracle.
    memory = [signed(rng.getrandbits(32)) for _ in range(256)]
    program = [encode('LDB', dst=2, a=1, imm=1), encode('LDBS', dst=3, a=1, imm=2),
               encode('ADD', dst=4, a=1, b=1), encode('LDH', dst=5, a=4, imm=6),
               encode('LDHS', dst=6, a=4, imm=10),
               encode('STB', dst=2, a=1, imm=301), encode('STB', dst=3, a=1, imm=402),
               encode('STH', dst=5, a=4, imm=504), encode('STH', dst=6, a=4, imm=610),
               encode('STB', dst=0, a=1, imm=700), encode('HALT')]
    base = 3
    result = execute(program, memory, lanes, base)
    raw = bytearray()
    for w in memory: raw += (w & 0xffffffff).to_bytes(4, 'little')
    for i in range(lanes):
        r = base + i
        b1, b2 = raw[r + 1], raw[r + 2]
        h6 = int.from_bytes(raw[2 * r + 6:2 * r + 8], 'little')
        h10 = int.from_bytes(raw[2 * r + 10:2 * r + 12], 'little')
        assert result.registers[i][2] == b1 and result.registers[i][3] == b2 - 256 * (b2 >> 7)
        assert result.registers[i][5] == h6 and result.registers[i][6] == h10 - 65536 * (h10 >> 15)
        raw[r + 301] = b1
        raw[r + 402] = (b2 - 256 * (b2 >> 7)) & 255
        raw[2 * r + 504:2 * r + 506] = h6.to_bytes(2, 'little')
        raw[2 * r + 610:2 * r + 612] = (h10 - 65536 * (h10 >> 15) & 0xffff).to_bytes(2, 'little')
        raw[r + 700] = 0
    assert [signed(int.from_bytes(raw[4 * i:4 * i + 4], 'little')) for i in range(256)] == result.memory
    yield dict(name='byte-halfword-access', program=program, memory=memory, base=base)
    empty = [0] * 256
    even = [encode('LDI', dst=2, imm=1), encode('AND', dst=15, a=1, b=2),
            encode('XOR', dst=15, a=15, b=2), encode('LDH', dst=3, a=1, pred=True),
            encode('STH', dst=1, a=1, imm=100, pred=True), encode('HALT')]
    for name, prog, extra in (
        ('half-misaligned', [encode('LDH', dst=2, a=0, imm=1), encode('HALT')], {}),
        ('half-misaligned-lane1', [encode('LDH', dst=2, a=1), encode('HALT')], {}),
        ('half-misaligned-store', [encode('STH', dst=2, a=0, imm=3), encode('HALT')], {}),
        ('half-masked-odd', even, {}),
        ('byte-out-of-range', [encode('LDB', dst=2, a=0, imm=1024), encode('HALT')], {}),
        ('byte-fault', [encode('LDB', dst=2, a=1), encode('HALT')], {'fault_address': 0}),
        ('byte-negative-address', [encode('LDB', dst=2, a=0, imm=-1), encode('HALT')], {}),
        ('last-op', [(26 << 26) | 0, encode('HALT')], {}),
        ('first-bad-op', [27 << 26], {}),
    ):
        yield dict(name=name, program=prog, memory=empty, **extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog', default='iverilog')
    parser.add_argument('--vvp', default='vvp')
    parser.add_argument('--yosys', help='Optional existing native Yosys executable')
    parser.add_argument('--output', type=Path, default=FPGA/'build/compute-simd')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    for tool in (args.iverilog,args.vvp):
        if not shutil.which(tool): parser.error(f'existing executable required: {tool}')
    args.output.mkdir(parents=True,exist_ok=True)
    report = dict(date='2026-11-04', scope='offline programmable SIMD component; no hardware, transport or DDR PHY',
                  tests=[], synthesis=[], hardware_tested=False, cpu_speedup_measured=False)
    rtl = COMPUTE/'rtl/compute_simd.v'
    bench = COMPUTE/'tests/tb_compute_simd.v'
    for lanes in (1,2,4):
        exe = args.output/f'compute-{lanes}.vvp'
        run_tool([args.iverilog,'-g2012','-Wall','-s','tb_compute_simd',
                        f'-Ptb_compute_simd.LANES={lanes}','-o',str(exe),str(rtl),str(bench)],check=True)
        for case in itertools.chain(cases(lanes), extension_cases(lanes)):
            directory = args.output/f'{lanes}-{case["name"]}'
            directory.mkdir(exist_ok=True)
            program, memory = case['program'],case['memory']
            options = {k:case[k] for k in ('base','entry','budget','fault_address') if k in case}
            result = execute(program,memory,lanes=lanes,**options)
            hexfile(directory/'program.hex',program,256)
            hexfile(directory/'present.hex',[int(x is not None) for x in program],256)
            hexfile(directory/'input.hex',memory,256)
            hexfile(directory/'expected.hex',result.memory,256)
            hexfile(directory/'registers.hex',[x for r in result.registers for x in r])
            for index,field in enumerate(('write','addr','data','mask')):
                hexfile(directory/f'trace_{field}.hex',[x[index] for x in result.requests],4096)
            for stalled in (0,1):
                command = [args.vvp,str(exe),f'+directory={directory.as_posix()}',
                           f'+program_words={len(program)}',f'+base={case.get("base",0)}',
                           f'+entry={case.get("entry",0)}',f'+budget={case.get("budget",10000)}',
                           f'+fault={case.get("fault_address",-1)}',f'+stall={stalled}',
                           f'+error={result.error}',f'+instructions={result.instructions}',
                           f'+requests={len(result.requests)}']
                completed = run_tool(command,capture_output=True,text=True,timeout=60)
                if completed.returncode:
                    raise RuntimeError(f'{lanes}/{case["name"]}/stall={stalled}\n{completed.stdout}\n{completed.stderr}')
                runs = re.findall(r'PASS run=(\d+) lanes=(\d+) cycles=(\d+) instructions=(\d+) requests=(\d+) error=(\d+)',completed.stdout)
                if len(runs)!=2: raise RuntimeError(completed.stdout)
                report['tests'].append(dict(name=case['name'],lanes=lanes,stalled=bool(stalled),
                                            cycles=int(runs[0][2]),instructions=result.instructions,
                                            requests=len(result.requests),error=result.error,restarts_checked=2))
        print(f'PASS {lanes} lanes: oracle, arithmetic, extension ops, byte/halfword access, masks, memory faults, branch/budget faults, restart/reset',flush=True)
        if args.yosys:
            directory=args.output/f'synth-{lanes}'
            directory.mkdir(exist_ok=True)
            stats=directory/'stats.json'
            script=(f'read_verilog "{rtl.as_posix()}"; chparam -set LANES {lanes} compute_simd; '
                    f'synth_gowin -family gw2a -top compute_simd; check -assert; '
                    f'tee -o "{stats.as_posix()}" stat -json')
            result_synth=run_tool([args.yosys,'-p',script],capture_output=True,text=True,timeout=300)
            (directory/'synthesis.log').write_text(result_synth.stdout+result_synth.stderr,encoding='utf8')
            if result_synth.returncode: raise RuntimeError(f'synthesis failed: {directory}/synthesis.log')
            statistics=json.loads(stats.read_text())
            report['synthesis'].append(dict(lanes=lanes,statistics=statistics,
                                           placement_routing=False,timing_signoff=False))
            print(f'PASS GW2A component synthesis, {lanes} lanes',flush=True)
    files=[rtl,bench,COMPUTE/'model.py',Path(__file__).resolve()]
    report['sources']={p.relative_to(FPGA.parent).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    report['tools']={}
    for name,tool in (('iverilog',args.iverilog),('vvp',args.vvp),('yosys',args.yosys)):
        if tool:
            version=run_tool([tool,'-V'],capture_output=True,text=True,timeout=20)
            report['tools'][name]=dict(path=str(Path(shutil.which(tool)).resolve()),version=(version.stdout+version.stderr).splitlines()[0])
    target=args.report or args.output/'report.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(f'PASS {len(report["tests"])} RTL conditions x 2 launches; report: {target}',flush=True)


if __name__=='__main__': main()
