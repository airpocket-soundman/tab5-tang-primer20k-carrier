# Isolated nearest-map full RV32 ISA proof

Actual RV32IMC soft-float firmware completed all649 nodes /57 Conv /65 logical MatMul with400368 Tile commands and zero hardware Matrix commands.352B BSS was prefilled0xA5 before startup. All1800 output float bits exactly match predeclared RV32 golden9a4e9b9319e2b2592c9c10d2134c97b71226f0bf32e3b4774dfeb71feca6f715. Integer MAC uses independent native oracle; no physical hardware was accessed.

Compared with index32 parent (noCRCcombo), step-budget slices142253Å®142130 (-0.0865%). Read callbacks increased2742127 and writes31458850.370 host seconds is not FPGA speed; tiny wholegraph instruction savings plus additional memory accesses do not establish a physical speed improvement. Exact ELF/BIN, all19 build-input hash matches, native tests, source snapshot and full ISA output/log/provenance are preserved. Canonical firmware, host SDK and active hardware unchanged.

Static helper+caller+main stack subtotal is28160B before unmeasured deeper calls. Linker stack top0x07fe0000 to heap end0x07000000 gap is16646144B (~15.875MiB). No dynamic SP/canary/highwater was measured; unchanged harness was intentionally used for directly comparable workload counters. This is offline numerical eligibility only, not candidate promotion or physical NN qualification.
