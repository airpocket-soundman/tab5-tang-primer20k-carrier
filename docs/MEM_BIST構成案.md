# Standalone MEM BIST candidate

2026-11-04. Isolated codex/mem-bist, based1033656. This configuration is approved for implementation/build only. No hardware or MEM programming has been performed. A full BIST would prove a mapped128MiB region, not exact physical chip capacity or transparent Linux RAM.

## Document-based configuration

Core schematic UD1 H5TQ1G63EFR-PBC is a document identification, not a physical marking observation. The official Sipeed sample uses14 row bits and a1G/2G alias probe. It is not reused blindly. Current generatedIP explicitly selects DQ16/DRAM16,row13,column10,bank3,rank1,1:4,BL8,CL6/CWL5. Configured range is128MiB; physical memory remains unverified.

Manufacturer-authored SKhynix Rev1.1/Aug2013 datasheet was retrieved from a mirror, not a manufacturer download host: https://dtsheet.com/doc/820216/hynix-h5tq1g63efrpbj . SHA256 f4ac9e849f197fdf2c799a87991c3f4460df4d71df715f2913638707a6c2e240. Its x16 geometry uses rowsA0..12/columnsA0..9; CL6/CWL5 permits2.5..3.3ns tCK. Actual324MHz tCK is3.086419753ns.

The official sample PLL produces27x59/4=398.25MHz. The current IP frequency property rejects398.25 as a noninteger. The isolated MEM PLL instead uses IDIV0/FBDIV11/ODIV2: memory324MHz,VCO648MHz,user81MHz. The family's documented400..1200MHz VCO interval includes648MHz. Timing constraints must use324/81, not400/100.

Generator Tcl records every geometry/timing value. Emitted parameters assert x16/row13/nCK4 and are hashed in fpga/mem/config/configuration.json. Generated tCK is3086ps. Refresh input3.5us corresponds to1134 actual memory cycles; ceil284 user cycles gives3.506173us under nominal timer quantization, below3.9us. This is a quantization envelope, not a measured refresh interval or a proof of hidden controller logic. Minimum delays are conservatively configured, CL6=18.518519ns and WR8=24.691358ns. Backpressure, refresh scheduling and calibration remain verification gates.

Generated vendor files stay under ignored build/mem-bist-ip. Reproduce with official Education gw_sh and fpga/mem/config/generate_ip.tcl. Record tool/version, IPC/VO/parameter hashes and settings. No protected source is modified.

## Host review before experimental ABI

ESP original d4d89e3 README/Project_B, actual demo115dd7a, batchb3ce8a2 and TXc7a0e9a transport/display were checked. They use tile GFX; MEM BIST is unimplemented. Linux cfc9a6ec README/DEVELOPMENT_GOALS and actualDTS have no FPGA/PARLIO/MEM driver. MeOS26c80829 README/FPGA_CARRIER_REQUIREMENTS and drivers provide low-speed LINK/scalar GFX but no MEM BIST. Memory research e4aa69d0 README/Project_A requires explicit region READ/WRITE/CRC tests, not Linux main RAM. No external host source is changed here. Future hosts must pin the carrier revision and query the separate MEM signature. Host GPIO/electrical conditions stay unchanged.

## Approved experimental ABI

Use existing8-byte CRC16/seq/status framing; tagged responses retain8c3 prefix bytes. LINK1..4 remain. GFX20..44 is unsupported2. MEM_CAPS50 args0 returns014d, distinct from GFX batch0140. CFG51..56 set baseBYTE LO/HI,beatcount LO/HI,seed LO/HI and echo16-bit values; writes are locked while busy. START57 args0 explicitly launches destructive BIST only with physical ARM, software-armed host transport, calibration and complete configuration. Base must be16-byte aligned; count1..8388608;64-bit base+16*count must not exceed configured128MiB. There is no boot-time BIST or write before calibration.

SNAPSHOT58 atomically freezes32x16-bit SYS words and returns generation16. WORD59 index0..31/b0 reads only that held bank. CANCEL5a cancels without rollback; a transaction fault/cancel requires recalibration before another job. RECALIBRATE5b clears configuration/jobs and performs controlled reset. SYSQUERY5c exposes geometry/clock/calibration and stale/mailbox timeout flags even if user clock stops. Held bundles, request/ack toggles and two-stage synchronization prevent torn reads. A timeout preserves the old bank and does not claim freshness.

Error count means mismatching128-bit beats, not BER. First failure address is a byte address. Expected/actual128-bit values are exposed in little-endian16-bit word order. Progress counts verified beats and elapsed time uses64-bit USER81MHz cycles. No generic block-device READ/WRITE ABI is implemented by these diagnostic commands.

## Deterministic diagnostic and snapshot format

The native engine performs four ordered whole-region phases: fill A, verify A, write complemented A with byte mask `aaaa` (one preserves that byte), verify the merged result. For byte address `x` and seed `s`, little-endian 32-bit lanes are:

```
p0 = x XOR s XOR a5a55a5a
p1 = NOT(x) XOR s XOR 3c6ef372
p2 = rotate16(x) XOR s XOR 9e3779b9
p3 = x XOR NOT(s) XOR c001d00d
```

A is `{p3,p2,p1,p0}`; final expected value is A XOR `00ff00ff00ff00ff00ff00ff00ff00ff`. Every input address is BYTE-addressed and increments16. Native address is rank0/bank=`x[13:11]`/row=`x[26:14]`/column=`x[10:1]`. Independent command/data ready handshakes are tracked separately, with at most one read outstanding. There are no inferred fixed read latencies. Normal completion verifies `2*count` beats. This catches the tested alias injection, address/data and mask faults, but is not exhaustive electrical stress or a formal DRAM test-suite certification.

Engine errors:1 uncalibrated start,2 invalid range,3 command/data watchdog,4 read watchdog,5 unexpected read or missing read-end,6 data mismatch,7 cancel,8 calibration loss,9 total-job deadline. Error6 accumulates mismatching beats and continues; transaction faults7/8/3/4/5/9 inhibit new jobs until recalibration. Native no-progress deadline is8,100,000 USER clocks (100ms), total-job deadline4,860,000,000 clocks (60s). These are bounded diagnostics, not bandwidth guarantees.

Snapshot WORD indices:

| Words | Meaning |
|---|---|
|0|flags bit0 calibrated,1 busy,2 done,3 transaction fault,4 any mismatch,6 full configured region completed without errors|
|1|error low8, phase bits10:8 (0 idle,1 fill,2 verify,3 masked write,4 verify merged,5 complete)|
|2..3|accepted job ID32|
|4..5|verified beats32|
|6..7|mismatching beats32|
|8..9|first bad BYTE address32|
|10..17|first expected128, least-significant16-bit word first|
|18..25|first actual128, same order|
|26..29|elapsed USER81MHz cycles64, same order|
|30|USER clock MHz81|
|31|format signature014d|

SYSQUERY selectors0 signature014d;1 configured bytes in64KiB units2048;2 row/column0d0a;3 bank bits/data width0310;4 memoryMHz324;5 USERMHz81;6 flags calibrated/busy/fault/snapshot-valid/stale/mailbox-timeout inbits0..5;7 held generation16. Reserved selectors fail3. Snapshot freshness requires successful SNAPSHOT acknowledgement and expected generation; old WORD data remains readable after a failed snapshot but stale/timeout is explicit. Generation wraps modulo65536; consumers must not infer global uniqueness across reset or unbounded wrap.

LINK status0 success,1 malformed frame/CRC,2 unsupported opcode,3 invalid arguments/range,4 SYS mailbox deadline,5 unavailable/busy/incomplete configuration. SYS mailbox deadline is2,700,000 SYS clocks (100ms). On deadline a separate asynchronous USER reset inhibition prevents a timed-out START from executing when its stopped clock resumes. Explicit recalibration resets both handshake epochs, configuration and held-bank validity. It does not erase DDR contents and it does not roll back earlier accepted writes.

## Reproduction and current qualification limits

`fpga/mem/tests/run_tests.py --iverilog <tool> --vvp <tool>` runs14 independent-memory shim scenarios,33 mailbox commands and7 pin-level packets. Coverage includes separate channel stalls, independent golden patterns/mask byte order, address boundary/alias injection, errors/range/timeouts/cancel/reset, coherent held snapshots, USER clock stopped and late START inhibition, legacy/tagged framing and immediate ARM OE removal. These are simulation checks only.

Official build: run Education `gw_sh fpga/mem/config/generate_ip.tcl`, then `gw_sh fpga/mem/config/build.tcl`. The latter has no programming action. SUG100 PDF129 documents `-use_sspi_as_gpio 1`, required for the existing Dock T10 reset/N9 AUX pins; JTAG stays dedicated and existing GPIO pins/voltages are unchanged.

Initial official synthesis, placement, routing and bitstream generation completed. **Timing is not yet qualified and MEM hardware remains prohibited pending parent review.** The deliberately unwaived initial related-clock STA reports vendor calibration USER→memory HOLD/CALIB and SYS→memory clock-gate paths. The official sample declares all three clocks asynchronous, but this build does not blindly copy that blanket exception. A generated FS is not timing closure or proof of physical DDR functionality. See the versioned validation record for exact source hashes, counts and remaining violations.

Next gates: independent backpressure/readvalid/timeout/reset/cancel/first-error tests, CDC/stopped-clock tests, official MEM-only synthesis/PnR/STA/pin review, then parent-only finite hardware calibration/BIST. No GFX/NPU/HDMI coexistence or DDR bandwidth claim follows from sample synthesis.

