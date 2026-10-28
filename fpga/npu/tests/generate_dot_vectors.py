"""Dot-job CPU oracle/cycle vectors; generation does not execute Verilog."""
import argparse
import importlib.util
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dot_cpu_golden', ROOT / 'reference/compute_reference.py')
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)
INPUTS = dict(reset=1, begin_valid=1, bias=32, input_zero_point=16, multiplier=32,
              shift=7, output_zero_point=16, lower=16, upper=16, length=32,
              sample_valid=1, activation=8, weight=8, result_ready=1)
OUTPUTS = dict(begin_ready=1, sample_ready=1, result_valid=1, result=8,
               busy=1, error=1, error_code=2)


def validate(c):
    if not -128 <= c['input_zero_point'] <= 127:
        raise ValueError('input zero point')
    gold.requantize(c['bias'], c['multiplier'], c['shift'], c['output_zero_point'], c['lower'], c['upper'])


class Model:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state, self.result, self.acc, self.code, self.remaining = 'IDLE', 0, 0, 0, 0
        self.config = None

    def outputs(self):
        return dict(begin_ready=int(self.state=='IDLE'), sample_ready=int(self.state=='STREAM'),
                    result_valid=int(self.state=='OUTPUT'), result=self.result,
                    busy=int(self.state!='IDLE'), error=int(self.state=='FAULT'), error_code=self.code)

    def step(self, i):
        if i['reset']:
            self.reset()
        elif self.state=='IDLE' and i['begin_valid']:
            try:
                validate(i)
            except ValueError:
                self.state, self.code = 'FAULT', 1
            else:
                self.config = i.copy()
                self.remaining = i['length']
                self.state = 'START'
        elif self.state=='START':
            self.acc = self.config['bias']
            self.state = 'STREAM' if self.remaining else 'FINISH'
        elif self.state=='STREAM' and i['sample_valid']:
            try:
                self.acc = gold.tiled_gemm([[i['activation']]], [[i['weight']]], [self.acc],
                                          self.config['input_zero_point'])[0][0]
            except OverflowError:
                self.state, self.code = 'FAULT', 2
            else:
                self.remaining -= 1
                if not self.remaining:
                    self.state = 'FINISH'
        elif self.state=='FINISH':
            self.state = 'QUANT'
        elif self.state=='QUANT':
            c = self.config
            self.result = gold.requantize(self.acc, c['multiplier'], c['shift'],
                                          c['output_zero_point'], c['lower'], c['upper'])
            self.state = 'OUTPUT'
        elif self.state=='OUTPUT' and i['result_ready']:
            self.state = 'IDLE'


def generate():
    model, vectors, jobs = Model(), [], []
    defaults = dict(reset=0, begin_valid=0, bias=0, input_zero_point=0, multiplier=1,
                    shift=0, output_zero_point=0, lower=-128, upper=127, length=0,
                    sample_valid=0, activation=0, weight=0, result_ready=0)

    def cycle(**kwargs):
        ins = defaults | kwargs
        before = model.outputs()
        model.step(ins)
        vectors.append(dict(inputs=ins, before=before, expected=model.outputs()))

    def job(pairs, **config):
        cfg = defaults | config | dict(length=len(pairs))
        start = len(vectors)
        cycle(**(cfg | dict(begin_valid=1, sample_valid=1, activation=99, weight=99)))
        if model.state=='FAULT':
            jobs.append(dict(config=cfg, pairs=pairs, error=1, result=None, start_cycle=start))
            cycle(begin_valid=1, sample_valid=1, result_ready=1)
            cycle(reset=1)
            return
        # Every post-begin config is deliberately different, proving latch semantics.
        noise = dict(begin_valid=1, bias=123456, multiplier=-1, input_zero_point=300,
                     shift=127, output_zero_point=999, lower=900, upper=-900, length=999)
        cycle(**noise, sample_valid=1, activation=99, weight=99)  # START accepts no sample
        for index, (a,w) in enumerate(pairs):
            if model.state=='FAULT':
                break
            if index % 3 == 0:
                cycle(**noise)  # source bubble
            cycle(**noise, sample_valid=1, activation=a, weight=w)
        if model.state=='FAULT':
            jobs.append(dict(config=cfg, pairs=pairs, error=2, result=None, start_cycle=start))
            cycle(begin_valid=1, sample_valid=1, result_ready=1)
            cycle(reset=1)
            return
        while model.state!='OUTPUT':
            cycle(**noise, sample_valid=1, activation=-128, weight=-128)
        result = model.result
        for _ in range(3):
            cycle(**noise, sample_valid=1, activation=100, weight=100)
        cycle(**noise, sample_valid=1, result_ready=1)  # no same-cycle begin replacement
        jobs.append(dict(config=cfg, pairs=pairs, error=0, result=result, start_cycle=start))

    cycle(reset=1, begin_valid=1, sample_valid=1)
    job([], bias=-7, multiplier=1, shift=1)
    job([(127,-128),(-128,-128)], bias=7, input_zero_point=-128, multiplier=1, shift=8)
    job([(127,-128),(-128,-128)], bias=7, input_zero_point=127, multiplier=3, shift=9)
    job([(1,1)]*3, bias=gold.INT32_MAX-2)
    job([(1,-1)]*3, bias=gold.INT32_MIN+2)
    job([], bias=gold.INT32_MIN, multiplier=gold.INT32_MAX, shift=62)
    job([(1,1)], multiplier=0, output_zero_point=17, lower=17)
    for invalid in [dict(input_zero_point=-129),dict(input_zero_point=128), dict(multiplier=-1),
                    dict(shift=63),dict(output_zero_point=128),dict(lower=-129),dict(upper=128),
                    dict(lower=7,upper=6)]:
        job([], **invalid)
    rng = random.Random(20261023)
    for _ in range(70):
        low, high = sorted([rng.randint(-128,127),rng.randint(-128,127)])
        pairs = [(rng.randint(-128,127),rng.randint(-128,127)) for _ in range(rng.randrange(20))]
        job(pairs, bias=rng.randint(-100000,100000), input_zero_point=rng.randint(-128,127),
            multiplier=rng.randint(0,gold.INT32_MAX), shift=rng.randrange(63),
            output_zero_point=rng.randint(-128,127), lower=low, upper=high)
    # Reset aborts each pipeline phase and a pending result, followed by a clean job.
    for phase in ['START','STREAM','FINISH','QUANT','OUTPUT']:
        cycle(begin_valid=1, length=1, bias=5)
        if phase!='START':
            cycle()
        if phase in ['FINISH','QUANT','OUTPUT']:
            cycle(sample_valid=1, activation=2, weight=3)
        if phase in ['QUANT','OUTPUT']:
            cycle()
        if phase=='OUTPUT':
            cycle()
        assert model.state==phase
        cycle(reset=1, begin_valid=1, sample_valid=1, result_ready=1)
        job([(2,3)], bias=5)
    return dict(vectors=vectors, jobs=jobs)


def literal(value, width):
    return f"{width}'h{value & ((1 << width)-1):x}"


def testbench(data):
    lines=['`timescale 1ns/1ps','module tb_int8_dot_job;','reg clk=0;','always #5 clk=~clk;']
    lines += [f'reg [{w-1}:0] {k}=0;' for k,w in INPUTS.items()]
    lines += [f'wire [{w-1}:0] {k};' for k,w in OUTPUTS.items()]
    ports=', '.join(f'.{k}({k})' for k in ['clk',*INPUTS,*OUTPUTS])
    lines += [f'int8_dot_job dut({ports});','initial begin']
    for index,v in enumerate(data['vectors']):
        lines.append('@(negedge clk);')
        lines += [f'{k}={literal(n,INPUTS[k])};' for k,n in v['inputs'].items()]
        lines.append('#1;')
        if index:
            lines += [f'if ({k} !== {literal(v["before"][k],OUTPUTS[k])}) $fatal(1,"cycle {index} before {k}");'
                      for k in ['begin_ready','sample_ready','result_valid']]
        lines.append('@(posedge clk); #1;')
        lines += [f'if ({k} !== {literal(n,OUTPUTS[k])}) $fatal(1,"cycle {index} after {k}");'
                  for k,n in v['expected'].items()]
    lines += ['$display("PASS dot job golden cycles");','$finish;','end',
              'initial begin #1000000; $fatal(1,"timeout"); end','endmodule']
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    data=generate()
    (args.output/'dot_vectors.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (args.output/'tb_int8_dot_job.v').write_text(testbench(data),encoding='utf-8')
    print(f"Generated {len(data['jobs'])} dot jobs / {len(data['vectors'])} cycles; RTL simulation NOT run")


if __name__=='__main__':
    main()
