"""Back end: scene_isa.Prog trees -> compute_simd v2 machine code (model.py ISA).

The scene DSL (fpga/reference/scene_isa*.py, from claude/track-l-scenes) has
unlimited virtual registers. compute_simd has r2..r13 (12) allocatable:
r0=0, r1=element id, r14=per-element spill pointer, r15=predicate. Values live in
a write-back register cache; spill slots are interleaved per element
(address = SPILL_BASE + id*NSLOTS + slot), so every spill access is [r14+slot].
At loop heads the cache is empty (everything flushed to memory); constants are
rematerialised, not spilled. Offline research code, not a LINK ABI.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from model import Program, encode, signed   # noqa: E402
from fpga.reference.scene_isa import V, FULL   # noqa: E402

FEATS = FULL - {'sqrt'}          # ISQRT is not implemented in compute_simd v2
ALLOC = list(range(2, 14))
IMM_OPS = {'ADDI', 'ANDI', 'SHLI', 'SARI', 'SHRI', 'MULI', 'LTI'}
REG3 = {'ADD', 'SUB', 'MUL', 'MULQ', 'LT', 'LTU', 'AND', 'XOR', 'OR', 'SHL', 'SAR', 'SHR',
        'MIN', 'MAX', 'EQ', 'NE', 'DIV'}


class Compiler:
    def __init__(self, prog, spill_base):
        self.p = prog
        self.spill_base = spill_base
        self.asm = Program()
        self.const = {v.id: val for val, v in prog.consts.items()}
        self.loc, self.owner, self.dirty, self.lru = {}, {}, set(), []
        self.slots, self.defined = {}, set()
        self.idx = 0
        self.labels = 0
        self.stats = dict(spill_stores=0, spill_loads=0, remat=0)
        self.last = self._liveness()

    # ---- liveness (same extension rule as scene_isa.max_live) ----
    def _liveness(self):
        seq = []

        def flat(nodes):
            for n in nodes:
                if n[0] == 'op':
                    seq.append(n)
                else:
                    seq.append(('begin',))
                    flat(n[1])
                    seq.append(('flag', n[2]))
                    flat(n[3])
                    seq.append(('end',))
        flat(self.p.root)
        first, last, loops = {}, {}, []
        for i, n in enumerate(seq):
            if n[0] == 'begin':
                loops.append(i)
            elif n[0] == 'end':
                b = loops.pop()
                for v, f in list(first.items()):
                    if f < b and last.get(v, -1) >= b:
                        last[v] = max(last[v], i)
            elif n[0] == 'flag':
                if n[1] is not None:
                    last[n[1].id] = max(last.get(n[1].id, 0), i)
                    first.setdefault(n[1].id, 0)
            else:
                _, op, d, a, b, imm, pred, c = n
                for s in (a, b, c):
                    if isinstance(s, V):
                        last[s.id] = i
                        first.setdefault(s.id, 0)
                if isinstance(d, V) and op not in ('STORE', 'ATOMADD'):
                    first.setdefault(d.id, i)
                    last.setdefault(d.id, i)
        return last

    # ---- register cache ----
    def alive(self, vid):
        return self.last.get(vid, -1) > self.idx

    def touch(self, vid):
        if vid in self.lru:
            self.lru.remove(vid)
        self.lru.append(vid)

    def slot(self, vid):
        return self.slots.setdefault(vid, len(self.slots))

    def spill(self, vid):
        if vid in self.dirty and vid not in self.const:
            self.asm.emit('STORE', dst=self.loc[vid], a=14, imm=self.slot(vid))
            self.stats['spill_stores'] += 1
        self.dirty.discard(vid)

    def release(self, vid):
        r = self.loc.pop(vid)
        self.owner.pop(r, None)
        self.dirty.discard(vid)
        if vid in self.lru:
            self.lru.remove(vid)

    def get_reg(self, pinned):
        for r in ALLOC:
            if r not in self.owner and r not in pinned:
                return r
        for vid in self.lru:
            r = self.loc[vid]
            if r in pinned:
                continue
            if self.alive(vid) or vid == self.cur_dst:
                self.spill(vid)
            self.release(vid)
            return r
        raise RuntimeError('register allocation failed')

    def bind(self, vid, r):
        self.loc[vid] = r
        self.owner[r] = vid
        self.touch(vid)

    def load_const(self, r, value):
        if -32768 <= value <= 32767:
            self.asm.emit('LDI', dst=r, imm=value)
        else:
            lo = value & 0xffff
            if lo >= 0x8000:
                lo -= 0x10000
            hi = ((value - lo) >> 16) & 0xffff
            self.asm.emit('LUI', dst=r, imm=hi)
            if lo:
                self.asm.emit('ADDI', dst=r, a=r, imm=lo)
        self.stats['remat'] += 1

    def ensure(self, v, pinned):
        if v is None:
            return 0
        if v.id == -1:
            return 1
        if v.id in self.loc:
            self.touch(v.id)
            return self.loc[v.id]
        r = self.get_reg(pinned)
        if v.id in self.const:
            self.load_const(r, self.const[v.id])
        else:
            self.asm.emit('LOAD', dst=r, a=14, imm=self.slot(v.id))
            self.stats['spill_loads'] += 1
        self.bind(v.id, r)
        return r

    def flush(self):
        for vid in list(self.loc):
            if vid in self.dirty and self.alive_or_cur(vid):
                self.spill(vid)

    def alive_or_cur(self, vid):
        return self.last.get(vid, -1) >= self.idx

    def invalidate(self):
        self.loc.clear(); self.owner.clear(); self.dirty.clear(); self.lru.clear()

    def save(self):
        return (dict(self.loc), dict(self.owner), set(self.dirty), list(self.lru))

    def restore(self, s):
        self.loc, self.owner, self.dirty, self.lru = dict(s[0]), dict(s[1]), set(s[2]), list(s[3])

    def free_dead(self):
        for vid in list(self.loc):
            if self.last.get(vid, -1) <= self.idx:
                self.release(vid)

    # ---- code generation ----
    def op(self, n):
        _, o, d, a, b, imm, pred, c = n
        self.cur_dst = None
        if o == 'SETP':
            ra = self.ensure(a, set())
            self.asm.emit('ADD', dst=15, a=ra, b=0)
            return
        pinned = set()
        ra = self.ensure(a, pinned); pinned.add(ra)
        rb = self.ensure(b, pinned); pinned.add(rb)
        if o in ('STORE', 'ATOMADD'):
            # DSL: a = base, b = value
            self.asm.emit(o, dst=rb, a=ra, imm=imm, pred=pred)
            return
        self.cur_dst = d.id if isinstance(d, V) else None
        rd = None
        if o == 'SEL':
            rc = self.ensure(c, pinned); pinned.add(rc)
            if pred and d.id in self.defined:
                raise NotImplementedError('predicated SEL redefining a live value')
            old = self.loc.get(d.id)
            rd = self.get_reg(pinned | ({old} if old is not None else set()))
            if pred:
                self.asm.emit('LDI', dst=rd, imm=0)
            self.asm.emit('ADD', dst=rd, a=rc, b=0, pred=pred)
            self.asm.emit('SEL', dst=rd, a=ra, b=rb, pred=pred)
            if old is not None:
                self.release(d.id)
            self.bind(d.id, rd)
            self.dirty.add(d.id); self.defined.add(d.id)
            return
        if d.id in self.loc:
            rd = self.loc[d.id]
            self.touch(d.id)
        elif pred and d.id in self.defined:
            rd = self.ensure(d, pinned)
        else:
            rd = self.get_reg(pinned)
            self.bind(d.id, rd)
            if pred:
                self.asm.emit('LDI', dst=rd, imm=0)       # inactive lanes read 0
        if o == 'LOAD':
            self.asm.emit('LOAD', dst=rd, a=ra, imm=imm, pred=pred)
        elif o == 'LDI':
            self.asm.emit('LDI', dst=rd, imm=imm, pred=pred)
        elif o in IMM_OPS:
            if o == 'ANDI' and imm < 0:
                t = self.get_reg(pinned | {rd})
                self.asm.emit('LDI', dst=t, imm=imm)
                self.asm.emit('AND', dst=rd, a=ra, b=t, pred=pred)
            else:
                self.asm.emit(o, dst=rd, a=ra, imm=imm, pred=pred)
        elif o == 'MULQS':
            self.asm.emit('MULSH', dst=rd, a=ra, b=rb, imm=imm, pred=pred)
        elif o == 'ABS':
            self.asm.emit('ABS', dst=rd, a=ra, pred=pred)
        elif o in REG3:
            self.asm.emit(o, dst=rd, a=ra, b=rb, pred=pred)
        else:
            raise NotImplementedError(o)
        self.dirty.add(d.id); self.defined.add(d.id)

    def nodes(self, nodes):
        for n in nodes:
            if n[0] == 'op':
                self.op(n)
                self.free_dead()
                self.idx += 1
            else:
                _, cn, flag, bn = n
                k = self.labels
                self.labels += 1
                self.idx += 1                              # 'begin'
                self.flush(); self.invalidate()
                self.asm.label(f'L{k}')
                self.nodes(cn)
                rf = self.ensure(flag, set())
                self.flush()
                self.asm.branch('ANY', f'B{k}', a=rf)
                self.asm.branch('JMP', f'E{k}')
                self.asm.label(f'B{k}')
                saved = self.save()
                self.idx += 1                              # 'flag'
                self.nodes(bn)
                self.flush()
                self.asm.branch('JMP', f'L{k}')
                self.asm.label(f'E{k}')
                self.idx += 1                              # 'end'
                self.restore(saved)
                self.free_dead()

    def compile(self):
        a = self.asm
        # r14 = SPILL_BASE + r1 * NSLOTS (NSLOTS patched after compilation)
        a.emit('MULI', dst=14, a=1, imm=1)
        self.load_const(13, self.spill_base)
        a.emit('ADD', dst=14, a=14, b=13)
        self.nodes(self.p.root)
        a.emit('HALT')
        words = a.assemble()
        words[0] = encode('MULI', dst=14, a=1, imm=max(1, len(self.slots)))
        return words, len(self.slots)


def compile_prog(prog, spill_base):
    c = Compiler(prog, spill_base)
    words, nslots = c.compile()
    return dict(words=words, nslots=nslots, stats=c.stats, instructions=len(words))
