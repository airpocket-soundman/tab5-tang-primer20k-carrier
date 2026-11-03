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

Use existing8-byte CRC16/seq/status framing; tagged responses retain8c3 prefix bytes. LINK1..4 remain. GFX20..44 is unsupported2. MEM_CAPS50 args0 returns014d, distinct from GFX batch0140. CFG51..56 set baseBYTE LO/HI,beatcount LO/HI,seed LO/HI and echo16-bit values; writes are locked while busy. START57 args0 explicitly launches destructive BIST only with physical ARM, software-armed host transport, calibration and complete configuration. Base must be16-byte aligned; count1..8388608;64-bit base+16*count must not exceed configured128MiB. There is no boot-time BIST or user/native write before calibration. Vendor initialization/calibration can write training locations; programming this standalone image and RECAL must be treated as destructive to existing DDR contents.

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

SYSQUERY selectors0 signature014d;1 configured bytes in64KiB units2048;2 row/column0d0a;3 bank bits/data width0310;4 memoryMHz324;5 USERMHz81;6 SYS flags below;7 held generation16. Reserved selectors fail3. Snapshot freshness requires successful SNAPSHOT acknowledgement and expected generation; old WORD data remains readable after a failed snapshot but stale/timeout is explicit. Generation wraps modulo65536; consumers must not infer global uniqueness across reset or unbounded wrap.

Guarded candidate SYSQUERY6 flags:0 calibrated,1 busy,2 USER transaction fault,3 held bank valid,4 stale,5 mailbox timeout,6 sticky context lost,7 calibration guard ready,8 USER reset released,9 heartbeat fresh,10 reset-loss reason,11 calibration-loss reason,12 heartbeat-loss reason,13 pending-request reset/loss reason. Bits14..15 are reserved0. START requires calibration stable for at least256 SYS clocks9.481us, USER epoch alive, and fresh heartbeat. USER toggles heartbeat every256 USER clocks3.160us; SYS detects no change for27000 SYS clocks1ms. This is bounded halt detection, not detection of every missing edge. After an acknowledged job, reset/calibration/heartbeat loss sets sticky SYS context fault, marks the bank stale and asynchronously inhibits USER logic until explicit RECAL. A reset pulse during a request cannot reset the acknowledgement toggle into a false success. No automatic job resumes after a detected loss.

Host must freshly acknowledge SNAPSHOT, read all32 WORD values, then read SYSQUERY6 and SYSQUERY7 and verify no stale/context-loss/timeout, expected generation, healthy calibration/USER/heartbeat and expected full job ID. An old held DONE bank is not a current PASS. `fpga/host/mem_protocol.h` supplies portable CRC/sequence/argument validation and this final PASS check;591 native C checks cover rejection cases, generation wrap and64-bit cycles. Valid diagnostic error frames have LINK status1..5, never PASS. START acknowledges only jobID low16; a fresh healthy baseline snapshot provides full accepted jobID and next accepted START increments it modulo2^32. Every successful SNAPSHOT increments generation, including IDLE snapshots. Reset/RECAL resets the bank/generation and job epoch.

LINK status0 success,1 malformed frame/CRC,2 unsupported opcode,3 invalid arguments/range,4 SYS mailbox deadline,5 unavailable/busy/incomplete configuration. SYS mailbox deadline is2,700,000 SYS clocks (100ms). On deadline a separate asynchronous USER reset inhibition prevents a timed-out START from executing when its stopped clock resumes. Explicit recalibration resets both handshake epochs, configuration and held-bank validity. It is not a full-region erase, can alter DDR contents through training, and does not roll back earlier accepted writes.

## Reproduction and current qualification limits

`fpga/mem/tests/run_tests.py --iverilog <tool> --vvp <tool>` runs17 independent-memory shim scenarios,33 mailbox commands and7 pin-level packets. Coverage includes separate channel stalls, independent golden patterns/mask byte order, address boundary/alias injection, errors/range/timeouts/cancel/reset, coherent held snapshots, USER clock stopped and late START inhibition, legacy/tagged framing and immediate ARM OE removal. These are simulation checks only.

Official build: run Education `gw_sh fpga/mem/config/generate_ip.tcl`, then `gw_sh fpga/mem/config/build.tcl`. The latter has no programming action. SUG100 PDF129 documents `-use_sspi_as_gpio 1`, required for the existing Dock T10 reset/N9 AUX pins; JTAG stays dedicated and existing GPIO pins/voltages are unchanged.

Initial official synthesis, placement, routing and bitstream generation completed. **Timing is not yet qualified and MEM hardware remains prohibited pending parent review.** The deliberately unwaived initial related-clock STA reports vendor calibration USER→memory HOLD/CALIB and SYS→memory clock-gate paths. The official sample declares all three clocks asynchronous, but this build does not blindly copy that blanket exception. A generated FS is not timing closure or proof of physical DDR functionality. See the versioned validation record for exact source hashes, counts and remaining violations.

### Clock-port audit and scoped CDC contracts

IPUG281-2.6E PDF32 defines `clk` as the reference crystal input (50MHz recommended), `memory_clk` as the memory interface frequency, and `clk_out` as the user-design clock. The official Sipeed20K sample connects its27MHz oscillator to `clk`. Our `.clk(sys_clk)` follows that contract. Generated IPC/parameters and installed `ddr3.ipspec` expose MEMORY_CLK324 and CLK_RATIO1:4, with no separate reference-frequency property or50MHz configuration. This is not a claim that arbitrary reference frequencies have been exhaustively tested. The documented active-high processed `ddr_rst` also enters the USER asynchronous-assert, synchronous-release reset chain.

SUG940-2.0E PDF79..81 documents the precise `get_regs`/`get_pins`, max-delay and hold-only exception syntax used. Request payload stays stable until acknowledgement; its earliest USER capture is two USER periods24.691358ns after SYS launch, so the payload path is constrained to20ns. USER captures a snapshot, acknowledges the following USER edge, then SYS synchronizes acknowledgement and waits an explicit settling cycle: minimum123.456790ns before SYS bank capture, with60ns max delay. Only those held bundles have their irrelevant same-edge hold checks exempted. Exact routed from/to lists, delays and slacks are recorded in validation JSON. Actual27/81MHz simulation asserts both minimum settle intervals. Five explicit first-stage D pins accept asynchronous samples (request,ack,cal,busy,fault); their next stages and all same-domain paths remain timed. No clock group is declared asynchronous.

Review-only `vendor_async_review.json` lists20 exact vendor primitive/synchronizer input endpoints and their sources. It is **not active** in the build. Public official `IDE/simlib/gw2a/prim_sim.v` shows four falling-edge stages inside DHCEN CE, three falling-edge stages for DQS HOLD, and three rising-edge stages for IDES8_MEM CALIB. UG286-1.9.9E PDF28 documents active-low DHCEN gating and PDF99 the HOLD calibration/FIFO function. Generated unprotected controller VO shows the vendor recalibration two-stage synchronizer. These are functional-model/structure evidence for a finite first-stage exception proposal, not metastability MTBF certification or external DDR timing proof. The separate single reference-clock `wloadn_1_s0` initialization crossing has not been qualified or exempted. No protected source was decrypted or modified.

Parent approved the finite20 endpoints for a **separate measured build**. Run `prepare_scoped.py`, then set environment `MEM_BIST_SCOPED=1` before the same official build Tcl. This preserves the ordinary `mem-bist-official` report/FS and emits separate `mem-bist-scoped` output. The preparation script asserts20 unique cell+port matches with exact expected primitive types in public generated VO; the routed-name interpretation is also checked for tool diagnostics and before/after timing changes. No blanket clock group is introduced. Baseline79 setup/recovery-summary endpoints and8 hold become scoped61 summary and7 hold; normal data setup is positive, worst0.109ns, USER Fmax81.720MHz for81 target. All61 remaining recovery endpoints are61 explicit vendor hard-primitive RESET pins (126 negative paths); hold remains the initialization WLOADN crossing plus6 DLL STEP bits. Rounded negative-zero slack remains recorded as a violation. This remains **unqualified for hardware**.

Optional official-model test: add `--primitive-lib <official gw2a/prim_sim.v>` to the portable runner. `project_vendor_clock_cone.py` mechanically extracts116 unchanged public vendor cells from5560, with explicit pre-calibration boundary assumptions `sys_reset_Z=0` and `ddr_init_internal=0` (no recalibration or completed-DRAM feedback). No vendor source is committed; generated projection remains ignored. The real reference FSM, DHCEN, CLKDIV and DLL execute. Observed STEP changes to31 at711.111us, UPDNCNTL holds it at711.259us, INIT_START rises712.037us, and the actual one-shot STEP capture occurs712.448us with LOCK=1,1336.766ns prior stability and1188.614ns held duration. The test asserts capture actually occurs and those settle conditions hold. This supports a narrowly guarded DLL STEP hold-exception proposal; it does not simulate a DRAM device, completion of calibration, PVT drift, or physical timing. The unsliced controller model was stopped during costly Icarus startup and is **not** counted as passing.

Next gates: independent backpressure/readvalid/timeout/reset/cancel/first-error tests, CDC/stopped-clock tests, official MEM-only synthesis/PnR/STA/pin review, then parent-only finite hardware calibration/BIST. No GFX/NPU/HDMI coexistence or DDR bandwidth claim follows from sample synthesis.


