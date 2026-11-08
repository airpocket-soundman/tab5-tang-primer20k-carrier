# Experimental4E30 fullchip build / RTL evidence (no physical claim)

Tile-only hardware MAC plus FPGA-local RV32IMC control/software math. The hardware matrix sequencer is omitted; firmware emits the same existing Tile descriptors for MatMul. P4 performs only upload/control/display in the new profile.

Fullchip synthesis and PNR succeeded: Logic18513/20736, Register8647/16173, BSRAM46/46, DSP12.5/24, CLS9785/10368 (95%). Same-clock SYS Fmax38.217MHz versus27MHz; USER100.697MHz versus99.5625MHz. UnwaivedSTA1416setup/84hold endpoints remain: NOT timing-qualified or CDC/reset-proven. Resource fit alone is not hardware/model correctness.

`diagnostic-4e30-tile-only.fs` SHA256 `0325998685d3d41badd243829c979881fbb80e04fbb3d11c55affdf8126e49d8` is the exact generated image. Owned15source files match both build snapshot and current source at archival time. PicoISC license/pin/compiledmacro wrapper are preserved; encryptedDDR/IP and generatedVG/netlists are excluded and identified by hashes.

`rtl-core-final` is root's final actualPicoRV32/cache/8OCMAC/CPU-sequencedMatMul/CDC/DDR-adapter test, only DDRPHY fake:14 checked integeroutputs and39 packets with token/BUSY/unsupported0x78/79/latchedmonitor/CLEAR-before-nextSTART/ABORT-no-stale checks. It is not whole-model execution. `historical-resource-failure-full-v1` preserves the22035Logic overflow attempt separately.

No JTAG/COM access or physical programming was performed by this archival task. Physical trials, if later performed by the root agent, must be separate records. No full-model physical PASS is claimed here. Firmware code/data must be uploaded and readback-verified before EACH RUN; CLEAR alone is not a warm restart.
