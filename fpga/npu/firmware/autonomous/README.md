# FPGA-local autonomous RT-DETR firmware (experimental)

This is firmware for an RV32IMC soft processor **inside the FPGA**, using the existing FPGA INT8 Conv MAC hardware (also used for matrix products). Tab5 performs upload/UI only. It is a distinct architecture from dedicating a separate hardware circuit to every graph operator. The soft processor implements non-MAC math, quantization, scheduling and input RGB conversion. Compilation does not prove FPGA resource fit, full execution, numerical qualification or acceleration.

The portable graph/backend sources are byte-exact pinned copies from host `d5eca70`; `vendor/host/PINNED_SOURCE.json` records SHA256. The carrier repository owns this FPGA firmware integration. No ESP-IDF, GPIO/PARLIO host call or hidden P4 fallback is linked.

## Build

Run `python fpga/npu/firmware/autonomous/build.py --output build/npu-autonomous-firmware-v7`; add `--smoke` for the self-checking Tile+Matrix test. The default installed Espressif baremetal toolchain is GCC14.2, RV32IMC soft-float ILP32, FMA contraction disabled. The compiler-selected multilib name contains zicsr/zifencei; generated instructions must be audited against PicoRV32. The current build has no F/A/CSR instructions; one intentional EBREAK remains in the newlib abort path. All full-graph FP32/FP64 arithmetic/libm runs on the FPGA-local processor.

## Memory and launch

| Region | Address | Contract |
|---|---:|---|
| Model constants | `0x00010000` | Exact verified RQG2 payload |
| Model activation arena | caller `arena_base` | Page-aligned after constants; validated by typed loader |
| MAC scratch | caller `scratch_base` | Page-aligned after arena, bounded strictly below80MiB |
| Firmware entry/text/data/BSS | `0x05000000` | Uploaded binary, entry fixed; linked below88MiB |
| RQG2 metadata | `0x05800000` | Header/tensors/nodes/bindings, <=1MiB |
| Raw RGB640 input | `0x05900000` | 1,228,800 bytes; FPGA CPU converts RGB to BGR FLOAT0..255 |
| Heap | `0x06000000..0x06ffffff` | Separate16MiB region |
| Stack top | `0x07fe0000` | Descending; reserve at least256KiB beneath |
| Mailbox | `0x07ff0000` | Uncached/write-through shared result/control |
| Accelerator MMIO | `0x10000000` | Separate from physical128MiB DDR |

Before **every** CPU release, host uploads the complete firmware BIN (including initial `.data`) and verifies readback, then uploads metadata/payload/raw RGB and initializes `AutonomousMailbox` (ABI1, magic `0x31545041`, command1, nonzero token, layout). Firmware verifies source model identity, typed metadata CRC and complete payload CRC before inference. Model/activation/scratch callbacks cannot access firmware, metadata, heap, stack or mailbox regions above80MiB.

The full model is the experimental RT-DETRv2-R18 Wholebody25 derived300 graph:649 nodes,57 Conv and65 MatMul/Gemm. The model/source SHA and final shape1800 FLOAT values are enforced. Only after all operators and MAC counts, epoch/memory health, finite/class/score checks succeed does firmware publish result address/count, token and `AP_COMPLETE`. A failed or cancelled run publishes no output count. This does not yet establish equality to P4/native output; platform rounding differences remain a separate qualification problem.

CLEAR alone is not a warm restart: this prototype resets BSS but does not restore mutable `.data` from an immutable ROM LMA. Reuploading the whole BIN on every RUN is mandatory; no resident/warm CPU-run guarantee is made. Proper LMA-to-VMA startup copying is a future distinct revision.

## Resource-selected V7 profile

The full-chip hardware Matrix sequencer configuration exceeded device logic capacity (root synthesis evidence is separate). V7 therefore defaults `AUTONOMOUS_SOFTWARE_MATRIX=1`: `nd::matrix` expands the same N8/M256/K16 descriptor sequence in the FPGA-local CPU, issuing **Tile COMMAND1 only**. Matrix arithmetic still executes in hardware INT8 MAC; no P4 operation or CPU matrix multiplication is substituted. Current tile-only4E30 rejects hardware Matrix COMMAND2. The legacy optional COMMAND2 description in `abi.h` does not imply this capability exists in the resource-selected image. High-level graph counts remain57Conv/65MatMulGemm, backend matrix macros13067, while total hardware Tile commands become400368.

The internal backend `Execution::Matrix4E24` enum identifies the pinned software backend contract; it is not the public4E30 capability response. V7 preserves exact input/weight/output layouts, padding and accumulation order from the RTL sequencer. V6 with hardware sequencing and older V5 startup proofs remain historical, not the current deployment image. Startup BSS symbols now live inside the actual aligned `.bss` section; `validate_elf.py` rejects the old V5 layout and is mandatory in the build helper.

## Accelerator and coherence

`abi.h` is the isolated internal CPU ABI, **not a published host wire command**. STATUS bits0 READY,1 BUSY,2 DONE,3 ERROR,4 QUARANTINED,5 RESULT_VALID,6 MEMORY_READY. Epoch is at+0x18. Descriptor words at+0x40 preserve existing52-byte Tile /36-byte Matrix formats. COMMAND+4 is1 Tile or2 Matrix, ACK+8 clears completion, ABORT+12 requests cancellation. NODE/STAGE/APP_ERROR/FINISH at+0x20/+0x24/+0x28/+0x2c expose application progress, with FINISH1 success/2 failure.

A nonfinal IC Tile produces DONE without RESULT_VALID; the wrapper requires validity only for a final Tile or complete Matrix. No invalid result, hardware error, calibration/epoch change or timeout is retried or repaired on P4. The CPU bridge must commit CPU stores before COMMAND and invalidate data cache before completion becomes visible; mailbox is uncached. V1 COMMAND stores can block until MAC completion, so hardware timeout and external abort must work independently of firmware polling. Instruction-cache contents are immutable during a run.

## Proof boundaries

The smoke firmware fills its own DDR inputs, issues one real Tile and one real Matrix descriptor and checks14 INT32 outputs against scalar integer arithmetic running on the FPGA-local CPU. It needs zero-initialized fake/physical DDR, memory-ready and a stable captured epoch; no NN model. Full firmware, tiny CPU RTL execution, ISA interpreter execution, real DDR/core integration, synthesis/PNR and physical whole-model completion are separate gates. Retain failures and report which gates actually ran; do not promote a host integer oracle or compiled ELF to physical FPGA inference.
