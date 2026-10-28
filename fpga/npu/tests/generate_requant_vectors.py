"""CPU-golden cycle vectors and self-checking Verilog TB; not RTL simulation."""
import argparse
import importlib.util
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("requant_cpu_golden", ROOT / "reference/compute_reference.py")
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)

INPUT_WIDTHS = dict(reset=1, input_valid=1, accumulator=32, multiplier=32,
                    shift=7, zero_point=16, lower=16, upper=16, output_ready=1)
OUTPUT_WIDTHS = dict(input_ready=1, output_valid=1, result=8, error=1)


def generate():
    state = dict(output_valid=0, result=0, error=0)
    vectors = []

    def cycle(**kwargs):
        ins = dict(reset=0, input_valid=0, accumulator=0, multiplier=1,
                   shift=0, zero_point=0, lower=-128, upper=127, output_ready=0)
        ins.update(kwargs)
        ready = int(not state['output_valid'] and not state['error'])
        if ins['reset']:
            state.update(output_valid=0, result=0, error=0)
        else:
            if state['output_valid'] and ins['output_ready']:
                state['output_valid'] = 0
            if ins['input_valid'] and ready:
                try:
                    result = gold.requantize(ins['accumulator'], ins['multiplier'], ins['shift'],
                                             ins['zero_point'], ins['lower'], ins['upper'])
                except ValueError:
                    state['error'] = 1
                else:
                    state.update(result=result, output_valid=1)
        vectors.append(dict(inputs=ins, input_ready=ready, expected=state.copy()))

    def job(acc, mult, shift, zero=0, lower=-128, upper=127, stall=False):
        cycle(input_valid=1, accumulator=acc, multiplier=mult, shift=shift,
              zero_point=zero, lower=lower, upper=upper)
        if stall:
            cycle(input_valid=1, accumulator=3, multiplier=-1)  # invalid payload cannot enter
            cycle()
        cycle(input_valid=1, accumulator=99, output_ready=1)  # intentional no replacement

    cycle(reset=1, input_valid=1, multiplier=-1)
    for shift in range(63):
        for acc, mult in [(gold.INT32_MIN, gold.INT32_MAX), (gold.INT32_MAX, gold.INT32_MAX),
                          (-1, 0), (1, 1)]:
            job(acc, mult, shift, stall=(shift % 17 == 0))
    for acc in [-7, -5, -3, -1, 0, 1, 3, 5, 7]:
        job(acc, 1, 1, stall=True)
    job(gold.INT32_MIN, 1 << 30, 62)  # exact negative half at maximum shift
    job(1 << 30, 1 << 30, 61)  # exact positive half with a large product
    for acc in [gold.INT32_MIN, -257, -1, 0, 1, 257, gold.INT32_MAX]:
        for zero in [-128, -3, 0, 7, 127]:
            job(acc, 3, 2, zero, max(-128, zero), 127)  # ReLU limits
    job(12345, 12345, 12, -17, 5, 5)  # degenerate clamp interval
    rng = random.Random(20261023)
    for _ in range(160):
        lower, upper = sorted([rng.randint(-128, 127), rng.randint(-128, 127)])
        job(rng.randint(gold.INT32_MIN, gold.INT32_MAX), rng.randint(0, gold.INT32_MAX),
            rng.randrange(63), rng.randint(-128, 127), lower, upper, stall=rng.randrange(8)==0)
    invalid = [dict(multiplier=-1), dict(multiplier=gold.INT32_MIN), dict(shift=63),
               dict(shift=127), dict(zero_point=-129), dict(zero_point=128),
               dict(lower=-129), dict(upper=128), dict(lower=5, upper=4),
               dict(lower=128, upper=128), dict(lower=-129, upper=-129)]
    for params in invalid:
        cycle(input_valid=1, **params)
        cycle(input_valid=1, accumulator=7, output_ready=1)  # latched error refuses work
        cycle(reset=1)
        job(3, 1, 1)  # recovery
    cycle(input_valid=1, accumulator=-7, shift=1)
    cycle(reset=1, output_ready=1)  # pending output abort
    return vectors


def literal(value, width):
    return f"{width}'h{value & ((1 << width)-1):x}"


def testbench(vectors):
    lines = ['`timescale 1ns/1ps', 'module tb_int8_requantize;', 'reg clk = 0;', 'always #5 clk = ~clk;']
    lines += [f'reg [{width-1}:0] {name} = 0;' for name, width in INPUT_WIDTHS.items()]
    lines += [f'wire [{width-1}:0] {name};' for name, width in OUTPUT_WIDTHS.items()]
    ports = ', '.join(f'.{name}({name})' for name in ['clk', *INPUT_WIDTHS, *OUTPUT_WIDTHS])
    lines += [f'int8_requantize dut({ports});', 'initial begin']
    for i, v in enumerate(vectors):
        lines.append('@(negedge clk);')
        lines += [f'{name} = {literal(value, INPUT_WIDTHS[name])};' for name, value in v['inputs'].items()]
        lines.append('#1;')
        if i:
            lines.append(f'if (input_ready !== 1\'b{v["input_ready"]}) $fatal(1, "cycle {i} ready");')
        lines.append('@(posedge clk); #1;')
        lines += [f'if ({name} !== {literal(value, OUTPUT_WIDTHS[name])}) $fatal(1, "cycle {i} state {name}");'
                  for name, value in v['expected'].items()]
    lines += ['$display("PASS int8_requantize golden cycles");', '$finish;', 'end',
              'initial begin #1000000; $fatal(1, "timeout"); end', 'endmodule']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    vectors = generate()
    (args.output / 'requant_vectors.json').write_text(json.dumps(vectors, indent=2)+'\n', encoding='utf-8')
    (args.output / 'tb_int8_requantize.v').write_text(testbench(vectors), encoding='utf-8')
    print(f'Generated {len(vectors)} requantization reference cycles; RTL simulation NOT run')


if __name__ == '__main__':
    main()
