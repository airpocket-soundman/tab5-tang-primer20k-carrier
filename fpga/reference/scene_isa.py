"""シーン移植評価用: 汎用SIMD演算器(compute_simd)相当の整数ISAシミュレータ + 小DSL。

ISAの基準は fpga/gfx/compute/model.py (別チェックアウト・未コミット; 本ファイルはそれを読んで
意味だけ再現し、編集も import もしない)。ここは評価用の研究コードで、LINKのABIでも
RTLでもない。実機・合成・配置配線は未検証。

基本ISA(base): LDI ADD SUB MUL MULQ(Q12) LT AND XOR SHL SAR LOAD STORE (+HALT/JMP/ANY)。
r0=0, r1=group_base+lane, r15=述語。レジスタは16本×32bit、LOAD/STOREのimmは符号付き16bit。
拡張(ext)は「要望」で、機能名ごとにON/OFFできる。ONでない機能のマクロはbase命令列に展開
されるので、命令数は拡張の有無で比較できる(展開できないものは Unsupported)。

実行は numpy で (グループ数G, レーン数L) の配列を一括実行する。共有PCなので、ループは
グループ単位の生存フラグで管理し、命令数はグループごとに数える。LOAD/STOREは
グループ内レーン番号順、グループ間はchunk単位で逐次(chunk=1なら完全に逐次)。
"""
import numpy as np

M32 = 0xFFFFFFFF

# 拡張機能(要望)。名前 -> 追加される命令
FEATURES = {
    'imm': 'ADDI/ANDI/SHLI/SARI/SHRI/MULI/LTI: レジスタ演算のb側16bit即値形式',
    'minmax': 'MIN/MAX/ABS',
    'or': 'OR (bit演算)',
    'shr': 'SHR (論理右shift)',
    'sel': 'SEL d,a,b : r15!=0 ? a : b ではなく3オペランド選択 (c=述語レジスタ)',
    'mulqs': 'MULQS d,a,b,#sh : 符号付き64bit積を任意shift(0..31)して下位32bit',
    'div': 'DIV d,a,b : 符号付き32bit除算(0へ丸め)',
    'sqrt': 'ISQRT d,a : 符号なし32bit整数平方根(floor)',
    'atom': 'ATOMADD [a+imm],r[d] : メモリへの原子加算(レーン直列)',
    'ltu': 'LTU: 符号なし比較',
    'cmp': 'EQ/NE: 等値比較',
}
FULL = frozenset(FEATURES)

BASE_OPS = {'LDI', 'ADD', 'SUB', 'MUL', 'MULQ', 'LT', 'AND', 'XOR', 'SHL', 'SAR', 'LOAD',
            'STORE', 'SETP'}  # SETP = ADD r15,a,r0 (1命令として数える)


IMM_OPS = {'ADDI', 'ANDI', 'SHLI', 'SARI', 'SHRI', 'MULI', 'LTI'}


class Unsupported(Exception):
    pass


class V:
    """仮想レジスタ。"""
    __slots__ = ('id', 'name')

    def __init__(self, id_, name=''):
        self.id, self.name = id_, name

    def __repr__(self):
        return 'v%d%s' % (self.id, self.name)


def sgn(x):
    x &= M32
    return x - (1 << 32) if x & 0x80000000 else x


class Prog:
    """プログラム生成。木構造(op / loop)を保持する。"""

    def __init__(self, name, feats=()):
        self.name = name
        self.feats = frozenset(feats)
        self.nv = 0
        self.consts = {}          # 値 -> V
        self.const_cost = 0       # プロローグ命令数
        self.root = []
        self.stack = [self.root]
        self.pmask = None         # 現在の述語元(V) / None
        self.r1 = V(-1, 'id')     # r1: group_base+lane
        self.sw_cost = {}         # 'ソフト展開' の内訳(命令数)
        self.mix = {}

    # --- 基本 ---
    def has(self, f):
        return f in self.feats

    def new(self, name=''):
        self.nv += 1
        return V(self.nv, name)

    def emit(self, op, a=None, b=None, imm=0, dst=None, c=None):
        d = dst if dst is not None else self.new()
        self.stack[-1].append(('op', op, d, a, b, imm, self.pmask is not None, c))
        return d

    def k(self, value):
        """定数レジスタ(プロローグで1回だけ作る)。"""
        value = sgn(value)
        if value == 0:
            return None   # r0
        if value not in self.consts:
            v = self.new('k%d' % value)
            self.consts[value] = v
            self.const_cost += 1 if -32768 <= value <= 32767 else 4   # LDI / LDI,SHL,LDI,ADD等
        return self.consts[value]

    def _r(self, a):
        return a if a is not None else None

    # --- 述語 ---
    class _Mask:
        def __init__(self, p, v):
            self.p, self.v = p, v

        def __enter__(self):
            self.prev = self.p.pmask
            if self.v is not None:
                self.p.pmask = None
                self.p.emit('SETP', self.v)
                self.p.pmask = self.v
            return self

        def __exit__(self, *a):
            self.p.pmask = self.prev
            if self.prev is not None:
                self.p.pmask = None
                self.p.emit('SETP', self.prev)
                self.p.pmask = self.prev

    def mask(self, v):
        return Prog._Mask(self, v)

    # --- ループ ---
    def while_any(self, cond, body):
        """cond() -> 継続フラグV(非継続レーンは0にすること)。body(flag)。
        フラット化: L: cond; ANY flag(→出口); body; JMP L"""
        saved = self.pmask
        cnode, bnode = [], []
        parent = self.stack[-1]
        parent.append(None)
        pos = len(parent) - 1
        self.stack.append(cnode)
        flag = cond()
        self.stack.pop()
        self.stack.append(bnode)
        with self.mask(flag):
            body(flag)
        self.stack.pop()
        self.pmask = saved
        parent[pos] = ('loop', cnode, flag, bnode)
        if saved is not None:
            self.pmask = None
            self.emit('SETP', saved)
            self.pmask = saved

    def into(self, dst, v):
        """直前に作った値vの定義命令の出力先をdst(既存レジスタ)に付け替える(ループ持ち越し変数の更新)。"""
        blk = self.stack[-1]
        for i in range(len(blk) - 1, -1, -1):
            n = blk[i]
            if n[0] == 'op' and n[2] is v:
                blk[i] = n[:2] + (dst,) + n[3:]
                return dst
        raise ValueError('definition of value not found in current block')

    # --- 算術マクロ ---
    def _bin(self, op, a, b, base_ok=True):
        """b が int の場合: imm拡張があれば即値形式、無ければ定数レジスタ。"""
        if isinstance(b, int):
            if self.has('imm') and -32768 <= b <= 32767:
                return self.emit(op + 'I', a, None, b)
            b = self.k(b)
        return self.emit(op, a, b)

    def add(self, a, b):
        return self._bin('ADD', a, b)

    def sub(self, a, b):
        if isinstance(b, int):
            return self.add(a, -b)
        return self.emit('SUB', a, b)

    def mul(self, a, b):
        return self._bin('MUL', a, b)

    def mulq(self, a, b):
        return self.emit('MULQ', a, b if not isinstance(b, int) else self.k(b))

    def and_(self, a, b):
        return self._bin('AND', a, b)

    def xor(self, a, b):
        if isinstance(b, int):
            b = self.k(b)
        return self.emit('XOR', a, b)

    def shl(self, a, n):
        if isinstance(n, int):
            if self.has('imm'):
                return self.emit('SHLI', a, None, n)
            n = self.k(n)
        return self.emit('SHL', a, n)

    def sar(self, a, n):
        if isinstance(n, int):
            if self.has('imm'):
                return self.emit('SARI', a, None, n)
            n = self.k(n)
        return self.emit('SAR', a, n)

    def shr(self, a, n):
        """論理右shift(n: int)。"""
        if self.has('shr'):
            return self.emit('SHRI' if self.has('imm') else 'SHR', a, None if self.has('imm') else self.k(n),
                             n if self.has('imm') else 0)
        if n == 0:
            return a
        t = self.sar(a, n)
        return self.and_(t, (1 << (32 - n)) - 1)

    def lt(self, a, b):
        if isinstance(a, int):
            a = self.k(a)
        if isinstance(b, int):
            if self.has('imm') and -32768 <= b <= 32767:
                return self.emit('LTI', a, None, b)
            b = self.k(b)
        return self.emit('LT', a, b)

    def gt(self, a, b):
        return self.lt(b, a)

    def ge(self, a, b):
        return self.xor(self.lt(a, b), 1)

    def le(self, a, b):
        return self.xor(self.lt(b, a), 1)

    def or_(self, a, b):
        if self.has('or'):
            if isinstance(b, int):
                b = self.k(b)
            return self.emit('OR', a, b)
        if isinstance(b, int):
            bb = self.k(b)
        else:
            bb = b
        x = self.emit('XOR', a, bb)
        y = self.and_(a, bb) if not isinstance(b, int) else self.and_(a, b)
        return self.emit('XOR', x, y)

    def neg(self, a):
        return self.emit('SUB', None, a)

    def eq0(self, a):
        """a==0 ?(0/1)。"""
        if self.has('cmp'):
            return self.emit('EQ', a, None, 0)
        # a==0 <=> !(a<0) & !(0<a):  x|(-x) の符号
        n = self.neg(a)
        o = self.or_(a, n)
        return self.xor(self.shr(o, 31), 1)

    def eq(self, a, b):
        if self.has('cmp'):
            return self.emit('EQ', a, b)
        return self.eq0(self.emit('SUB', a, b))

    def ne(self, a, b):
        if self.has('cmp'):
            return self.emit('NE', a, b)
        return self.xor(self.eq(a, b), 1)

    def ltu(self, a, b):
        if isinstance(b, int):
            b = self.k(b)
        if self.has('ltu'):
            return self.emit('LTU', a, b)
        # 符号ビット反転して符号付き比較
        sb = self.k(-0x80000000)
        return self.emit('LT', self.xor(a, sb), self.xor(b, sb))

    def abs(self, a):
        if self.has('minmax'):
            return self.emit('ABS', a)
        m = self.sar(a, 31)
        return self.emit('SUB', self.emit('XOR', a, m), m)

    def sel(self, c, a, b):
        """c(0/1)? a : b"""
        if isinstance(a, int):
            a = self.k(a) if a else None
        if isinstance(b, int):
            b = self.k(b) if b else None
        if self.has('sel'):
            return self.emit('SEL', a, b, c=c)
        m = self.emit('SUB', None, c)       # 0 or -1
        x = self.emit('XOR', a, b)
        return self.emit('XOR', self.emit('AND', x, m), b)

    def min(self, a, b):
        if self.has('minmax'):
            return self.emit('MIN', a, b if not isinstance(b, int) else self.k(b))
        if isinstance(b, int):
            b = self.k(b)
        return self.sel(self.lt(a, b), a, b)

    def max(self, a, b):
        if self.has('minmax'):
            return self.emit('MAX', a, b if not isinstance(b, int) else self.k(b))
        if isinstance(b, int):
            b = self.k(b)
        return self.sel(self.lt(a, b), b, a)

    def clamp(self, a, lo, hi):
        return self.min(self.max(a, lo), hi)

    def mulsh(self, a, b, sh, small=False):
        """(a*b)>>sh (符号付き64bit積の算術shift)。sh=12 は基本ISAのMULQ。
        small=True: 積が 0<=a*b<2^32 と分かっている場合の簡易形(MUL→論理shift)。"""
        if isinstance(b, int):
            b = self.k(b)
        if self.has('mulqs'):
            return self.emit('MULQS', a, b, sh)
        if sh == 12:
            return self.emit('MULQ', a, b)
        if small:
            return self.shr(self.emit('MUL', a, b), sh)
        # 16bit limb: a=a1*2^16+a0 (a0>=0), b同様。 a*b>>16 = a1*b1*2^16 + a1*b0 + a0*b1 + ((a0*b0)>>16 論理)
        if sh != 16:
            raise Unsupported('mulsh base only sh=12/16')
        a1, a0 = self.sar(a, 16), self.and_(a, 0xFFFF)
        b1, b0 = self.sar(b, 16), self.and_(b, 0xFFFF)
        t = self.shl(self.emit('MUL', a1, b1), 16)
        t = self.emit('ADD', t, self.emit('MUL', a1, b0))
        t = self.emit('ADD', t, self.emit('MUL', a0, b1))
        return self.emit('ADD', t, self.shr(self.emit('MUL', a0, b0), 16))

    # --- 除算 / 平方根 ---
    def div(self, a, b, nbits=31):
        """符号付き除算(0へ丸め)。a,b は int32、b!=0。baseは非復元型の復元除算を展開。
        |a| < 2**nbits を呼び出し側が保証する。"""
        if self.has('div'):
            return self.emit('DIV', a, b)
        sa = self.sar(a, 31)
        sb_ = self.sar(b, 31)
        ua = self.emit('SUB', self.emit('XOR', a, sa), sa)
        ub = self.emit('SUB', self.emit('XOR', b, sb_), sb_)
        num = self.shl(ua, 32 - nbits)
        rem = None
        q = None
        one31 = 31
        for i in range(nbits):
            bit = self.shr(num, 31)
            num = self.shl(num, 1)
            rem = bit if rem is None else self.emit('ADD', self.emit('ADD', rem, rem), bit)
            ge = self.xor(self.lt(rem, ub), 1)
            m = self.neg(ge)
            rem = self.emit('SUB', rem, self.emit('AND', ub, m))
            q = ge if q is None else self.emit('ADD', self.emit('ADD', q, q), ge)
        s = self.emit('XOR', sa, sb_)
        return self.emit('SUB', self.emit('XOR', q, s), s)

    def isqrt(self, a, nbits=20):
        """floor(sqrt(a)), 0<=a<2**nbits (nbits<=30)。"""
        if self.has('sqrt'):
            return self.emit('ISQRT', a)
        res = None
        for i in range((nbits + 1) // 2 - 1, -1, -1):
            cand = self.add(res, 1 << i) if res is not None else self.k(1 << i)
            sq = self.emit('MUL', cand, cand)
            ok = self.xor(self.lt(a, sq), 1)
            add = self.shl(ok, i)
            res = add if res is None else self.emit('ADD', res, add)
        return res

    # --- メモリ ---
    def _addr(self, base, off):
        if -32768 <= off <= 32767:
            return base, off
        return self.add(base, off) if base is not None else self.k(off), 0

    def load(self, base, off=0):
        b, o = self._addr(base, off)
        return self.emit('LOAD', b, None, o)

    def store(self, val, base, off=0):
        b, o = self._addr(base, off)
        self.emit('STORE', b, val, o)

    def atomadd(self, val, base, off=0):
        if not self.has('atom'):
            raise Unsupported('ATOMADD is not in base ISA')
        b, o = self._addr(base, off)
        self.emit('ATOMADD', b, val, o)

    def ldi(self, value):
        value = sgn(value)
        return self.k(value) if value else None


# ----------------------------------------------------------------- 解析

def _walk(nodes, fn, depth=0):
    for n in nodes:
        if n[0] == 'op':
            fn(n, depth)
        else:
            _walk(n[1], fn, depth)
            _walk(n[3], fn, depth + 1)


def static_stats(p):
    """静的命令数: プロローグ(定数) + 直線部 + ループ(条件+本体 / 1反復, ANY+JMP含む)。"""
    out = {'prologue': p.const_cost, 'straight': 0, 'loops': [], 'ops': {}}

    def count(nodes):
        c = 0
        for n in nodes:
            if n[0] == 'op':
                c += 1
                out['ops'][n[1]] = out['ops'].get(n[1], 0) + 1
            else:
                lc = count(n[1]) + 1 + count(n[3]) + 1
                out['loops'].append(lc)
        return c
    out['straight'] = count(p.root)
    return out


def max_live(p):
    """仮想レジスタの同時生存数の見積り(ループ内で使われる外側定義はループ末尾まで生存)。
    定数レジスタはプロローグ定義。r1(id)を使う場合は+1。"""
    seq = []   # (kind, node) flat

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
    flat(p.root)
    first, last = {}, {}
    loops = []
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
        else:
            _, op, d, a, b, imm, pred, c = n
            for s in (a, b, c):
                if isinstance(s, V):
                    last[s.id] = i
                    first.setdefault(s.id, 0)
            if isinstance(d, V):
                first.setdefault(d.id, i)
                last.setdefault(d.id, i)
    for v in p.consts.values():
        first[v.id] = 0
    ev = []
    for v, f in first.items():
        if v == -1:
            continue
        ev.append((f, 1))
        ev.append((last.get(v, f) + 1, -1))
    ev.sort()
    cur = mx = 0
    for _, d in ev:
        cur += d
        mx = max(mx, cur)
    return mx


# ----------------------------------------------------------------- 実行

class Machine:
    def __init__(self, mem, lanes=4):
        self.mem = mem            # np.int32 配列(wordアドレス)
        self.L = lanes
        self.stat = {}

    def run(self, p, n_elems, chunk=None, group_base=0):
        L = self.L
        assert n_elems % L == 0, 'n_elems must be multiple of lanes'
        G = n_elems // L
        chunk = chunk or G
        tot = {'group_instr': 0, 'lane_instr': 0, 'loads': 0, 'stores': 0, 'atoms': 0,
               'groups': G, 'elements': n_elems, 'loop_iters': 0}
        for g0 in range(0, G, chunk):
            g1 = min(G, g0 + chunk)
            self._run_chunk(p, g0, g1, group_base, tot)
        tot['group_instr_per_group'] = tot['group_instr'] / G
        tot['instr_per_element'] = tot['group_instr'] / n_elems
        tot['loads_per_element'] = tot['loads'] / n_elems
        tot['stores_per_element'] = tot['stores'] / n_elems
        tot['atoms_per_element'] = tot['atoms'] / n_elems
        return tot

    def _run_chunk(self, p, g0, g1, base, tot):
        L, G = self.L, g1 - g0
        regs = {}
        ids = (np.arange(g0 * L, g1 * L, dtype=np.int64) + base).astype(np.int32).reshape(G, L)
        regs[-1] = ids
        for val, v in p.consts.items():
            regs[v.id] = np.full((G, L), val, dtype=np.int32)
        P = np.zeros((G, L), dtype=np.int32)
        gm0 = np.ones(G, dtype=bool)
        tot['group_instr'] += p.const_cost * G
        tot['lane_instr'] += p.const_cost * G * L
        zero = np.zeros((G, L), dtype=np.int32)

        def get(x):
            if x is None:
                return zero
            return regs.get(x.id, zero)

        mem = self.mem

        def block(nodes, gm):
            nonlocal P
            for n in nodes:
                if n[0] == 'op':
                    op(n, gm)
                else:
                    _, cn, flag, bn = n
                    alive = gm.copy()
                    while True:
                        block(cn, alive)
                        f = get(flag)
                        tot['group_instr'] += int(alive.sum())   # ANY
                        tot['lane_instr'] += int(alive.sum()) * L
                        anyv = (f != 0).any(axis=1)
                        alive = alive & anyv
                        if not alive.any():
                            break
                        tot['loop_iters'] += int(alive.sum())
                        block(bn, alive)
                        tot['group_instr'] += int(alive.sum())   # JMP
                        tot['lane_instr'] += int(alive.sum()) * L

        def op(n, gm):
            nonlocal P
            _, o, d, a, b, imm, pred, c = n
            ng = int(gm.sum())
            tot['group_instr'] += ng
            act = gm[:, None] & ((P != 0) if pred else np.ones((1, L), dtype=bool))
            if o == 'SETP':
                tot['lane_instr'] += ng * L
                P = np.where(gm[:, None], get(a), P)
                return
            av, bv = get(a), get(b)
            nact = int(np.count_nonzero(act))
            tot['lane_instr'] += nact
            i32 = np.int32
            if o == 'LOAD':
                addr = (av.astype(np.int64) + imm) & M32
                sel = addr[act]
                assert (sel < len(mem)).all(), 'LOAD out of range'
                res = zero.copy()
                res[act] = mem[sel]
                tot['loads'] += nact
            elif o in ('STORE', 'ATOMADD'):
                addr = (av.astype(np.int64) + imm) & M32
                sel = addr[act]
                assert (sel < len(mem)).all(), '%s out of range @%s' % (o, sel.max() if sel.size else 0)
                vals = bv[act]
                if o == 'STORE':
                    mem[sel] = vals       # 同一アドレスは配列順(群→レーン)で後勝ち
                    tot['stores'] += nact
                else:
                    np.add.at(mem, sel, vals)
                    tot['atoms'] += nact
                return
            else:
                if o in IMM_OPS:
                    bv = np.full((G, L), imm, dtype=np.int32)
                    o = o[:-1]
                if o == 'LDI':
                    res = np.full((G, L), imm, dtype=i32)
                elif o == 'ADD':
                    res = av + bv
                elif o == 'SUB':
                    res = av - bv
                elif o == 'MUL':
                    res = av * bv
                elif o == 'MULQ':
                    res = ((av.astype(np.int64) * bv) >> 12).astype(i32)
                elif o == 'MULQS':
                    res = ((av.astype(np.int64) * bv) >> imm).astype(i32)
                elif o == 'LT':
                    res = (av < bv).astype(i32)
                elif o == 'LTU':
                    res = (av.view(np.uint32) < bv.view(np.uint32)).astype(i32)
                elif o == 'AND':
                    res = av & bv
                elif o == 'XOR':
                    res = av ^ bv
                elif o == 'OR':
                    res = av | bv
                elif o == 'SHL':
                    res = (av.astype(np.int64) << (bv & 31)).astype(i32) if False else np.left_shift(av, bv & 31)
                elif o == 'SAR':
                    res = np.right_shift(av, bv & 31)
                elif o == 'SHR':
                    res = np.right_shift(av.view(np.uint32), (bv & 31).astype(np.uint32)).view(i32)
                elif o == 'MIN':
                    res = np.minimum(av, bv)
                elif o == 'MAX':
                    res = np.maximum(av, bv)
                elif o == 'ABS':
                    res = np.abs(av.astype(np.int64)).astype(i32)
                elif o == 'SEL':
                    res = np.where(get(c) != 0, av, bv)
                elif o == 'EQ':
                    res = (av == bv).astype(i32)
                elif o == 'NE':
                    res = (av != bv).astype(i32)
                elif o == 'DIV':
                    bz = np.where(bv == 0, 1, bv).astype(np.int64)
                    aq = av.astype(np.int64)
                    qq = np.abs(aq) // np.abs(bz)
                    res = (np.where((aq < 0) != (bz < 0), -qq, qq)).astype(i32)
                elif o == 'ISQRT':
                    res = np.floor(np.sqrt(av.view(np.uint32).astype(np.float64))).astype(np.int64)
                    res = np.where((res + 1) * (res + 1) <= av.view(np.uint32).astype(np.int64), res + 1, res)
                    res = np.where(res * res > av.view(np.uint32).astype(np.int64), res - 1, res).astype(i32)
                else:
                    raise AssertionError(o)
            if d is not None:
                old = regs.get(d.id, zero)
                regs[d.id] = np.where(act, res, old).astype(i32) if pred or not gm.all() else res.astype(i32)

        block(p.root, gm0)


def new_memory(words):
    return np.zeros(words, dtype=np.int32)
