# INT8 single MAC lane (prototype)

`int8_mac_lane.v` is an arithmetic primitive, not a DDR controller, Conv engine,
requantizer, graph executor, or measured accelerator. No hardware access is needed.

All handshakes occur on the rising clock edge. Reset is synchronous, active high,
has priority over every handshake, aborts a job/result, and clears the latched error.
Signals are not valid until at least one reset clock edge has occurred.

1. Hold `begin_valid` and INT32 `bias` until `begin_ready`; that edge loads the
   accumulator and starts the job. No MAC is accepted on the begin edge.
2. Each `mac_valid && mac_ready` edge adds `(activation-zero_point)*weight`.
   Inputs are signed INT8; the difference is signed INT9 and product INT17.
   Partial sums are INT32, with signed INT33 overflow detection before writing.
3. Hold `end_valid` until `end_ready`. End accepts no MAC itself; if MAC and end
   are both requested, MAC wins and end waits. The caller must stop issuing MACs
   to end the job. An empty job is legal and returns the bias.
4. End publishes `result_valid`. Hold the result until `result_ready`; while it
   is blocked the result stays stable and no next begin is accepted. A begin is
   accepted starting the cycle after result consumption (intentional bubble).

Valid sources hold payloads stable while waiting. Begin/end requests presented
in the wrong phase remain unaccepted; they do not mutate state. This primitive
has no timeout: the future command processor must enforce legal sequencing.

Overflow accepts the offending MAC handshake but rejects its numerical update:
the last valid accumulator remains unchanged, `error` latches high, `active`
clears, no result is published, and all ready signals remain low until reset.
Already accepted sums are not rolled back. The command processor must translate
this condition to `ACC_OVERFLOW`; the accumulator is diagnostic, not a successful
output. INT32 overflow must never wrap or silently saturate.

Generate and host-check the deterministic Verilog testbench:

```
python npu/tests/generate_vectors.py --output build/rtl-compute
python -m unittest discover -s npu/tests -p "test_*.py" -v
```

If a Verilog simulator is available, compile `int8_mac_lane.v` and the generated
`tb_int8_mac_lane.v` and run the resulting simulation. The generated bench asserts
every state and handshake against the Python reference-derived cycle vectors,
including reset, stalls, empty jobs, signed extrema, both overflow directions,
and error recovery. Host vector checks do **not** prove RTL simulation passed.
No simulator is installed for this prototype; simulation and synthesis remain
unexecuted. No clock frequency, device utilization, or speedup is claimed.
