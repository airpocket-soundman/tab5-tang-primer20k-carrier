# DDR-backed Conv tile integration notes (proposal, not implemented)

The existing `mem/mem_adapter.v` is a suitable verified lower layer to reuse, not replace. It operates in the DDR USER domain (~99.56MHz), one outstanding command, READ/WRITE/CRC over1..256 aligned128bit beats (4KiB). It preserves the registered command/write pairing and app row-padding address mapping used by the qualified memory design. Errors include calibration loss, timeout, cancelled prefix writes and read ordering. Reusing its interface does not by itself qualify a new NPU integration.

## Proposed data path

Keep Conv in SYS27MHz; standalone Fmax66.684MHz is below the existing USER99MHz clock and does not justify clocking it at USER speed. Submit DDR requests using the held-bundle toggle bridge pattern, and use4KiB128bit dual-clock staging RAM for USER→SYS input and SYS→USER output. A SYS scheduler gathers a padded input halo and each output-channel weight span into the existing Conv upload interface, runs the IC block, then repeats channel blocks without P4 tensor transfers. On final completion pack INT32 results into128bit beats and write them to DDR. Distinguish upload/gather, MAC activity, output writeback and full descriptor time in counters.

For dense NCHW input, compute each channel/row byte span with64bit range checking. Align read address down16, read ceil((leading_skip+copy_bytes)/16) beats, drop leading/trailing bytes, and synthesize zero padding outside image bounds. OIHW weight spans must use the full Cin/group stride; a block of16 input channels is not necessarily adjacent across output channels. Partial groups and odd channel counts cannot be treated as power-of-two strides.

**Write hazard:** `mem_adapter` writes complete128bit beats with mask0. A dense FP32 output width5 has a20byte row stride and is not16byte-aligned. Rounding writes outward would corrupt neighboring rows/tensors. Prefer explicit row_pitch=align16(width×element_bytes), channel_pitch=row_pitch×height and16byte-aligned tensor regions in the DDR package. Tail beats then land in owned padding. If dense layouts must remain supported, do a read-modify-write of edge beats while the scheduler owns the adapter exclusively.

## Ownership and failure

The present MEM top multiplexes native DDR between BIST and the MEMV1 bridge. Add a command owner/arbiter with NPU idle entry, rather than arbitrating arbitrary individual native beats. A descriptor may start only after calibration/settle and with no BIST/host transaction outstanding. Drain or cancel before switching owners. Tag/generation mismatches, calibration loss, explicit cancel and timeout invalidate the entire output tensor; incomplete DDR write prefixes are not rolled back and cannot be published as a successful graph value. Retrying a failed output must use a fresh generation/region or overwrite all logical bytes before publishing.

## Full graph requirement

Moving Conv tiles into DDR solves only that operator's transport. A FP32 CPU graph still needs activation tensor access for Sigmoid/Mul/Add/Concat/Pool/Resize/Softmax/head etc. To claim that only initial image/final boxes cross the link, those consumers must also stay device-side (static INT8 tensor scales, requantization and the necessary operator engines, or a graph processor), with a bounded complete-graph lifetime plan. Weight size alone is not an activation/workspace peak or proof that the model fits128MiB.

A descriptor must include tensor addresses and byte strides, true logical shape, Conv/group attributes, input/weight/output quantization contracts, output region generation and measured deadlines. This note does not assign wire commands, change pins/electrical conditions, implement DDR DMA, or establish multi-OS driver compatibility. The parent task must cross-review that specification with ESP-IDF/Linux/MeOS and the memory research requirements before adopting an ABI.
