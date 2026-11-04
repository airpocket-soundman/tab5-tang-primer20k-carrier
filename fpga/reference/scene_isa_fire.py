"""Fire (fire_g0) を汎用SIMD ISAのプログラムとして書く。参照は fpga/reference/fire_g0.py (既存、
専用回路fire_pixel.vのオラクル) をそのまま使い、全画素ビット一致を比較する。
Q16整数。専用opcodeは使わない(基本ISA+拡張要望のみ)。"""
import numpy as np
from . import fire_g0 as F
from .scene_isa import Prog, Machine, new_memory, sgn

W, H = F.FIRE_W, F.FIRE_H
PARAM = 0                  # PARAM[0]=frame
FB = 65536                 # RGB565を1ピクセル1word(下位16bit)で置く


def _hash_consts(octave):
    return sgn(F.HASH_A), sgn(F.HASH_B), sgn((17 + octave) * F.HASH_C)


def build(feats, octaves):
    p = Prog('fire', feats)
    i = p.r1
    # id -> (x,y): y=((id>>7)*1639)>>13 (0<=id<230400で厳密), x=id-y*640
    t7 = p.sar(i, 7)
    y = p.sar(p.mul(t7, 1639), 13)
    x = p.emit('SUB', i, p.mul(y, 640))
    frame = p.load(None, PARAM)
    nx = p.mul(p.sub(x, 320), F.SX)
    h = p.mul(p.emit('SUB', p.k(359), y), F.SY)
    t = p.mul(frame, F.TIME_STEP)
    t4 = p.sar(t, 2)
    turb = None

    def hashv(hv):
        x1 = p.xor(hv, p.shr(hv, 15))
        m = p.mul(p.and_(x1, 0xFFFF), F.HASH_M)
        return p.and_(p.xor(p.xor(m, p.sar(m, 11)), p.shr(hv, 16)), 0xFFFF)

    def smooth(f):
        if p.has('mulqs'):
            s = p.mulsh(f, f, 16)
            return p.mulsh(s, p.emit('SUB', p.k(196608), p.shl(f, 1)), 16)
        s = p.shr(p.mul(f, f), 16)              # f<2^16 なので f*f<2^32 (論理shift)
        sf = p.mul(s, f)                        # s*f < 2^32
        ce = p.shr(p.add(sf, 32767), 15)        # ceil(s*f/32768)
        return p.emit('SUB', p.mul(s, 3), ce)   # (s*(196608-2f))>>16 == 3s - ceil(sf/32768)

    def lerp(a, b, s):
        return p.add(a, p.mulsh(p.emit('SUB', b, a), s, 16))

    for o in range(octaves):
        freq = 3 << o
        u = p.add(p.mul(nx, freq), 12 << 16)
        tm = t if o == 0 else p.add(t, p.mul(t4, o))
        v = p.emit('SUB', p.mul(h, freq), tm)
        ix, fx = p.sar(u, 16), p.and_(u, 0xFFFF)
        iy, fy = p.sar(v, 16), p.and_(v, 0xFFFF)
        A, B, C = _hash_consts(o)
        hv00 = p.add(p.add(p.mul(ix, A), p.mul(iy, B)), C)
        n00 = hashv(hv00)
        hv10 = p.add(hv00, A)
        n10 = hashv(hv10)
        hv01 = p.add(hv00, B)
        n01 = hashv(hv01)
        n11 = hashv(p.add(hv10, B))
        sx, sy = smooth(fx), smooth(fy)
        a = lerp(n00, n10, sx)
        b = lerp(n01, n11, sx)
        n = lerp(a, b, sy)
        nn = p.sar(n, o + 1)
        turb = nn if turb is None else p.emit('ADD', turb, nn)
    a = p.sar(p.mul(p.emit('SUB', p.k(65536), h), 3), 1)
    b = p.mulsh(p.abs(nx), p.add(h, 32768), 16)
    c = p.mulsh(turb, 55706, 16, small=True)
    hq = p.clamp(p.add(p.emit('ADD', p.emit('SUB', a, b), c), -45875), 0, 65536)
    h3 = p.mul(hq, 3)
    r = p.sar(p.mul(p.min(h3, 65536), 255), 16)
    g = p.sar(p.mul(p.clamp(p.add(h3, -52429), 0, 65536), 240), 16)
    bl = p.sar(p.mul(p.clamp(p.add(p.shl(hq, 2), -163840), 0, 65536), 160), 16)
    col = p.shl(p.and_(r, 248), 8)
    col = p.emit('ADD', col, p.shl(p.and_(g, 252), 3))        # 互いに素なbitなのでORの代わりにADD
    col = p.emit('ADD', col, p.sar(bl, 3))
    p.store(col, i, FB)
    return p


def run(feats, octaves, frame, rows=None):
    n = W * H if rows is None else W * rows
    mem = new_memory(FB + W * H)
    mem[PARAM] = frame
    p = build(feats, octaves)
    st = Machine(mem).run(p, n)
    return p, st, mem[FB:FB + n].astype(np.int64) & 0xFFFF


def reference(frame, octaves, rows=None):
    rows = H if rows is None else rows
    return np.array([F.color(x, y, frame, octaves) for y in range(rows) for x in range(W)],
                    dtype=np.int64)
