"""Compile the track-l-scenes DSL programs for compute_simd v2 and run them on
model.py (and, with --rtl, on the Verilog core), comparing with the CPU integer
references from fpga/reference. Offline; no hardware."""

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from backend import FEATS, compile_prog, ROOT   # noqa: E402
sys.path.insert(0, str(HERE.parent))
from model import execute, signed               # noqa: E402
import numpy as np                              # noqa: E402
from fpga.reference import scene_isa as I       # noqa: E402
from fpga.reference import scene_isa_scenes as S   # noqa: E402

SPILL_BASE = 1 << 19        # above every scene buffer used here (FB..ACC.. < 2^19 for 640x360 FB)
LANES = 4
PC_BITS = 12


def run_model(words, mem, count, lanes=LANES, spill_base=SPILL_BASE, nslots=1, base=0):
    size = spill_base + (count + lanes) * nslots + 16
    memory = [int(x) for x in mem] + [0] * (size - len(mem))
    res = execute(words, memory, lanes=lanes, base=base, elements=count, budget=10 ** 9, words=1 << PC_BITS)
    return res


def particles(count, frame):
    mem = I.new_memory(S.MEM_WORDS)
    S.build_tables(mem)
    mem[S.PARAM] = frame
    ref = S.particles_ref(mem, count, frame)
    prog = S.particles_build(FEATS)
    comp = compile_prog(prog, SPILL_BASE)
    return mem, ref, comp


def rtl_check(name, comp, mem, count, res, spill_base, lanes=LANES, out=None, iverilog='iverilog', vvp='vvp', base=0):
    """Run the compiled program on compute_simd (Verilog) and compare memory, registers, requests."""
    sys.path.insert(0, str(HERE.parent / 'tests'))
    import run_compute as RC
    out = Path(out)
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    memw = spill_base + (count + lanes) * comp['nslots'] + 16
    words = comp['words']
    rtl = HERE.parent / 'rtl/compute_simd.v'
    bench = HERE.parent / 'tests/tb_compute_simd.v'
    exe = d / 'sim.vvp'
    tracew = max(4096, len(res.requests) + 16)
    RC.run_tool([iverilog, '-g2012', '-s', 'tb_compute_simd', f'-Ptb_compute_simd.LANES={lanes}',
                 f'-Ptb_compute_simd.PCB={PC_BITS}', f'-Ptb_compute_simd.MEMW={memw}',
                 f'-Ptb_compute_simd.TRACEW={tracew}', '-Ptb_compute_simd.MAXTICKS=200000000',
                 '-o', str(exe), str(rtl), str(bench)], check=True)
    inp = [int(x) for x in mem] + [0] * (memw - len(mem))
    RC.hexfile(d / 'program.hex', words, 1 << PC_BITS)
    RC.hexfile(d / 'present.hex', [1] * len(words), 1 << PC_BITS)
    RC.hexfile(d / 'input.hex', inp)
    RC.hexfile(d / 'expected.hex', res.memory[:memw])
    RC.hexfile(d / 'registers.hex', [x for r in res.registers for x in r])
    for i, f in enumerate(('write', 'addr', 'data', 'mask')):
        RC.hexfile(d / f'trace_{f}.hex', [x[i] for x in res.requests], tracew)
    cmd = [vvp, str(exe), f'+directory={d.as_posix()}', f'+program_words={len(words)}', f'+base={base}', '+entry=0',
           '+budget=100000000', '+fault=-1', '+stall=0', f'+error={res.error}',
           f'+instructions={res.instructions}', f'+requests={len(res.requests)}',
           f'+elements={count}', f'+groups={res.groups}']
    t = time.time()
    done = RC.run_tool(cmd, capture_output=True, text=True, timeout=3600)
    if done.returncode:
        raise RuntimeError(f'{name}: RTL mismatch\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}')
    import re
    m = re.findall(r'PASS run=(\d+) lanes=(\d+) cycles=(\d+) instructions=(\d+) requests=(\d+)', done.stdout)
    return dict(rtl_cycles=int(m[0][2]), rtl_runs=len(m), rtl_seconds=round(time.time() - t, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rtl', action='store_true')
    ap.add_argument('--iverilog', default='iverilog')
    ap.add_argument('--vvp', default='vvp')
    ap.add_argument('--output', type=Path, default=ROOT / 'fpga/build/scenes')
    ap.add_argument('--report', type=Path)
    ap.add_argument('--scenes', default='particles')
    args = ap.parse_args()
    report = {}
    for scene in args.scenes.split(','):
        report[scene] = RUN[scene](args)
        print(scene, json.dumps(report[scene]), flush=True)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')


def finish(args, name, comp, mem, ref, count, res, base_addr, size, spill_base):
    got = np.array(res.memory[base_addr:base_addr + size], dtype=np.int64)
    out = dict(count=count, program_words=comp['instructions'], spill_slots=comp['nslots'],
               backend=comp['stats'], model_error=res.error, model_instructions=res.instructions,
               groups=res.groups, memory_requests=len(res.requests),
               mismatch_pixels=int((got != ref).sum()), drawn_pixels=int(np.count_nonzero(ref)))
    assert res.error == 0 and out['mismatch_pixels'] == 0, out
    if args.rtl:
        out.update(rtl_check(name, comp, mem, count, res, spill_base, out=args.output,
                             iverilog=args.iverilog, vvp=args.vvp))
    return out


def stage(args, name, build, mem, count, base=0, spill_base=None, check=None, rtl=True):
    """One DSL program: compare (1) the DSL numpy simulator, (2) the compiled program on model.py,
    (3) optionally the Verilog core. `check(mem_after)` compares with a CPU reference."""
    spill_base = spill_base or ((len(mem) + 4095) // 4096 * 4096)
    prog = build()
    memA = mem.copy()
    t = time.time()
    st = I.Machine(memA, LANES).run(prog, count, chunk=1, group_base=base)
    t_dsl = time.time() - t
    comp = compile_prog(prog, spill_base)
    t = time.time()
    res = run_model(comp['words'], mem, count, nslots=comp['nslots'], spill_base=spill_base, base=base)
    t_model = time.time() - t
    after = np.array(res.memory[:len(mem)], dtype=np.int64)
    out = dict(elements=count, group_base=base, program_words=comp['instructions'], spill_slots=comp['nslots'],
               backend=comp['stats'], model_error=res.error, model_instructions=res.instructions,
               groups=res.groups, memory_requests=len(res.requests),
               dsl_group_instr=st['group_instr'], dsl_loads=st['loads'], dsl_stores=st['stores'], dsl_atoms=st['atoms'],
               dsl_vs_isa_mismatch_words=int((after != memA.astype(np.int64)).sum()),
               model_seconds=round(t_model, 1))
    if check is not None:
        out['reference_mismatch'] = int(check(after))
    assert res.error == 0 and out['dsl_vs_isa_mismatch_words'] == 0 and out.get('reference_mismatch', 0) == 0, out
    if args.rtl and rtl:
        out.update(rtl_check(name, comp, mem, count, res, spill_base, out=args.output,
                             iverilog=args.iverilog, vvp=args.vvp, base=base))
    mem[:] = after.astype(mem.dtype)          # next stage sees this stage's result
    return out


def fresh():
    mem = I.new_memory(S.MEM_WORDS)
    S.build_tables(mem)
    return mem


def sc_particles(args, count=16, frame=7):
    mem = fresh()
    mem[S.PARAM] = frame
    ref = S.particles_ref(mem, count, frame)
    return {'particles': stage(args, 'particles', lambda: S.particles_build(FEATS), mem, count,
                               check=lambda m: (m[S.FB:S.FB + S.W * S.H] != ref).sum())}


def sc_wire(args, count=4, frame=3):
    mem = fresh()
    S.wire_setup(mem, count)
    scale = S.wire_layout(count)[3]
    mem[S.PARAM] = frame
    ref, _ = S.wire_ref(mem, count, frame, scale)
    out = {'xform': stage(args, 'wire-xform', lambda: S.wire_xform_build(FEATS, scale), mem, count)}
    out['edges'] = stage(args, 'wire-edges', lambda: S.wire_edges_build(FEATS), mem, count * 16,
                         check=lambda m: (m[S.FB:S.FB + S.W * S.H] != ref).sum())
    return out


def sc_galaxy(args, count=8, frame=5):
    mem = fresh()
    S.galaxy_setup(mem, count)
    mem[S.PARAM] = frame
    ref = S.galaxy_ref(mem, count, frame)
    out = {'accum': stage(args, 'galaxy-accum', lambda: S.galaxy_accum_build(FEATS), mem, count)}
    acc = mem[S.ACC:S.ACC + S.W * S.H]
    rows = np.nonzero(acc.reshape(S.H, S.W).any(axis=1))[0]
    y0, y1 = int(rows.min()), int(rows.max()) + 1
    n = (y1 - y0) * S.W
    out['final'] = stage(args, 'galaxy-final', lambda: S.galaxy_final_build(FEATS), mem, n, base=y0 * S.W,
                         check=lambda m: (m[S.FB + y0 * S.W:S.FB + y1 * S.W] != ref[y0 * S.W:y1 * S.W]).sum())
    out['final']['window_rows'] = [y0, y1]
    return out


def sc_fire(args, octaves=4, rows=1, frame=17):
    from fpga.reference import scene_isa_fire as FI
    mem = I.new_memory(FI.FB + FI.W * FI.H)
    mem[FI.PARAM] = frame
    ref = FI.reference(frame, octaves, rows)
    n = FI.W * rows
    return {'fire': stage(args, 'fire', lambda: FI.build(FEATS, octaves), mem, n,
                          check=lambda m: ((m[FI.FB:FI.FB + n] & 0xFFFF) != ref).sum())}


def sc_flow(args, count=8, frame=0):
    from fpga.reference import scene_isa_flow as FL
    mem = fresh()
    FL.flow_init(mem, count)
    mem2 = mem.copy()
    FL.flow_params(mem, frame)
    FL.flow_params(mem2, frame)
    ref = FL.step_ref(mem2, count, frame)
    npx = S.W * S.H
    rtl_mem = mem.copy()
    out = {}
    out['decay'] = stage(args, 'flow-decay', lambda: FL.decay_build(FEATS), mem, npx, rtl=False)
    out['particles'] = stage(args, 'flow-particles', lambda: FL.particles_build(FEATS), mem, count)
    out['present'] = stage(args, 'flow-present', lambda: FL.present_build(FEATS), mem, npx, rtl=False)
    out['obstacle'] = stage(args, 'flow-obstacle', lambda: FL.obstacle_build(FEATS), mem, 128 * 80,
                            check=lambda m: (m[S.FB:S.FB + npx] != ref).sum() + (m[S.PX:S.PX + count] != mem2[S.PX:S.PX + count]).sum())
    if args.rtl:
        # RTL on windows of the full-frame stages (compared with the DSL simulator)
        for name, build in (('decay', FL.decay_build), ('present', FL.present_build)):
            out[name + '_rtl_window'] = stage(args, 'flow-%s-window' % name, lambda: build(FEATS), rtl_mem, 2048, base=0)
    return out


RUN = {'particles': sc_particles, 'wire': sc_wire, 'galaxy': sc_galaxy, 'fire': sc_fire, 'flow': sc_flow}

if __name__ == '__main__':
    main()
