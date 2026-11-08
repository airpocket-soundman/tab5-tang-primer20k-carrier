# INDEX32 experiment: actual RV32 ISA proof

All 649 nodes, 57 Conv and 65 logical MatMul completed using actual RV32IMC soft-float instructions plus a host integer MAC MMIO oracle. No physical FPGA access occurred. All 1800 output floats match canonical v7 RV32 output bit for bit (SHA256 9a4e9b9319e2b2592c9c10d2134c97b71226f0bf32e3b4774dfeb71feca6f715). BSS was seeded with 0xA5 before startup. Commands: 400368 Tile, zero hardware Matrix.

Step-budget slices decreased 212125 to 142253 (32.94%); combined data callbacks decreased 17.60%. These are interpreter workload measurements, not FPGA throughput. Exact retired instruction counts were not instrumented. Host elapsed 472 to 376 seconds is not a hardware speed measurement.

The isolated experiment narrows bounded hot unsigned indices to 32 bits, retaining signed tensor INT64 and floating/double arithmetic. Model-specific guards restrict eligibility; this is not arbitrary ONNX compatibility. Canonical v7 is unchanged. The prior P4/FPGA strict numeric FAIL remains separate and unresolved. This archive establishes candidate correctness before any physical candidate output. Physical acceptance remains pending.

Firmware and build input hashes, exact ELF/BIN, native gate, ISA runner provenance, raw logs/results/output and source equivalence are frozen here. Pinned rv32emu and test-only callback patch provenance are in sibling npu-autonomous-isa-2026-11-08. Whole firmware upload/readback is mandatory before every run; CLEAR alone is not a warm reset.
