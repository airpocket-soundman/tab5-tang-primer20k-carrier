# FPGA-local RV32 component proof (2026-11-08)

This archive proves the actual pinned PicoRV32IMC core, cache and MMIO with compiled RV32 firmware, an independent INT32 MAC double and fake DDR. It does not prove full-model execution, actual MAC integration, physical DDR, full-chip fit, timing closure or speed superiority. Root integration records those separately.

Normal smoke checks14 independent values; IC17 chain checks20 values and unchanged nonfinal DDR/guards. Nine actual CPU faults cover bad tag, timeout/drain, abort, calibration loss, bad memory status, abort at a native response, MAC watchdog, illegal instruction and late output write failure. No success/retry is fabricated. Quarantine retains ownership; correlated drained failures may release only with the CPU halted.

Final standalone synthesis: Logic5824 / FF2235 / BSRAM1 / RAM16=72 / DSP0. Adding Logic14193 from4E24 arithmetically leaves719; this omits owner/framer/control and routing. Do not call it an integrated fit. Fmax71.173MHz is synthesis estimate under the tool's reported100MHz default, not PNR/STA. The final raw RTL source hashes match the synthesis snapshots. Initial5-BSRAM and all-flop overbudget reports are historical only; their exact exploratory source snapshots were not retained.

The core is officialYosysHQ/picorv32 commit ef203c2b0a3fb793280f5114941416c425c5b461 ISC. Original vendor bytes remain unchanged. The generated synthesis source only wraps the official PICORV32_REGS hook to use the separate distributed-RAM register file. Cache storage is a single-port512x32 BSRAM shared sequentially by1KiB I-cache/1KiB write-back D-cache; tags use distributed RAM.

COMMAND stores block CPU instruction execution across pre-flush/invalidate, accelerator completion and post-invalidate. Tile ACK never clears the loader's partial accumulator; nonfinal tile DONE with RESULT_VALID0 is legal. FINISH follows final dirty-data flush then permanently halts CPU until explicit new-run clear. Mailbox0x07ff0000 is uncached/write-through. Host/CPU/MAC DDR/staging ownership is an integration obligation, not a raw-toggle mux.


## Later optional-matrix profile

The integrated first full-chip candidate exceeded Logic capacity (root measured22035/20736). The current module adds ENABLE_MATRIX (default1 for prior component behavior); the deployed-candidate setting0 rejects COMMAND2 and ignores unavailable matrix-ready. Firmware v8/chainv3 instead sequences identical accelerator Tile commands inside the FPGA CPU. This is not CPU MAC fallback. Current tile-only CPU proof checks14/20 values per run across two RUNs, fresh0xA5 ELF.bss and epoch37->38, with matrix_start_ready0. Nine fault cases pass on this profile. Source/rtl is current; synthesis/final/source_snapshot is the exact earlier component measured5824, not a falsely relabeled current full-chip fit.

The compiled firmware ELF files are gzip-compressed only for archive size. Decompress beside the corresponding .bin to reproduce --seed-bss, which reads the actual ELF section range. Archived current tests use --no-matrix --seed-bss --restart for normal and --chain additionally for IC17. Older matrix-capable test binaries/results remain dated history. The early v6 tiny smoke also passes with seeded BSS; it is not a negative control proving that the old linker always failed. The later linker fix places BSS symbols correctly and is required independently.
