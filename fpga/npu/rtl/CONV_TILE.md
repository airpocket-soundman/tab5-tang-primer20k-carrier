# Bounded INT8 Conv tile engine

`conv_tile_engine.v` is a host-neutral arithmetic kernel, not a wire ABI, DDR controller, model runtime, calibrated YOLO model, or measured board accelerator. It leaves pins and commands unchanged. The parent integration defines the transport separately.

## Arithmetic and layout

- Signed INT8, input and weight zero-point0, CHW input halo and OIHW weights.
- Kernel1 or3, stride1 or2. Host handles groups by selecting channel subsets and supplies explicit zero-padded halo, including image edges.
- IC block1..16, OC1..8, output height/width1..16. Input height/width must equal `(output-1)*stride+kernel`, max33 each.
- RAM bounds: input17424 bytes, weights1152 bytes, output2048 signedINT32 words. RAMs are not cleared/reset; metadata prevents uninitialised locations from entering valid jobs.
- No bias or requantization. First block starts each output at0. Subsequent channel blocks add to retained INT32 values. The caller must keep a consistent input/weight scale across blocks. FP32 bias/dequantization or INT8 requantization is external.
- Every add is widened to33bits. Overflow faults before updating that sum; the entire tile is invalidated. Partial sums must never be treated as a successful output.

## Interface sequence

All signals use the rising `clk` edge. Reset and abort are synchronous, active high, have priority, invalidate partial/published outputs and clear the latched fault. Hold all configuration through `load_start`; it is latched on that edge and does not need to remain stable during upload or compute.

1. Assert `load_start` for1 edge with `cfg_ic/oc/oh/ow/kernel/stride/input_h/input_w` and `first_block/final_block`. It is accepted only while idle and not faulted.
2. Wait for `upload_ready`. Supply `upload_valid`, `upload_kind` (0input,1weight), `upload_address[14:0]`, signed `upload_data[7:0]`. Each kind must start at address0 and advance exactly1 per accepted beat. The two streams may be interleaved. A repeated/missing/out-of-order/out-of-span address faults. `load_start` resets both upload counters.
3. Assert `start` for1 edge only after both exact spans have been uploaded. `busy` covers compute. Each accepted block eventually emits a1-cycle `block_done`; `compute_cycles` is the block activity count, saturating atUINT32_MAX.
4. For a nonfinal block, `output_valid` remains0 and its accumulations remain private. Next `load_start` must set `first_block=0` and retain OC/OH/OW/kernel/stride; IC count may differ in the final channel block. All per-block inputs and weights must be re-uploaded.
5. A successful final block sets `output_valid=1`. `read_enable` plus `read_address[10:0]` yields registered `read_valid/read_data` on that edge. Reads are permitted only for logical output indices0..OC×OH×OW-1 and only while idle with `output_valid`. `read_data` is0 whenever `read_valid` is0. Any invalid read faults and invalidates the tile.
6. A new first block may replace a published result, invalidating it at `load_start`. Starting an accumulation without a prior nonfinal block is rejected. Abort/reset is the required fault recovery and explicit cancellation path.

Error codes:1invalid configuration,2incomplete/invalid upload,3signed accumulator overflow,4state/read mismatch. Faults latch and block further operation until reset/abort. There is no internal watchdog: the maximum legal compute bound is fixed and the command wrapper must enforce its own deadline and cancellation policy.

## Implementation and evidence

The core uses synchronous-read inferred RAM. Each MAC needs a read cycle and a MAC cycle, plus3 cycles/output for accumulator load/wait/store: `OC*OH*OW*(2*IC*kernel*kernel+3)` compute cycles per successful block. This excludes host upload/readout and is not end-to-end inference latency.

`run_conv_tile.py` uses an independent NumPy INT64 sliding-window/einsum oracle. The normal suite covers all324 combinations of kernel1/3, stride1/2, IC1/2/16, OC1/3/8, OH1/2/16, OW1/3/16, plus a3-block IC16+16+3 accumulation. The final full run passed2156 blocks:327 shape/partial cases plus911 positive and918 negative legal-block accumulations crossing INT32 bounds. It additionally checks latched configuration, upload holes/repeats/missing data, premature reads, reset/abort, start while busy and overflow publication. Full mode also crosses the real positive and negative INT32 boundaries through repeated legal IC blocks; a separate injected-state test checks the boundary fail path quickly.

Standalone Gowin Education1.9.11.03 placement/routing at sys27MHz succeeded:773 logic cells,356 registers,21/46 BSRAM,5/24 DSP. Setup/hold violated endpoints0; reported standalone Fmax66.684MHz. It has no Dock constraints and its many top-level I/O pads are tool-assigned: **do not program this component bitstream**. These figures do not certify an integrated transport design, external I/O timing, full YOLO fit, or hardware performance. Reports are under `fpga/build/conv-tile-component/conv_tile/impl/pnr/`, synthesis script/log under `fpga/build/conv-tile-synth/`.

No board access, JTAG operation, pin/electrical/command change, or host driver change was performed by this component task. Host requirement references were rechecked from ESP-IDF Project_B, Linux DEVELOPMENT_GOALS, MeOS FPGA_CARRIER_REQUIREMENTS and the external-memory research plan. Existing model/transport integration remains owned by the parent task.

## Packet-wrapper regression

`npu/tests/run_conv_link.py` independently exercises `npu_conv_link.v` with SYS≈27MHz, bus500kHz:6 tensor/block jobs and101 packets passed, including2048-byte upload chunks,256-word read pages, full maximum tile, partial IC accumulation, header/tail CRC, rejected CRC uploads without numerical effects, invalid high fields before narrowing, invalid halo faults, partial direction changes, timeout, reset/DISARM OE and abort. Invalid engine configuration code1 maps to wire INVALID_PARAM3; overflow code3 maps to5. The other state/upload faults map to4. Proof: `fpga/build/conv-link-test-configstatus/{result.json,run.log,tb_conv_link.v,vectors.txt}`. No actual board transfer is implied.
