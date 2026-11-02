# Test-only Gowin primitive models

`gowin_bench_models.v` is an independent, bounded functional model for the
current synthesized Dock GFX design. It is **not** a Gowin library, a vendor
certification, a post-route timing model, or a hardware test. It must not be
used as a general replacement for a vendor primitive library.

The synthesized GFX netlist uses one `SPX9`: `BIT_WIDTH=18`, `READ_MODE=0`
(bypass), `WRITE_MODE=2` (read-before-write), `RESET_MODE="ASYNC"`,
`BLK_SEL=000`, and all 64 initialization parameters zero. Other parameter
configurations cause `$fatal`; the upper 18 output bits are deliberately unknown.
The primitive has 1,024 18-bit words. The documented `AD[13:4]` selects the
word and `AD[1:0]` enables writes to the two 9-bit lanes; read-before-write
returns the old word on the active clock edge. In bypass mode `OCE` does not
gate output. The model resets the output asynchronously without clearing RAM.
All memory words start at zero, matching the zero initialization parameters;
the RTL interface still requires CLEAR before access. CE and BLKSEL are
modeled as ideal functional clock-edge gates. The real device has additional
CE transition and setup/hold conditions documented in UG285 Appendix A; these
are outside this model. In the actual GFX netlist CE/OCE are tied high,
BLKSEL/RESET are tied low, and both byte enables follow WRE.

`IOBUF` models the active-low output enable and resolved bidirectional pin.
It does not model pin delays, electrical levels, bus resistance, or configuration
pin reuse. Other Yosys primitive models must be supplied separately. Remove or
exclude duplicate SPX9/IOBUF blackbox definitions before adding this file.
An unresolved GSR blackbox is not equivalent to a verified power-up sequence;
check the assumptions of any simulator overlay separately.

The overlay also contains a test-only `ALU` limited to `ALU_MODE=2`
(ADDSUB), the only mode in the current GFX synthesis (141 instances).
It expresses the Yosys model's equations as continuous assignments to avoid an
Icarus vvp code-generation assertion seen with two chained original ALUs.
It rejects all other modes. For Yosys 0.70 (commit `28ba3cb92`), the installed
[`techlibs/gowin/cells_sim.v`](https://github.com/YosysHQ/yosys/blob/28ba3cb92/techlibs/gowin/cells_sim.v)
had SHA-256 `0af82c7c45d64bbdfca798b951c3cd5ba4b6a6f85336f8aaa518725a5a5f7222`.
The 16 binary input combinations were compared against both an independently
computed truth table and a separately simulated original Yosys ALU. This is a
functional test, not an assessment of unknown-state or timing behavior.

Sources: [Gowin UG285 B-SRAM guide](https://www.gowinsemi.com/upload/database_doc/6/document/5b5852bfdb1b1.pdf),
Tables 2-2, 3-2 and 3-3, sections 6.2.3, 6.4, 6.7 and Appendix A;
[Gowin UG289 GPIO guide](https://cdn.gowinsemi.com.cn/UG289E.pdf), section 3.6.4.

Run the independent unit test using already installed Icarus tools:

```text
python fpga/simulation/tests/run.py --iverilog <iverilog> --vvp <vvp>
python fpga/simulation/tests/run_alu.py --iverilog <iverilog> --vvp <vvp> --yosys-cells <path-to-gowin-cells_sim.v>
```

The tests check two distant addresses, registered read behavior, old-value
write output, 9-bit enables, enable/block gating, reset retention, bidirectional
pin direction, and rejection of unsupported primitive parameters. They use
explicit expected values and do not call the graphics reference model.

## Synthesized-netlist runner

From the repository root, explicitly opt into the bounded functional model:

```text
python fpga/gfx/tests/run_synth_bench.py --model-overlay fpga/simulation/gowin_bench_models.v
```

The runner checks recorded synthesis source hashes, writes a separate combined
library under `fpga/build/synth-bench/`, and records original/overlay/combined
library hashes. It never edits the installed Yosys library. Without an overlay,
the incomplete bundled SPX9/IOBUF models are still rejected. A passed screening
check only detects known defects; it does not certify primitive behavior.
