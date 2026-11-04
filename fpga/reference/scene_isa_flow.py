"""Flow (円柱後流 + 粒子トレイル) を汎用SIMD ISAプログラムとして書く。整数シーン定義g1。
float版 lab.cpp FlowState との違い: 座標Q12/速度Q12、渦位置・強度は毎フレームホストが計算して
PARAMへ置く、乱数は粒子番号・フレーム・サブステップのstateless hash、%演算は乗算shiftに置換、
障害物中心は整数(269,180)、色はn&3の4色表。"""
import math
import numpy as np
from .scene_isa import Prog, Machine, new_memory, sgn, M32
from .scene_isa_scenes import (W, H, LANES, PARAM, SIN, FLOWPAL, FB, TRAIL, PX, PY, rgb,
                               bresenham, draw_groups)

CX4, CY4 = 269 * 16, 180 * 16            # 障害物中心 (Q4 px)
CX12, CY12 = 269 << 12, 180 << 12        # Q12 px
R2 = (34 * 16) ** 2                      # R^2 (Q8)
RR1 = 35 * 16                            # 半径+1 (Q4)


COVER = {'respawn': 0, 'obstacle': 0, 'vortex': 0, 'substeps': 0}


def idiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def flow_params(mem, frame):
    """渦4本の位置・回転強度。フレームごとの定数なのでホストが計算して PARAM[16..] へ置く。"""
    mem[PARAM] = frame
    ph = (frame * 4172) >> 8
    for k in range(4):
        sg = 1 if k % 2 else -1
        amp = 26 + ((10 * int(mem[SIN + ((ph + 652 * k) & 4095)])) >> 12)
        sp = sg * (100 + ((30 * int(mem[SIN + ((((ph * 3277) >> 12) + 652 * k) & 4095)])) >> 12))
        mem[PARAM + 16 + 3 * k:PARAM + 19 + 3 * k] = ((269 + 70 + 76 * k) * 16, (180 + sg * amp) * 16, sp)


def flow_init(mem, count):
    seed = 0x666c6f77
    for n in range(count):
        seed = (seed * 1664525 + 1013904223) & M32
        x = seed % W
        seed = (seed * 1664525 + 1013904223) & M32
        y = seed % H
        mem[PX + n], mem[PY + n] = x << 12, y << 12
    mem[TRAIL:TRAIL + W * H] = 0
    mem[FB:FB + W * H] = 0


def vel_ref(ex, ey, vort):
    dx, dy = ex - CX4, ey - CY4
    dx2, dy2 = dx * dx, dy * dy
    rr = max(dx2 + dy2, R2)
    k = idiv(R2 << 12, rr)
    q = idiv(((dx2 - dy2) >> 9) << 12, rr >> 9)
    vx = (13107 * (4096 - ((k * q) >> 12))) >> 12
    q2 = idiv(((dx * dy) >> 9) << 12, rr >> 9)
    vy = -((26214 * ((k * q2) >> 12)) >> 12)
    if CX4 < ex:
        COVER['vortex'] += 1
        for vx4, vy4, spin in vort:
            rx, ry = ex - vx4, ey - vy4
            den = (((rx * rx) + (ry * ry)) >> 8) + 350
            w = idiv(spin << 12, den)
            vx -= (ry * w) >> 4
            vy += (rx * w) >> 4
    return vx, vy


def respawn_ref(n, frame, sub):
    h = sgn(n * sgn(0x9E3779B1) + frame * sgn(0x85EBCA6B) + sgn((sub + 1) * 0xC2B2AE35))
    h = sgn(h ^ ((h & M32) >> 15))
    h = sgn(h * 0x2C1B3C6D)
    h = sgn(h ^ ((h & M32) >> 12)) & M32
    return (((h & 0xFFFF) * 12) >> 16) << 12, ((((h >> 16) & 0xFFFF) * 360) >> 16) << 12


def substep_ref(px, py, vort):
    ax, ay = vel_ref(px >> 8, py >> 8, vort)
    mx, my = px + (ax >> 2), py + (ay >> 2)
    bx, by = vel_ref(mx >> 8, my >> 8, vort)
    nx, ny = px + (bx >> 1), py + (by >> 1)
    dxn, dyn = nx - CX12, ny - CY12
    d2 = (dxn >> 8) ** 2 + (dyn >> 8) ** 2
    COVER['substeps'] += 1
    if d2 < RR1 * RR1:
        COVER['obstacle'] += 1
        dist = max(math.isqrt(d2), 1)
        nx, ny = CX12 + idiv(dxn * RR1, dist), CY12 + idiv(dyn * RR1, dist)
    inb = 0 <= nx < (W << 12) and 0 <= ny < (H << 12)
    return nx, ny, inb


def step_ref(mem, count, frame, lanes=LANES):
    """1フレーム: 減衰→粒子→(コピー+障害物)。memのPX/PY/TRAILを更新し、表示面を返す。"""
    trail = mem[TRAIL:TRAIL + W * H].astype(np.int64)
    r, g, b = trail >> 11, (trail >> 5) & 63, trail & 31
    trail = (((r * 29) >> 5) << 11) | (((g * 29) >> 5) << 5) | ((b * 29) >> 5)
    vort = [tuple(int(v) for v in mem[PARAM + 16 + 3 * k:PARAM + 19 + 3 * k]) for k in range(4)]
    pal = [int(v) for v in mem[FLOWPAL:FLOWPAL + 4]]
    head = rgb(140, 235, 255)
    for g0 in range(0, count, lanes):
        ids = list(range(g0, min(count, g0 + lanes)))
        st = {n: [int(mem[PX + n]), int(mem[PY + n]), True] for n in ids}
        for sub in range(2):
            jobs = []
            for n in ids:
                px, py, alive = st[n]
                if not alive:
                    jobs.append((0, 0, 0, 0, 0, False))
                    continue
                nx, ny, inb = substep_ref(px, py, vort)
                if not inb:
                    COVER['respawn'] += 1
                    st[n][0], st[n][1] = respawn_ref(n, frame, sub)
                    st[n][2] = False
                    jobs.append((0, 0, 0, 0, 0, False))
                else:
                    jobs.append((px >> 12, py >> 12, nx >> 12, ny >> 12, pal[n & 3], True))
                    st[n][0], st[n][1] = nx, ny
            draw_groups(trail, jobs, lanes, False)
        for n in ids:
            trail[(st[n][1] >> 12) * W + (st[n][0] >> 12)] = head
            mem[PX + n], mem[PY + n] = st[n][0], st[n][1]
    mem[TRAIL:TRAIL + W * H] = trail
    fbv = trail.copy()
    for y in range(145, 216):
        for x in range(233, 304):
            d = (x - 269) ** 2 + (y - 180) ** 2
            if d < 34 * 34:
                fbv[y * W + x] = rgb(255, 175, 100) if d > 32 * 32 else rgb(22, 31, 48)
    return fbv


def decay_build(feats):
    p = Prog('flow_decay', feats)
    ai = p.add(p.r1, TRAIL)
    v = p.load(ai, 0)
    r = p.sar(p.mul(p.sar(v, 11), 29), 5)
    g = p.sar(p.mul(p.and_(p.sar(v, 5), 63), 29), 5)
    b = p.sar(p.mul(p.and_(v, 31), 29), 5)
    col = p.emit('ADD', p.shl(r, 11), p.shl(g, 5))
    col = p.emit('ADD', col, b)
    p.store(col, ai, 0)
    return p


def present_build(feats):
    p = Prog('flow_present', feats)
    v = p.load(p.add(p.r1, TRAIL), 0)
    p.store(v, p.add(p.r1, FB), 0)
    return p


def obstacle_build(feats):
    p = Prog('flow_obstacle', feats)
    e = p.r1
    dxi, dyi = p.and_(e, 127), p.sar(e, 7)
    valid = p.and_(p.lt(dxi, 71), p.lt(dyi, 71))
    dx, dy = p.add(dxi, 233 - 269), p.add(dyi, 145 - 180)
    d = p.emit('ADD', p.mul(dx, dx), p.mul(dy, dy))
    hit = p.and_(valid, p.lt(d, 34 * 34))
    ring = p.lt(32 * 32, d)
    col = p.sel(ring, rgb(255, 175, 100), rgb(22, 31, 48))
    addr = p.add(p.emit('ADD', p.mul(p.add(dyi, 145), W), p.add(dxi, 233)), FB)
    with p.mask(hit):
        p.store(col, addr, 0)
    return p


def particles_build(feats):
    p = Prog('flow_particles', feats)
    i = p.r1
    frame = p.load(None, PARAM)
    vort = [tuple(p.load(None, PARAM + 16 + 3 * k + j) for j in range(3)) for k in range(4)]
    pxa, pya = p.add(i, PX), p.add(i, PY)
    px, py = p.load(pxa, 0), p.load(pya, 0)
    pal = p.load(p.and_(i, 3), FLOWPAL)
    head = p.k(rgb(140, 235, 255))

    def vel(ex, ey):
        dx, dy = p.add(ex, -CX4), p.add(ey, -CY4)
        dx2, dy2 = p.mul(dx, dx), p.mul(dy, dy)
        rr = p.max(p.emit('ADD', dx2, dy2), R2)
        rr9 = p.sar(rr, 9)
        k = p.div(p.k(R2 << 12), rr, 31)
        q = p.div(p.shl(p.sar(p.emit('SUB', dx2, dy2), 9), 12), rr9, 30)
        vx = p.mulq(p.k(13107), p.emit('SUB', p.k(4096), p.mulq(k, q)))
        q2 = p.div(p.shl(p.sar(p.mul(dx, dy), 9), 12), rr9, 30)
        vy = p.neg(p.mulq(p.k(26214), p.mulq(k, q2)))
        m = p.lt(CX4, ex)
        with p.mask(m):
            for vx4, vy4, spin in vort:
                rx, ry = p.emit('SUB', ex, vx4), p.emit('SUB', ey, vy4)
                den = p.add(p.sar(p.emit('ADD', p.mul(rx, rx), p.mul(ry, ry)), 8), 350)
                w = p.div(p.shl(spin, 12), den, 20)
                p.into(vx, p.emit('SUB', vx, p.sar(p.mul(ry, w), 4)))
                p.into(vy, p.emit('ADD', vy, p.sar(p.mul(rx, w), 4)))
        return vx, vy

    def substep(sub):
        ax, ay = vel(p.sar(px, 8), p.sar(py, 8))
        mx, my = p.emit('ADD', px, p.sar(ax, 2)), p.emit('ADD', py, p.sar(ay, 2))
        bx, by = vel(p.sar(mx, 8), p.sar(my, 8))
        nx = p.emit('ADD', px, p.sar(bx, 1))
        ny = p.emit('ADD', py, p.sar(by, 1))
        dxn, dyn = p.add(nx, -CX12), p.add(ny, -CY12)
        dq, eq_ = p.sar(dxn, 8), p.sar(dyn, 8)
        d2 = p.emit('ADD', p.mul(dq, dq), p.mul(eq_, eq_))
        inside = p.lt(d2, RR1 * RR1)
        with p.mask(inside):
            dist = p.max(p.isqrt(d2, 19), 1)
            p.into(nx, p.add(p.div(p.mul(dxn, RR1), dist, 27), CX12))
            p.into(ny, p.add(p.div(p.mul(dyn, RR1), dist, 27), CY12))
        inb = p.and_(p.ltu(nx, W << 12), p.ltu(ny, H << 12))
        out = p.xor(inb, 1)
        with p.mask(out):
            h = p.emit('ADD', p.mul(i, sgn(0x9E3779B1)), p.mul(frame, sgn(0x85EBCA6B)))
            h = p.add(h, sgn((sub + 1) * 0xC2B2AE35))
            h = p.xor(h, p.shr(h, 15))
            h = p.mul(h, 0x2C1B3C6D)
            h = p.xor(h, p.shr(h, 12))
            p.into(px, p.shl(p.sar(p.mul(p.and_(h, 0xFFFF), 12), 16), 12))
            p.into(py, p.shl(p.sar(p.mul(p.shr(h, 16), 360), 16), 12))
        with p.mask(inb):
            bresenham(p, p.sar(px, 12), p.sar(py, 12), p.sar(nx, 12), p.sar(ny, 12), pal, inb, False, TRAIL)
            p.into(px, p.emit('ADD', nx, None))
            p.into(py, p.emit('ADD', ny, None))
        return inb

    alive = substep(0)
    with p.mask(alive):
        substep(1)
    addr = p.add(p.emit('ADD', p.mul(p.sar(py, 12), W), p.sar(px, 12)), TRAIL)
    p.store(head, addr, 0)
    p.store(px, pxa, 0)
    p.store(py, pya, 0)
    return p


def run_frame(feats, mem, count, frame):
    flow_params(mem, frame)
    ps = [decay_build(feats), particles_build(feats), present_build(feats), obstacle_build(feats)]
    stats = [Machine(mem, LANES).run(ps[0], W * H),
             Machine(mem, LANES).run(ps[1], count, chunk=1),
             Machine(mem, LANES).run(ps[2], W * H),
             Machine(mem, LANES).run(ps[3], 128 * 80)]
    return ps, stats, mem[FB:FB + W * H].astype(np.int64)
