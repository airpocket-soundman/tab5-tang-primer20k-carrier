"""Wire / Particles / Galaxy / Flow を汎用SIMD ISAのプログラムとして書き、
CPU整数参照(素のPython整数)と全画素比較する。Fireは scene_isa_fire.py。

整数シーン定義(g1)は tab5-fpga-gpu main/lab.cpp (float版) を ISA で書ける形に再定義したもので、
float版と画素一致はしない。違いは各関数のdocstringと設計文書に列挙。
表(sin/逆数/パレット/星)は『データ』であってFPGA回路ではない(ホストまたは初期化ジョブが作る)。
"""
import math
import numpy as np
from .scene_isa import Prog, Machine, new_memory, sgn, M32

W, H = 640, 360
LANES = 4

# ---- メモリ配置(wordアドレス) ----
PARAM = 0                 # [0]=frame, Flowの渦パラメータは [16..]
SIN = 64                  # 4096 entries Q12
PAL = SIN + 4096          # 256 entries (RGB565)
FLOWPAL = PAL + 256       # 4
EDGE = FLOWPAL + 4        # 16 words: v0|v1<<4 (k>=12は0)
RECIP_BASE_IDX = 512
RECIP = EDGE + 16         # 3072 entries: index = (depth>>3) - 512
CUBE = RECIP + 3072       # (cx,cy) x 144
VB = CUBE + 2 * 144       # 144*16 words
STAR = VB + 144 * 16 + 64  # 3 words x 16384  (>32767 を跨ぐ: アドレス加算が要る)
FB = 65536 + 65536        # 1ピクセル1word
ACC = FB + W * H
STATIC = ACC + W * H
TRAIL = STATIC + W * H
PX = TRAIL + W * H
PY = PX + 8192
MEM_WORDS = PY + 8192 + 64
assert STAR + 3 * 16384 <= FB


def rgb(r, g, b):
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


def build_tables(mem):
    for i in range(4096):
        mem[SIN + i] = int(round(4096 * math.sin(2 * math.pi * i / 4096)))
    for n in range(256):
        mem[PAL + n] = rgb(32 + (n * 9 % 224), 60 + (n * 5 % 196), 100 + (n * 3 % 156))
    for i, g in enumerate((130, 165, 200, 165)):
        mem[FLOWPAL + i] = rgb(35, g, 230)
    edges = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    for k, (a, b) in enumerate(edges):
        mem[EDGE + k] = a | (b << 4)
    for i in range(3072):
        mem[RECIP + i] = (1 << 24) // (((i + RECIP_BASE_IDX) << 3) + 4)


def table_py(mem):
    """参照実装用: memoryから読むのではなく同じ表をPython側で持つ(一致はテストで確認)。"""
    return mem


def pack_check(mem):
    return int(mem[SIN:SIN + 4096].sum()), int(mem[RECIP:RECIP + 3072].sum())


# ============================================================ 共通: Bresenham
def bresenham(p, x0, y0, x1, y1, color, alive, bounds, target=FB):
    """float版line()と同じ整数Bresenham。レーンごとに終了を管理するループ。
    bounds=True: pixel() と同じ範囲検査。"""
    dx = p.abs(p.emit('SUB', x1, x0))
    dy = p.neg(p.abs(p.emit('SUB', y1, y0)))
    sx = p.sel(p.lt(x0, x1), 1, -1)
    sy = p.sel(p.lt(y0, y1), 1, -1)
    err = p.emit('ADD', dx, dy)
    x = p.emit('ADD', x0, None)
    y = p.emit('ADD', y0, None)
    al = p.emit('ADD', alive, None)

    def cond():
        return al

    def body(flag):
        addr = p.emit('ADD', p.mul(y, W), x)
        if bounds:
            inb = p.and_(p.ltu(x, W), p.ltu(y, H))
            with p.mask(inb):
                p.store(color, addr, target)
        else:
            p.store(color, addr, target)
        done = p.and_(p.eq(x, x1), p.eq(y, y1))
        e2 = p.shl(err, 1)
        m1 = p.neg(p.ge(e2, dy))
        m2 = p.neg(p.le(e2, dx))
        p.into(err, p.emit('ADD', err, p.and_(dy, m1)))
        p.into(x, p.emit('ADD', x, p.and_(sx, m1)))
        p.into(err, p.emit('ADD', err, p.and_(dx, m2)))
        p.into(y, p.emit('ADD', y, p.and_(sy, m2)))
        p.into(al, p.and_(al, p.xor(done, 1)))

    p.while_any(cond, body)


def line_ref(x0, y0, x1, y1):
    """Bresenham の点列(float版 line() と同じ更新規則)。"""
    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    err = dx + dy
    pts = []
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e = 2 * err
        if e >= dy:
            err += dy
            x0 += sx
        if e <= dx:
            err += dx
            y0 += sy
    return pts


def draw_groups(fbv, jobs, lanes=LANES, bounds=True):
    """jobs: [(x0,y0,x1,y1,color,valid)] を lanes個ずつ群にし、群ごとに『ステップごとレーン順』で描画。"""
    for g in range(0, len(jobs), lanes):
        seqs = []
        for j in jobs[g:g + lanes]:
            seqs.append((line_ref(*j[:4]), j[4]) if j[5] else ([], 0))
        steps = max((len(s[0]) for s in seqs), default=0)
        for t in range(steps):
            for pts, col in seqs:
                if t < len(pts):
                    x, y = pts[t]
                    if not bounds or (0 <= x < W and 0 <= y < H):
                        fbv[y * W + x] = col


# ============================================================ Particles
def hash32_ref(n):
    h = sgn((n + 1) * 0x9E3779B1)
    h = sgn(h ^ ((h & M32) >> 16))
    h = sgn(h * sgn(0x85EBCA6B))
    return sgn(h ^ ((h & M32) >> 13))


def particles_build(feats):
    p = Prog('particles', feats)
    i = p.r1
    frame = p.load(None, PARAM)
    h = p.mul(p.add(i, 1), sgn(0x9E3779B1))
    h = p.xor(h, p.shr(h, 16))
    h = p.mul(h, sgn(0x85EBCA6B))
    h = p.xor(h, p.shr(h, 13))
    ang = p.and_(p.add(p.sar(p.and_(h, 0xFFFF), 4), p.sar(p.mul(frame, 125), 4)), 4095)
    radius = p.add(p.sar(p.mul(p.shr(h, 16), 69), 15), 20)
    rx = p.sar(p.mul(radius, 7), 2)
    c = p.load(p.and_(p.add(ang, 1024), 4095), SIN)
    s = p.load(ang, SIN)
    x = p.add(p.mulq(c, rx), 320)
    y = p.add(p.mulq(s, radius), 180)
    color = p.load(p.and_(i, 255), PAL)
    base = p.add(p.emit('ADD', p.mul(y, W), x), FB)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            p.store(color, base, dy * W + dx)
    return p


def particles_ref(mem, count, frame, lanes=LANES):
    fbv = np.zeros(W * H, dtype=np.int64)
    sinv = mem[SIN:SIN + 4096]
    pal = mem[PAL:PAL + 256]
    pts = []
    for n in range(count):
        h = hash32_ref(n) & M32
        ang = ((((h & 0xFFFF) >> 4) + ((frame * 125) >> 4)) & 4095)
        radius = 20 + (((h >> 16) * 69) >> 15)
        rx = (radius * 7) >> 2
        x = 320 + ((int(sinv[(ang + 1024) & 4095]) * rx) >> 12)
        y = 180 + ((int(sinv[ang]) * radius) >> 12)
        pts.append((x, y, int(pal[n & 255])))
    for g in range(0, count, lanes):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for x, y, col in pts[g:g + lanes]:
                    fbv[(y + dy) * W + x + dx] = col
    return fbv


def particles_run(feats, mem, count, frame):
    mem[PARAM] = frame
    mem[FB:FB + W * H] = 0
    p = particles_build(feats)
    st = Machine(mem, LANES).run(p, count, chunk=1)
    return p, st, mem[FB:FB + W * H].astype(np.int64)


# ============================================================ Galaxy
DR, DB, DX = 180 | (110 << 10) | (50 << 20), 50 | (100 << 10) | (200 << 20), 40 | (70 << 10) | (120 << 20)
BGPACK = 5 | (10 << 10) | (23 << 20)


def galaxy_stars(count):
    """ホスト/初期化ジョブが作る星表。float版 galaxy() の乱数列・Kepler角速度を整数表へ変換する
    (sqrt/exp はここだけ。毎フレームのシェーダには入らない)。"""
    seed = 0x67616c61

    def rnd():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) & M32
        return seed
    rows = []
    for n in range(count):
        u = (rnd() & 65535) / 65535.0
        radius = 8 + math.sqrt(u) * 260
        jitter = ((rnd() & 65535) / 65535.0 - 0.5) * 0.75
        omega = 45.0 / math.sqrt(radius ** 3)
        a0 = radius * 0.031 + (n % 2) * math.pi + jitter
        blue = (seed & 7) > 2
        extra = (seed & 31) == 0
        rows.append((int(radius) | (int(blue) << 9) | (int(extra) << 10),
                     int(a0 / (2 * math.pi) * 4096) & 4095,
                     int(omega / (2 * math.pi) * 4096 * 256)))
    return rows


def galaxy_static():
    """背景+中心グロー(packed R|G<<10|B<<20)。float版の最後の二重ループに対応。"""
    img = np.full(W * H, BGPACK, dtype=np.int64)
    for y in range(-8, 9):
        for x in range(-12, 13):
            a = math.exp(-(x * x + y * y) / 35.0)
            img[(H // 2 + y) * W + W // 2 + x] += int(255 * a) | (int(220 * a) << 10) | (int(150 * a) << 20)
    return img


def galaxy_setup(mem, count):
    for n, (a, b, c) in enumerate(galaxy_stars(count)):
        mem[STAR + 3 * n:STAR + 3 * n + 3] = (a, b, sgn(c))
    mem[STATIC:STATIC + W * H] = galaxy_static()
    mem[ACC:ACC + W * H] = 0


def galaxy_accum_build(feats):
    p = Prog('galaxy_accum', feats)
    i = p.r1
    frame = p.load(None, PARAM)
    a3 = p.mul(i, 3)
    w0, a0, om = p.load(a3, STAR), p.load(a3, STAR + 1), p.load(a3, STAR + 2)
    rad = p.and_(w0, 511)
    blue = p.and_(p.sar(w0, 9), 1)
    extra = p.and_(p.sar(w0, 10), 1)
    ang = p.and_(p.sar(p.emit('ADD', p.shl(a0, 8), p.mul(frame, om)), 8), 4095)
    c = p.load(p.and_(p.add(ang, 1024), 4095), SIN)
    s = p.load(ang, SIN)
    x = p.add(p.mulq(rad, c), 320)
    y = p.add(p.mulq(p.mulq(rad, s), 2130), 180)
    pix = p.add(p.emit('ADD', p.mul(y, W), x), ACC)
    p.atomadd(p.sel(blue, DB, DR), pix, 0)
    with p.mask(extra):
        p.atomadd(p.k(DX), pix, 1)
        p.atomadd(p.k(DX), pix, W)
    return p


def galaxy_final_build(feats):
    p = Prog('galaxy_final', feats)
    i = p.r1
    ai = p.add(i, ACC)
    acc = p.load(ai, 0)
    st = p.load(p.add(i, STATIC), 0)
    tot = p.emit('ADD', acc, st)
    p.store(None, ai, 0)                      # 次フレームのためにaccを自己クリア
    r = p.min(p.and_(tot, 1023), 255)
    g = p.min(p.and_(p.sar(tot, 10), 1023), 255)
    b = p.min(p.and_(p.sar(tot, 20), 1023), 255)
    col = p.shl(p.and_(r, 248), 8)
    col = p.emit('ADD', col, p.shl(p.and_(g, 252), 3))
    col = p.emit('ADD', col, p.sar(b, 3))
    p.store(col, i, FB)
    return p


def galaxy_ref(mem, count, frame):
    sinv = mem[SIN:SIN + 4096]
    acc = np.zeros(W * H, dtype=np.int64)
    st = galaxy_static()
    for n in range(count):
        w0, a0, om = int(mem[STAR + 3 * n]), int(mem[STAR + 3 * n + 1]), int(mem[STAR + 3 * n + 2])
        rad = w0 & 511
        blue, extra = (w0 >> 9) & 1, (w0 >> 10) & 1
        ang = (sgn((a0 << 8) + sgn(frame * om)) >> 8) & 4095
        x = 320 + ((rad * int(sinv[(ang + 1024) & 4095])) >> 12)
        y = 180 + ((((rad * int(sinv[ang])) >> 12) * 2130) >> 12)
        pix = y * W + x
        acc[pix] += DB if blue else DR
        if extra:
            acc[pix + 1] += DX
            acc[pix + W] += DX
    tot = acc + st
    r, g, b = np.minimum(tot & 1023, 255), np.minimum((tot >> 10) & 1023, 255), np.minimum((tot >> 20) & 1023, 255)
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


def galaxy_run(feats, mem, count, frame):
    mem[PARAM] = frame
    pa, pf = galaxy_accum_build(feats), galaxy_final_build(feats)
    s1 = Machine(mem, LANES).run(pa, count)
    s2 = Machine(mem, LANES).run(pf, W * H)
    return (pa, pf), (s1, s2), mem[FB:FB + W * H].astype(np.int64)


# ============================================================ Wire
def wire_layout(count):
    cols = int(math.isqrt(count))
    rows = (count + cols - 1) // cols
    cell = min(W // cols, H // rows)
    return cols, rows, cell, cell * 92 // 100


def wire_setup(mem, count):
    cols, rows, cell, scale = wire_layout(count)
    for n in range(count):
        mem[CUBE + 2 * n] = (n % cols) * W // cols + W // (2 * cols)
        mem[CUBE + 2 * n + 1] = (n // cols) * H // rows + H // (2 * rows)


def wire_xform_build(feats, scale):
    p = Prog('wire_xform', feats)
    n = p.r1
    frame = p.load(None, PARAM)
    idx = p.and_(p.sar(p.emit('ADD', p.mul(frame, 4172), p.mul(n, 28367)), 8), 4095)
    idx2 = p.and_(p.sar(p.mul(idx, 2867), 12), 4095)
    s = p.load(idx, SIN)
    c = p.load(p.and_(p.add(idx, 1024), 4095), SIN)
    s2 = p.load(idx2, SIN)
    c2 = p.load(p.and_(p.add(idx2, 1024), 4095), SIN)
    n2 = p.shl(n, 1)
    cx, cy = p.load(n2, CUBE), p.load(n2, CUBE + 1)
    cps = p.emit('ADD', c, s)
    cms = p.emit('SUB', c, s)
    ncps, ncms = p.neg(cps), p.neg(cms)
    # (x,z)の符号組 -> (xx, zz)   xx=x*c+z*s, zz=-x*s+z*c
    xz = {(1, 1): (cps, cms), (1, -1): (cms, ncps), (-1, 1): (ncms, cps), (-1, -1): (ncps, ncms)}
    sub = {}
    for key, (xx, zz) in xz.items():
        sub[key] = (xx, zz, p.mulq(zz, s2), p.mulq(zz, c2))
    n16 = p.shl(n, 4)
    for v in range(8):
        x = 1 if v & 1 else -1
        y = 1 if v & 2 else -1
        z = 1 if v & 4 else -1
        xx, zz, zs2, zc2 = sub[(x, z)]
        yy = p.emit('SUB', c2 if y > 0 else p.neg(c2), zs2)
        depth = p.add(p.emit('ADD', s2 if y > 0 else p.neg(s2), zc2), 4 * 4096)
        inv = p.load(p.sar(depth, 3), RECIP - RECIP_BASE_IDX)
        px = p.emit('ADD', cx, p.sar(p.mulq(p.mul(xx, scale), inv), 12))
        py = p.emit('ADD', cy, p.sar(p.mulq(p.mul(yy, scale), inv), 12))
        p.store(px, n16, VB + 2 * v)
        p.store(py, n16, VB + 2 * v + 1)
    return p


def wire_edges_build(feats):
    p = Prog('wire_edges', feats)
    e = p.r1
    k = p.and_(e, 15)
    valid = p.lt(k, 12)
    w = p.load(k, EDGE)
    v0 = p.and_(w, 15)
    v1 = p.and_(p.sar(w, 4), 15)
    nb = p.and_(e, -16)
    a0 = p.emit('ADD', nb, p.shl(v0, 1))
    a1 = p.emit('ADD', nb, p.shl(v1, 1))
    x0, y0 = p.load(a0, VB), p.load(a0, VB + 1)
    x1, y1 = p.load(a1, VB), p.load(a1, VB + 1)
    color = p.load(p.and_(p.add(p.sar(e, 4), 12), 255), PAL)
    bresenham(p, x0, y0, x1, y1, color, valid, True)
    return p


def wire_ref(mem, count, frame, scale, lanes=LANES):
    sinv = [int(v) for v in mem[SIN:SIN + 4096]]
    rec = [int(v) for v in mem[RECIP:RECIP + 3072]]
    pal = [int(v) for v in mem[PAL:PAL + 256]]
    edges = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    verts = []
    for n in range(count):
        idx = (sgn(frame * 4172 + n * 28367) >> 8) & 4095
        idx2 = ((idx * 2867) >> 12) & 4095
        s, c, s2, c2 = sinv[idx], sinv[(idx + 1024) & 4095], sinv[idx2], sinv[(idx2 + 1024) & 4095]
        cx, cy = int(mem[CUBE + 2 * n]), int(mem[CUBE + 2 * n + 1])
        pts = []
        for v in range(8):
            x = 1 if v & 1 else -1
            y = 1 if v & 2 else -1
            z = 1 if v & 4 else -1
            xx = x * c + z * s
            zz = -x * s + z * c
            yy = y * c2 - ((zz * s2) >> 12)
            depth = 4 * 4096 + y * s2 + ((zz * c2) >> 12)
            inv = rec[(depth >> 3) - RECIP_BASE_IDX]
            px = cx + ((((xx * scale) * inv) >> 12) >> 12)
            py = cy + ((((yy * scale) * inv) >> 12) >> 12)
            pts.append((px, py))
        verts.append(pts)
    jobs = []
    for n in range(count):
        for k in range(16):
            if k < 12:
                a, b = edges[k]
                jobs.append((*verts[n][a], *verts[n][b], pal[(n + 12) & 255], True))
            else:
                jobs.append((0, 0, 0, 0, 0, False))
    fbv = np.zeros(W * H, dtype=np.int64)
    draw_groups(fbv, jobs, lanes, True)
    return fbv, verts


def wire_run(feats, mem, count, frame):
    cols, rows, cell, scale = wire_layout(count)
    mem[PARAM] = frame
    mem[FB:FB + W * H] = 0
    px, pe = wire_xform_build(feats, scale), wire_edges_build(feats)
    s1 = Machine(mem, LANES).run(px, count)
    s2 = Machine(mem, LANES).run(pe, count * 16, chunk=1)
    return (px, pe), (s1, s2), mem[FB:FB + W * H].astype(np.int64)
