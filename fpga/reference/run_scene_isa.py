"""5シーン(Wire/Particles/Galaxy/Fire/Flow)のISA相当プログラムを実行し、CPU整数参照と全画素比較して
命令数・メモリアクセス数・レジスタ圧・拡張機能の寄与を JSON に書く。

    python fpga/reference/run_scene_isa.py --report fpga/validation/scene-isa-2026-11-04.json
    python fpga/reference/run_scene_isa.py --quick      # 小さい構成だけ(単体試験用)

実機・RTL・合成・配置配線には一切触れない。『命令数』はこの研究ISAのグループ命令数で、
クロック数・fps ではない(演算器RTLの実測サイクルとは未照合)。
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference import scene_isa as I                      # noqa: E402
from reference import scene_isa_scenes as S               # noqa: E402
from reference import scene_isa_fire as FI                # noqa: E402
from reference import scene_isa_flow as FL                # noqa: E402

BASE, FULL = frozenset(), I.FULL
LOADS = (('LIGHT', 0), ('MEDIUM', 1), ('HEAVY', 2))
COUNTS = {'particles': (512, 2048, 8192), 'galaxy': (1024, 4096, 16384), 'wire': (16, 64, 144),
          'flow': (512, 2048, 8192), 'fire_octaves': (2, 4, 6)}


def brief(st):
    keys = ('elements', 'groups', 'group_instr', 'lane_instr', 'loads', 'stores', 'atoms', 'loop_iters')
    d = {k: int(st[k]) for k in keys}
    d['instr_per_element'] = round(st['instr_per_element'], 2)
    d['lane_utilisation'] = round(st['lane_instr'] / max(1, st['group_instr'] * 4), 3)
    return d


def static_total(p):
    """1回通しの静的命令数(プロローグ+直線+ループは1反復分)。拡張機能の寄与比較用。"""
    s = I.static_stats(p)
    return s['prologue'] + s['straight'] + sum(s['loops'])


def prog_info(p):
    s = I.static_stats(p)
    return {'static_total': static_total(p), 'prologue': s['prologue'], 'straight': s['straight'],
            'loop_bodies': s['loops'], 'max_live_vregs': I.max_live(p)}


def micro_tests():
    """基本ISAに展開したマクロ(除算・平方根・64bit積shift・符号なし比較ほか)を拡張命令と照合する。"""
    rng = np.random.default_rng(7)
    n = 2048
    a = rng.integers(-(1 << 30), 1 << 30, n).astype(np.int32)
    b = rng.integers(1, 1 << 15, n).astype(np.int32) * rng.choice([-1, 1], n).astype(np.int32)
    c = rng.integers(0, 1 << 19, n).astype(np.int32)
    results = {}
    checks = {
        'div': lambda p, x, y, z: p.div(x, y, 31),
        'isqrt': lambda p, x, y, z: p.isqrt(z, 19),
        'mulsh16': lambda p, x, y, z: p.mulsh(x, y, 16),
        'ltu': lambda p, x, y, z: p.ltu(x, y),
        'abs': lambda p, x, y, z: p.abs(x),
        'min': lambda p, x, y, z: p.min(x, y),
        'max': lambda p, x, y, z: p.max(x, y),
        'shr7': lambda p, x, y, z: p.shr(x, 7),
        'eq': lambda p, x, y, z: p.eq(x, p.sar(x, 0) if False else y),
        'or': lambda p, x, y, z: p.or_(x, y),
    }
    for name, fn in checks.items():
        outs = []
        for feats in (BASE, FULL):
            mem = I.new_memory(4 * n + 8)
            mem[0:n], mem[n:2 * n], mem[2 * n:3 * n] = a, b, c
            p = I.Prog(name, feats)
            i = p.r1
            x, y, z = p.load(i, 0), p.load(i, n), p.load(i, 2 * n)
            p.store(fn(p, x, y, z), i, 3 * n)
            I.Machine(mem, 4).run(p, n)
            outs.append(mem[3 * n:4 * n].copy())
        ok = bool((outs[0] == outs[1]).all())
        ref = None
        if name == 'div':
            ref = np.array([abs(int(x)) // abs(int(y)) * (1 if (x < 0) == (y < 0) else -1) for x, y in zip(a, b)])
        if name == 'isqrt':
            ref = np.array([int(v) ** 0.5 // 1 for v in c]).astype(np.int64)
        if name == 'mulsh16':
            ref = np.array([(int(x) * int(y)) >> 16 for x, y in zip(a, b)])
            ref = ((ref + (1 << 31)) % (1 << 32)) - (1 << 31)
        if ref is not None:
            ok = ok and bool((outs[1].astype(np.int64) == ref).all())
        results[name] = ok
    return results


def run_fire(octaves, rows=None):
    out = {}
    t = time.time()
    ref = FI.reference(17, octaves, rows)
    out['reference_seconds'] = round(time.time() - t, 1)
    for tag, feats in (('base', BASE), ('ext', FULL)):
        p, st, img = FI.run(feats, octaves, 17, rows)
        out[tag] = {'program': prog_info(p), 'run': brief(st), 'mismatch_pixels': int((img != ref).sum())}
    out['pixels'] = int(len(ref))
    return out


def run_particles(count, frame=7):
    out = {}
    mem = I.new_memory(S.MEM_WORDS)
    S.build_tables(mem)
    ref = S.particles_ref(mem, count, frame)
    for tag, feats in (('base', BASE), ('ext', FULL)):
        p, st, img = S.particles_run(feats, mem, count, frame)
        out[tag] = {'program': prog_info(p), 'run': brief(st), 'mismatch_pixels': int((img != ref).sum())}
    out['drawn_pixels'] = int(np.count_nonzero(ref))
    return out


def run_galaxy(count, frame=5):
    out = {}
    mem = I.new_memory(S.MEM_WORDS)
    S.build_tables(mem)
    S.galaxy_setup(mem, count)
    ref = S.galaxy_ref(mem, count, frame)
    (pa, pf), (s1, s2), img = S.galaxy_run(FULL, mem, count, frame)
    out['ext'] = {'accum': {'program': prog_info(pa), 'run': brief(s1)},
                  'final': {'program': prog_info(pf), 'run': brief(s2)}, 'mismatch_pixels': int((img != ref).sum())}
    try:
        S.galaxy_accum_build(BASE)
        out['base'] = 'built'
    except I.Unsupported as e:
        out['base'] = 'Unsupported: %s' % e
    out['base_final'] = {'program': prog_info(S.galaxy_final_build(BASE))}
    mem[S.ACC:S.ACC + S.W * S.H] = 0
    return out


def run_wire(count, frame=3):
    out = {}
    mem = I.new_memory(S.MEM_WORDS)
    S.build_tables(mem)
    S.wire_setup(mem, count)
    scale = S.wire_layout(count)[3]
    ref, _ = S.wire_ref(mem, count, frame, scale)
    for tag, feats in (('base', BASE), ('ext', FULL)):
        (px, pe), (s1, s2), img = S.wire_run(feats, mem, count, frame)
        out[tag] = {'xform': {'program': prog_info(px), 'run': brief(s1)},
                    'edges': {'program': prog_info(pe), 'run': brief(s2)},
                    'mismatch_pixels': int((img != ref).sum())}
    out['drawn_pixels'] = int(np.count_nonzero(ref))
    return out


def run_flow(count, frames, start_frame=0):
    out = {}
    mem = I.new_memory(S.MEM_WORDS)
    S.build_tables(mem)
    FL.flow_init(mem, count)
    mem2 = mem.copy()
    for k in FL.COVER:
        FL.COVER[k] = 0
    mism = 0
    stats = None
    for fr in range(start_frame, start_frame + frames):
        ps, stats, img = FL.run_frame(FULL, mem, count, fr)
        FL.flow_params(mem2, fr)
        ref = FL.step_ref(mem2, count, fr)
        mism += int((img != ref).sum()) + int((mem[S.PX:S.PX + count] != mem2[S.PX:S.PX + count]).sum())
    names = ('decay', 'particles', 'present', 'obstacle')
    out['ext'] = {n: {'program': prog_info(p), 'run': brief(s)} for n, p, s in zip(names, ps, stats)}
    out['mismatch_pixels_and_state'] = mism
    out['frames_checked'] = frames
    out['coverage'] = dict(FL.COVER)
    base_ps = [FL.decay_build(BASE), FL.particles_build(BASE), FL.present_build(BASE), FL.obstacle_build(BASE)]
    out['base_static'] = {n: prog_info(p) for n, p in zip(names, base_ps)}
    return out


def ablation():
    """各機能をFULLから1つだけ外したときの静的命令数の増分(ループは1反復分)。"""
    builders = {
        'fire(oct4)': lambda f: FI.build(f, 4),
        'particles': S.particles_build,
        'galaxy_accum': S.galaxy_accum_build,
        'galaxy_final': S.galaxy_final_build,
        'wire_xform': lambda f: S.wire_xform_build(f, 27),
        'wire_edges': S.wire_edges_build,
        'flow_decay': FL.decay_build,
        'flow_particles': FL.particles_build,
        'flow_obstacle': FL.obstacle_build,
    }
    table = {}
    for name, b in builders.items():
        full = static_total(b(FULL))
        row = {'full': full}
        for f in I.FEATURES:
            try:
                row[f] = static_total(b(FULL - {f})) - full
            except I.Unsupported:
                row[f] = None            # その機能なしでは表現不可
        try:
            row['base'] = static_total(b(BASE))
        except I.Unsupported:
            row['base'] = None
        table[name] = row
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report')
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--fire-octaves', type=int, default=4)
    a = ap.parse_args()
    rep = {'date': '2026-11-04', 'scope': 'offline ISA-level evaluation; no hardware, no RTL', 'lanes': S.LANES}
    t0 = time.time()
    rep['micro_tests'] = micro_tests()
    print('micro', rep['micro_tests'], flush=True)
    quick = a.quick
    rep['fire'] = {}
    for o in ((2,) if quick else COUNTS['fire_octaves']):
        rows = 8 if (quick or o != a.fire_octaves) else None
        rep['fire']['octaves%d' % o] = run_fire(o, rows)
        print('fire', o, rep['fire']['octaves%d' % o]['ext']['run']['instr_per_element'], rep['fire']['octaves%d' % o]['ext']['mismatch_pixels'], flush=True)
    for name, fn, counts in (('particles', run_particles, COUNTS['particles']), ('galaxy', run_galaxy, COUNTS['galaxy']),
                             ('wire', run_wire, COUNTS['wire'])):
        rep[name] = {}
        for (ln, li), cnt in zip(LOADS, counts):
            if quick and li:
                continue
            rep[name][ln] = dict(count=cnt, **fn(cnt))
            print(name, ln, 'ok', flush=True)
    rep['flow'] = {}
    plan = ((('LIGHT', 512, 8),) if quick else (('LIGHT', 512, 12), ('MEDIUM', 2048, 2), ('HEAVY', 8192, 1)))
    for ln, cnt, frames in plan:
        rep['flow'][ln] = dict(count=cnt, **run_flow(cnt, frames, 0 if ln == 'LIGHT' else 40))
        print('flow', ln, rep['flow'][ln]['mismatch_pixels_and_state'], rep['flow'][ln]['coverage'], flush=True)
    rep['ablation'] = ablation()
    rep['features'] = I.FEATURES
    rep['elapsed_seconds'] = round(time.time() - t0, 1)
    bad = []

    def scan(node, path=''):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ('mismatch_pixels', 'base_mismatch_pixels', 'mismatch_pixels_and_state') and v:
                    bad.append(path + '/' + k)
                scan(v, path + '/' + k)
    scan(rep)
    rep['all_match'] = not bad and all(rep['micro_tests'].values())
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print('ALL MATCH' if rep['all_match'] else 'MISMATCH %s' % bad, rep['elapsed_seconds'], 's')
    return 0 if rep['all_match'] else 1


if __name__ == '__main__':
    sys.exit(main())
