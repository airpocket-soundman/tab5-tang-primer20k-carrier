"""Generate deterministic cycle vectors and a self-checking Verilog bench.

Host execution verifies the reference model only; it does not simulate RTL.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("compute_reference", ROOT / "reference/compute_reference.py")
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)


def generate():
    state = dict(accumulator=0, result=0, result_valid=0, error=0, active=0)
    vectors = []

    def cycle(**kwargs):
        ins = dict(reset=0, begin_valid=0, bias=0, mac_valid=0,
                   activation=0, zero_point=0, weight=0, end_valid=0, result_ready=0)
        ins.update(kwargs)
        ready = dict(begin_ready=int(not state['active'] and not state['result_valid'] and not state['error']),
                     mac_ready=int(state['active'] and not state['error']),
                     end_ready=int(state['active'] and not state['error'] and not ins['mac_valid']))
        if ins['reset']:
            state.update(accumulator=0, result=0, result_valid=0, error=0, active=0)
        else:
            if state['result_valid'] and ins['result_ready']:
                state['result_valid'] = 0
            if ins['begin_valid'] and ready['begin_ready']:
                state.update(accumulator=gold.checked_i32(ins['bias']), active=1)
            elif ins['mac_valid'] and ready['mac_ready']:
                try:
                    value = gold.tiled_gemm([[ins['activation']]], [[ins['weight']]],
                                            [state['accumulator']], ins['zero_point'])[0][0]
                    state['accumulator'] = value
                except OverflowError:
                    state.update(error=1, active=0)
            elif ins['end_valid'] and ready['end_ready']:
                state.update(result=state['accumulator'], result_valid=1, active=0)
        vectors.append(dict(inputs=ins, ready=ready, expected=state.copy()))

    cycle(reset=1, begin_valid=1, mac_valid=1, end_valid=1)
    cycle(begin_valid=1, bias=7)
    cycle(mac_valid=1, activation=127, zero_point=-128, weight=-128)
    cycle()  # input bubble
    cycle(mac_valid=1, activation=-128, zero_point=127, weight=-128, end_valid=1)
    cycle(end_valid=1)
    for _ in range(3):
        cycle(begin_valid=1, bias=99, mac_valid=1, activation=4, weight=5)
    cycle(begin_valid=1, bias=99, result_ready=1)  # no same-cycle replacement
    cycle(begin_valid=1, bias=-23)
    cycle(end_valid=1)  # empty job
    cycle(result_ready=1)
    for bias, weight in [(gold.INT32_MAX, 1), (gold.INT32_MIN, -1)]:
        cycle(begin_valid=1, bias=bias)
        cycle(mac_valid=1, activation=1, weight=weight)
        cycle(begin_valid=1, bias=0, mac_valid=1, weight=1, end_valid=1, result_ready=1)
        cycle(reset=1)
    rng = random.Random(20261022)
    for _ in range(20):
        cycle(begin_valid=1, bias=rng.randint(-10000, 10000))
        for _ in range(rng.randrange(1, 12)):
            cycle(mac_valid=1, activation=rng.randint(-128, 127),
                  zero_point=rng.randint(-128, 127), weight=rng.randint(-128, 127))
        cycle(end_valid=1)
        cycle()
        cycle(result_ready=1)
    cycle(begin_valid=1, bias=42)
    cycle(reset=1, end_valid=1)  # reset aborts active job
    cycle(begin_valid=1, bias=43)
    cycle(end_valid=1)
    cycle(reset=1, result_ready=1)  # reset drops pending result
    return vectors


def literal(value, width):
    return f"{width}'h{value & ((1 << width) - 1):x}"


def testbench(vectors):
    inputs = dict(reset=1, begin_valid=1, bias=32, mac_valid=1, activation=8,
                  zero_point=8, weight=8, end_valid=1, result_ready=1)
    outputs = dict(begin_ready=1, mac_ready=1, end_ready=1, result_valid=1,
                   result=32, error=1, active=1, accumulator=32)
    text = ['`timescale 1ns/1ps', 'module tb_int8_mac_lane;', 'reg clk = 0;',
            'always #5 clk = ~clk;']
    text += [f'reg [{w-1}:0] {k} = 0;' for k, w in inputs.items()]
    text += [f'wire [{w-1}:0] {k};' for k, w in outputs.items()]
    ports = ', '.join(f'.{k}({k})' for k in ['clk', *inputs, *outputs])
    text += [f'int8_mac_lane dut({ports});', 'initial begin']
    for index, vector in enumerate(vectors):
        text.append('@(negedge clk);')
        text += [f'{k} = {literal(v, inputs[k])};' for k, v in vector['inputs'].items()]
        text.append('#1;')
        # First reset starts from unknown hardware state; do not inspect pre-reset readiness.
        if index:
            text += [f'if ({k} !== {literal(v, outputs[k])}) $fatal(1, "cycle {index} ready {k}");'
                     for k, v in vector['ready'].items()]
        text += ['@(posedge clk); #1;']
        text += [f'if ({k} !== {literal(v, outputs[k])}) $fatal(1, "cycle {index} state {k}");'
                 for k, v in vector['expected'].items()]
    text += ['$display("PASS int8_mac_lane reference cycles");', '$finish;', 'end',
             'initial begin #1000000; $fatal(1, "timeout"); end', 'endmodule']
    return '\n'.join(text) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    vectors = generate()
    (args.output / 'vectors.json').write_text(json.dumps(vectors, indent=2) + '\n', encoding='utf-8')
    (args.output / 'tb_int8_mac_lane.v').write_text(testbench(vectors), encoding='utf-8')
    print(f'Generated {len(vectors)} reference cycles; RTL simulation NOT run')


if __name__ == '__main__':
    main()
