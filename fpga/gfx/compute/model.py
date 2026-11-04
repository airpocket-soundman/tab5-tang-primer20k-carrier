"""Assembler, executable ISA reference, and two programs for compute_simd.

This is an offline research ISA, not a LINK command ABI.
"""
from dataclasses import dataclass

OPS = {name: number for number, name in enumerate(
    ('HALT', 'LDI', 'ADD', 'SUB', 'MUL', 'MULQ', 'LT', 'AND', 'XOR',
     'SHL', 'SAR', 'LOAD', 'STORE', 'JMP', 'ANY'))}


def signed(value):
    value &= 0xffffffff
    return value - 0x100000000 if value & 0x80000000 else value


def encode(op, dst=0, a=0, b=0, imm=0, pred=False):
    if op not in OPS or any(type(r) is not int or not 0 <= r < 16 for r in (dst, a, b)):
        raise ValueError('unknown operation or register outside r0..r15')
    immediate = op in ('LDI', 'LOAD', 'STORE', 'JMP', 'ANY')
    if immediate:
        if b or not (-32768 <= imm <= 32767 if op in ('LDI', 'LOAD', 'STORE') else 0 <= imm <= 65535):
            raise ValueError('invalid immediate')
    elif imm:
        raise ValueError('register instruction has no immediate')
    if pred and op in ('HALT', 'JMP', 'ANY'):
        raise ValueError('flow instructions must be unconditional')
    return (OPS[op] << 26) | (int(pred) << 25) | (dst << 21) | (a << 17) | (
        (imm & 0xffff) if immediate else b << 13)


class Program:
    def __init__(self):
        self.words = []
        self.labels = {}
        self.fixups = []

    def emit(self, op, **kwargs):
        self.words.append(encode(op, **kwargs))

    def label(self, name):
        if name in self.labels:
            raise ValueError('duplicate label')
        self.labels[name] = len(self.words)

    def branch(self, op, label, a=0):
        self.fixups.append((len(self.words), op, label, a))
        self.words.append(0)

    def assemble(self):
        words = self.words.copy()
        for index, op, label, a in self.fixups:
            words[index] = encode(op, a=a, imm=self.labels[label])
        return words


def julia_program(cx=-2949, cy=819, iterations=64):
    """Input x at word[id], y at word[id+32]; output count at word[id+64]."""
    p = Program()
    p.emit('LOAD', dst=2, a=1)
    p.emit('LOAD', dst=3, a=1, imm=32)
    for dst, imm in ((4, cx), (5, cy), (6, iterations), (8, 16384), (13, 1), (14, 1)):
        p.emit('LDI', dst=dst, imm=imm)
    p.label('loop')
    p.emit('MULQ', dst=9, a=2, b=2)
    p.emit('MULQ', dst=10, a=3, b=3)
    p.emit('ADD', dst=12, a=9, b=10)
    p.emit('LT', dst=15, a=12, b=8)
    p.emit('AND', dst=14, a=14, b=15)
    p.emit('LT', dst=15, a=7, b=6)
    p.emit('AND', dst=14, a=14, b=15)
    p.emit('ADD', dst=15, a=14)
    p.branch('ANY', 'step', a=15)
    p.emit('STORE', dst=7, a=1, imm=64)
    p.emit('HALT')
    p.label('step')
    p.emit('MULQ', dst=11, a=2, b=3, pred=True)
    p.emit('SUB', dst=2, a=9, b=10, pred=True)
    p.emit('ADD', dst=2, a=2, b=4, pred=True)
    p.emit('ADD', dst=3, a=11, b=11, pred=True)
    p.emit('ADD', dst=3, a=3, b=5, pred=True)
    p.emit('ADD', dst=7, a=7, b=13, pred=True)
    p.branch('JMP', 'loop')
    return p.assemble()


def affine_program(scale=6144, bias=-1024):
    """Unrelated kernel: output[id+64] = floor(input[id]*scale/4096)+bias."""
    return [encode('LOAD', dst=2, a=1), encode('LDI', dst=3, imm=scale),
            encode('LDI', dst=4, imm=bias), encode('MULQ', dst=5, a=2, b=3),
            encode('ADD', dst=5, a=5, b=4), encode('STORE', dst=5, a=1, imm=64),
            encode('HALT')]


@dataclass
class Result:
    memory: list
    registers: list
    instructions: int
    error: int
    requests: list


def execute(program, memory, lanes=4, base=0, entry=0, budget=10000, words=256,
            fault_address=None):
    """Reference semantics; memory addresses are unsigned 32-bit WORD indices.

    Budget counts decoded instructions, including HALT and faulty instructions.
    An invalid fetch and budget exhaustion do not decode an instruction.
    """
    memory = [signed(x) for x in memory]
    registers = [[0] * 16 for _ in range(lanes)]
    for lane in range(lanes):
        registers[lane][1] = signed(base + lane)
    pc, count, error, requests = entry, 0, 0, []
    if entry >= words:
        return Result(memory, registers, 0, 3, requests)
    while True:
        if not budget:
            error = 5
            break
        if not 0 <= pc < words:
            error = 3
            break
        if pc >= len(program) or program[pc] is None:
            error = 2
            break
        if count >= budget:
            error = 5
            break
        insn = program[pc]
        op, pred, dst, a, b = insn >> 26, bool(insn & (1 << 25)), (insn >> 21) & 15, (insn >> 17) & 15, (insn >> 13) & 15
        imm = insn & 65535
        simm = imm - 65536 if imm & 32768 else imm
        count += 1
        pc += 1
        if op == OPS['HALT']:
            error = 1 if pred else 0
            break
        if op in (OPS['JMP'], OPS['ANY']):
            if pred:
                error = 1
                break
            if op == OPS['JMP'] or any(r[a] for r in registers):
                if imm >= words:
                    error = 3
                    break
                pc = imm
            continue
        if op not in OPS.values():
            error = 1
            break
        for r in registers:
            if pred and not r[15]:
                continue
            av, bv = r[a], r[b]
            if op in (OPS['LOAD'], OPS['STORE']):
                address = (av + simm) & 0xffffffff
                requests.append((int(op == OPS['STORE']), address, r[dst] & 0xffffffff))
                if address >= len(memory) or address == fault_address:
                    error = 4
                    break
                if op == OPS['STORE']:
                    memory[address] = r[dst]
                    continue
                value = memory[address]
            elif op == OPS['LDI']: value = simm
            elif op == OPS['ADD']: value = av + bv
            elif op == OPS['SUB']: value = av - bv
            elif op == OPS['MUL']: value = av * bv
            elif op == OPS['MULQ']: value = (av * bv) // 4096
            elif op == OPS['LT']: value = int(av < bv)
            elif op == OPS['AND']: value = av & bv
            elif op == OPS['XOR']: value = av ^ bv
            elif op == OPS['SHL']: value = av << (bv & 31)
            elif op == OPS['SAR']: value = av >> (bv & 31)
            else: raise AssertionError(op)
            if dst:
                r[dst] = signed(value)
        if error:
            break
    return Result(memory, registers, count, error, requests)


def julia_oracle(x, y, cx=-2949, cy=819, limit=64):
    """Algorithm oracle independent of the ISA interpreter (Q12, floor, wrap32)."""
    count = 0
    while count < limit:
        xx, yy = signed(x * x // 4096), signed(y * y // 4096)
        if signed(xx + yy) >= 16384:
            break
        x, y = signed(xx - yy + cx), signed(2 * signed(x * y // 4096) + cy)
        count += 1
    return count
