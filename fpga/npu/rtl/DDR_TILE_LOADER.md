# DDR Conv tile loader (2026-11-07)

`npu_ddr_tile_loader.v` is an independent SYS-clock scheduler around `conv_tile_engine`. It has no DDR PHY/pins and does not define a host command ABI. It gathers DDR-resident INT8 input/weights, computes a bounded Conv channel block, retains nonfinal sums in BRAM, and writes a successful final INT32 output tile back to DDR. It does not execute an entire graph or requantize/dequantize.

## Control and descriptor

Use SYS27MHz. `memory_ready` must already be synchronized into SYS and mean calibrated, settled and granted exclusive ownership of the adapter/staging buffers. `start_ready` requires idle, no fault/quarantine/outstanding request and ready memory. Pulse `start` with the full descriptor, which is latched; live inputs may change afterward.

- `cfg_ic/oc/oh/ow/kernel/stride`, `first_block/final_block`: the existing kernel limits IC1..16, OC1..8, OH/OW1..16, kernel1/3, stride1/2.
- `input_full_h/w` are unsigned16bit logical source dimensions. Signed32bit `input_origin_y/x` locate the halo's first pixel; negative/outside coordinates produce zero padding, without invalid DDR reads.
- `input_base` points to the selected first input channel. `input_row_pitch` and `input_channel_pitch` are bytes. Row pitch must cover logical width and channel pitch cover full logical height.
- `weight_base` points to selected OC0/IC0. `weight_oc_stride` is the complete padded OIHW span between output channels; IC/kernel elements within one OC span are dense bytes.
- `output_base` is the selected output tile/OC0 address. `output_row_pitch/channel_pitch` are bytes, each16B aligned. Base must be16B aligned, row pitch cover align16(OW×4) and channel pitch cover OH rows. INT32 results are little endian.
- `output_tail_owned` must be true if OW is not a multiple of4. Last-beat unused words are zeroed and belong to this output region; unowned tail writes are rejected rather than silently clobbering a dense neighbor.

Ranges are checked with64bit arithmetic against CAPACITY (default128MiB). Output overlap with either selected input or weight ranges is rejected conservatively, including stride gaps. No DMA request is issued before field/range checks finish. Address products use one fixed16-cycle shift/add unit for six descriptor products; runtime row/channel pointers increment without wide multipliers. Setup adds roughly100SYS cycles, not a new external request or buffer.

For continuation `first_block=0`, the prior successful nonfinal context must exist. Shape/kernel/stride/origin/pitches/output destination must match. Input base must equal previous input base+previous IC×channel pitch; weight base must equal previous weight base+previous IC×kernel². Thus IC blocks ascend contiguously. The caller owns consistent scales, group/channel selection and true full-layer channel count; this kernel cannot detect an intentionally premature final flag without full graph metadata.

`block_done` pulses only on success. For nonfinal blocks no output DDR writes occur and `result_valid=0`; private BRAM sums are retained. On final success `result_valid=1` only after every output row WRITE has completed successfully. A new descriptor or loss of memory_ready invalidates the prior publication. `kernel_cycles` counts only the current IC block; software must sum blocks for layer totals.

## Memory master interface

The ports directly match the existing held-bundle MEMV1 protocol: `req_t/cancel_t`, frozen `h_op/h_addr/h_beats/h_arg/h_tag`, `done_t/r_tag/r_status/r_beats`; write staging `w_we/w_addr/w_data` and synchronous read staging `r_addr/r_data`. `h_op` is0 READ or1 WRITE; requests are16B aligned with1..256128bit beats. Tags increment per request. Metadata is registered one SYS cycle before req_t toggles and remains frozen until matching completion/drain.

Reuse `memv1_bridge`, `mem_adapter(APP_ROW_PAD=1)` and `memv1_dpram` unchanged. The native DDR bank/row mapping is preserved; app_addr is not a plain byte_address/2. Each input row and weight span is aligned down16 for fetch; leading/trailing bytes are dropped before sequential Conv upload. Only owned output beats are written. There is no full-tensor P4 readback in this path.

Do not combinationally switch independent clients' req_t/cancel_t into one bridge: different stored toggle levels can fabricate a request/cancel. A SYS arbiter must adopt per-client toggle references, copy/freeze metadata before a central request toggle, freeze ownership until completion/cancel drainage, and demultiplex replies. Alternatively use separate bridges/adapters/staging and freeze the native USER owner. Staging buffers may not be overwritten by a host client while NPU owns them.

## Errors, cancel, reset and counters

Error codes:1 descriptor/continuation,2 kernel configuration/upload/read handoff,3 accumulator overflow,4 internal state,5 memory unavailable at start,6 adapter nonzero status or incomplete beat count,7 local deadline,8 explicit cancellation,9 calibration/tag fault. `mem_status` retains the adapter's raw status. Failed output regions may contain a written prefix and are never published; no rollback is claimed.

`abort` invalidates the job and the private kernel. With a memory request outstanding it toggles cancel once and waits for a matching tagged reply. A wrong tag also enters this cancel/drain path; unrelated completions cannot satisfy it. Missing matching cancel acknowledgement hits a second finite deadline, asserts `quarantined`, holds metadata and blocks all reuse. `clear` is ignored in quarantine or while a request remains outstanding. A coordinated controller/adapter/loader reset or a higher-level quiesce/recalibration sequence is required. Do not reset only this loader while allowing an old native transaction to continue.

`clear` clears a drained fault and invalidates partial/public outputs. Memory-ready loss while idle also invalidates them. Counters saturate atUINT32_MAX: total_cycles (descriptor busy), ddr_wait_cycles (completion/cancel wait), read_beats/write_beats (confirmed beats from captured normal responses). Drain/failure counters are not an exact physical DDR traffic meter; partial writes may have occurred. They do not substitute for end-to-end model latency or ownership accounting.

## Verification scope

1. `run_ddr_tile_loader.py`:45 numerical descriptor jobs against an independent INT64 oracle and a complete256KiB DDR/guard comparison. Includes max tile, unaligned and odd pitches, signed/extreme origins, IC16+16+1-style partials, full logical W40000/H6000, no reads for zero regions, zeroed owned tails. Fault checks reject bad alignment/pitches/ranges/overlap/tails and mismatched continuation before DMA; exercise unavailable memory, status/beat-count errors, cal loss, abort during memory/kernel activity, partial WRITE, unexpected tag with matching cancel ACK, no ACK quarantine, finite timeout, clear denial and coordinated reset recovery.
2. `run_ddr_adapter_integration.py`:same45 numerical descriptors with the actual unchanged bridge/adapter/dual-clock staging RTL, SYS≈27MHz and USER≈99.56MHz, APP_ROW_PAD1, randomized native command/write-ready stalls, mock native memory. Full DDR contents and guards match. No PHY/electrical validation is implied.
3. Gowin Education1.9.11.03 synthesis-only: kernel+loader uses4702 logic cells (23%),2278 FF (15%),21 BSRAM (46%),5 DSP (21%). No additional DSP beyond standalone kernel after address-multiplier optimization. Top has984 internal interface bits mapped to hypothetical I/O by synthesis; it was deliberately not placed/routed and no component bitstream should be programmed. No integrated Fmax or board-fit claim.

Proof directories: `fpga/build/ddr-tile-loader-final`, `fpga/build/ddr-tile-realadapter`, `fpga/build/ddr-loader-component/ddr_loader/impl/gwsynthesis`. Existing SRAM NPU bitstream, DDR code and device state were not changed by this task. New wrapper/top/commands and actual DDR hardware validation belong to the parent integration.
