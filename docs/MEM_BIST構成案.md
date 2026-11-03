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

SNAPSHOT58 atomically freezes32x16-bit SYS words and returns generation16. WORD59 index0..31/b0 reads only that held bank. CANCEL5a cancels without rollback; a transaction fault/cancel requires recalibration before another job. RECALIBRATE5b clears configuration/jobs and performs controlled reset. SYSQUERY5c exposes geometry/clock/calibration and stale/mailbox timeout flags even if user clock stops. Held bundles, four-phase request/ack and two-stage synchronization prevent torn reads. A timeout preserves the old bank and does not claim freshness.

Error count means mismatching128-bit beats, not BER. First failure address is a byte address. Expected/actual128-bit values are exposed in little-endian16-bit word order. Progress counts verified beats and elapsed time uses64-bit USER81MHz cycles. Pattern/snapshot map and errors are fixed by implementation tests before physical review. No generic block-device READ/WRITE ABI is implemented by these diagnostic commands.

Next gates: independent backpressure/readvalid/timeout/reset/cancel/first-error tests, CDC/stopped-clock tests, official MEM-only synthesis/PnR/STA/pin review, then parent-only finite hardware calibration/BIST. No GFX/NPU/HDMI coexistence or DDR bandwidth claim follows from sample synthesis.
