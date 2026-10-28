# Scalar INT8 requantization RTL prototype

`int8_requantize.v` implements the arithmetic proposed by
`reference/compute_reference.py::requantize` for one element. It is a separate
component; it is not integrated into the MAC lane, DDR path, or ONNX execution.

Inputs are signed INT32 accumulator, signed INT32 multiplier (legal range
0..2147483647), unsigned 7-bit shift (legal 0..62), and signed INT16 zero_point,
lower, upper (legal -128..127, lower<=upper). The wider parameter ports allow
invalid settings to be rejected before narrowing. The final result is signed
INT8. A caller must validate values before packing into these ports; values
outside the port's representable range must not be truncated by a command parser.

Arithmetic is signed INT64 product, absolute magnitude, half-unit addition and
logical right shift, restored sign, addition of zero_point, then clamp. Ties round
away from zero. Shift zero adds no rounding bias. Negative arithmetic shift alone
would give the wrong rounding. The largest valid product magnitude is below
2^62; rounding adds at most 2^61, so the 64-bit intermediate does not overflow.
ReLU uses lower=max(-128,zero_point), as supplied by the caller; there is no
implicit activation mode or alteration of the clamp range.

All operations use rising-edge valid/ready handshakes. Hold valid and all input
payload fields stable until input_ready. An accepted valid request publishes its
result on that edge; output_valid/result remain stable until output_ready. A full
output register blocks input_ready even on the result-consumption cycle; one
intentional bubble follows every output. This is a correctness prototype, not
a throughput-optimized pipeline.

An accepted request with invalid parameters latches error, preserves result,
publishes no output and blocks further requests until reset. A pending valid
output blocks every input request, including invalid ones. Synchronous active-high
reset has priority, drops pending output, clears result/error, and is required
before using the component. It is also the explicit job-abort/error-recovery
mechanism. There are no separate begin/end signals: each input is one complete
scalar job. The future command processor must translate error to INVALID_PARAM.

Generate reference vectors and a self-checking Verilog testbench:

```
python npu/tests/generate_requant_vectors.py --output build/rtl-requant
python -m unittest discover -s npu/tests -p "test_requant_vectors.py" -v
```

Vectors use the existing CPU golden, include zero/max multiplier, all shift
values, signed extrema, exact half ties, nonzero output offsets, saturation,
ReLU clamps, output stalls, reset, invalid parameters, and error recovery.
The host tests exercise vector generation and an independent integer formula;
they do not execute Verilog. No RTL simulator or synthesis tool is installed
by this work. RTL simulation, synthesis, timing, FPGA resource usage and hardware
validation are unperformed; no performance improvement is claimed.
