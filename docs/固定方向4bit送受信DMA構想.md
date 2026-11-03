# Fixed-direction 4+4 DMA link: research proposal, not an implemented interface

2026-11-03. Priority remains optimizing the existing eight-bit DMA transport and measuring its long tile bursts. This alternative must be a separate experimental FPGA image and host transport. No current pin, RTL or firmware behavior was changed by this research.

## Wiring and permanent ownership

| Signal | Owner and proposed function |
|---|---|
| GPIO18,19,5,3 | Tab5 permanently drives TX nibble bits0..3 |
| GPIO4,2,48,47 | FPGA permanently drives RX nibble bits0..3; Tab5 inputs |
| GPIO16 | Tab5 continuous session clock, shared by both directions |
| GPIO51 | Tab5 request VALID, replacing the old direction selector |
| GPIO45 | FPGA receive framing/VALID indication; precise mode must be resolved below |

There is no direction change or per-packet GPIO matrix change. The existing eight-bit image cannot be used with these meanings: its output-enable logic and DIR interpretation differ. Select the image/transport explicitly, leave outputs disabled until software ARM, and identify the new transport/version before sending drawing commands. Existing shared-bus hosts remain on their existing image. Carrier AGENTS host compatibility review is required again before finalizing this proposal as a specification. The versioned host review in `Dock完全タイル読出し.md` is useful background, but does not authorize this different physical transport.

## Official evidence and implementation limits

Official sources: [RX guide](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32p4/api-reference/peripherals/parlio/parlio_rx.html), [TX guide](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32p4/api-reference/peripherals/parlio/parlio_tx.html), and [P4 TRM](https://www.espressif.com/sites/default/files/documentation/esp32-p4_technical_reference_manual_en.pdf). Reviewed TRM is Pre-release v0.7, SHA256 `622fe9625d19cf00bd7aa49e65f0b5dd6ef2197f83cb7a88b4405078d6a957d4`. Local copy and reset requirements are recorded in the host `docs/ESP32_P4_PARLIO_RX_OFFICIAL_SEQUENCE.md`.

Reviewed IDF v5.5.2 commit `30aaf64524299d3bde422ca9a2848090d1bc5d0f`: [RX driver](https://github.com/espressif/esp-idf/blob/30aaf64524299d3bde422ca9a2848090d1bc5d0f/components/esp_driver_parlio/src/parlio_rx.c), [TX driver](https://github.com/espressif/esp-idf/blob/30aaf64524299d3bde422ca9a2848090d1bc5d0f/components/esp_driver_parlio/src/parlio_tx.c), and [P4 LL](https://github.com/espressif/esp-idf/blob/30aaf64524299d3bde422ca9a2848090d1bc5d0f/components/hal/esp32p4/include/hal/parlio_ll.h).

P4 has independent TX and RX Core clocks and a shared APB register domain (TRM61.5.2 pp3541–3542). Four-bit width is supported. TX VALID occupies internal TXD15, so it does not consume the four physical data outputs. RX VALID can be connected to an internal data-line index outside0..3, such as15, while data_width=4. Set all unused data GPIO entries to GPIO_NUM_NC explicitly.

The concrete clock arrangement is RX master: internal PLL/XTAL, clk_out_gpio_num=16, clk_in=-1, data_width=4, no clock gating. TX is external-clock slave: clk_in_gpio_num=16, clk_out=-1, input clock frequency declared and divider1, width4, bit-pack LSB first, VALID51. GPIO16 output-to-input loopback must stay enabled for TX input routing. Both units are created once while disarmed; configure GPIO16 input/output once, then start a continuous clock only during an armed session. Neither direction may perform the current experimental whole-group APB reset while the other unit exists.

RX `partial_rx_en=1` creates a circular descriptor chain, at least two descriptors; `owner_check=false`, `auto_update_desc=true` are the official driver's GDMA strategy. Its infinite EOF path keeps the transaction and does not gate/restart the clock. This is materially different from the failed soft-delimiter finite receive followed by per-response restart. Direct ring buffers require consumption before overwrite; callbacks must publish a descriptor/generation and copy or release it before DMA wraps. `indirect_mount=1` makes the driver copy in its ISR and has a CPU cost; it is not zero-copy. Descriptor counts, cache synchronization, RX overflow and missed generations must be exposed and checked.

**Important unresolved delimiter constraint:** TRM61.5.5 p3546 restricts external-enable EOF to pulse modes1/3; the IDF setter permits `eof_data_len=0` with a level delimiter as well. Thus READY-as-level with EOF on its falling edge is not accepted as proven. A first prototype must either use a TRM-supported paired-pulse framing mode on GPIO45 (with exact start/end inclusion verified against figure61.5-5), or use a continuous stream/ring with an independently validated EOF/chunk scheme. Do not silently assume that level framing is supported because the API accepts it. The TRM also warns that fixed bit-length EOF stops FIFO draining while incoming valid data can continue and overflow; descriptor loops alone do not prove unlimited reception.

TX public finite transactions still reset TX Core/FIFO and mount/start GDMA on every transaction (`parlio_tx_do_transaction`), even when external clock is free-running. They avoid pin handoff and RX reinitialization but do not eliminate every TX startup cost. A first fixed-direction prototype can measure that remaining cost. Fully continuous TX needs a deliberate ring backend or reviewed driver extension, not a claim that the existing API already provides arbitrary queued zero-reset frames. Existing loop transmission repeats data; it is not an ownership-safe command producer ring by itself.

One possible continuous TX backend uses logical data_width=8 but maps only bits0..3 to the four TX wires and bit7 to GPIO51. Each DMA byte then represents one nibble plus its VALID bit; bits4..6 are unmapped. Idle ring slots have VALID0, command slots VALID1. That permits in-band idle gaps without changing pin mux or dedicated-VALID configuration. It doubles TX buffer bytes relative to packed nibble mode and requires descriptor ownership/credit handling so old requests cannot replay. This is an additional design, not the first finite-TX implementation.

## Clock phase and FPGA framing

Keep clock running through idle periods, so both clock domains settle before the first valid packet. Launch output nibbles on one edge and sample on the opposite edge; initial phase must be verified against official master/slave timing (TRM61.5.3 pp3543–3544) and actual pad waveforms. No 40MHz or jumper limit is asserted. Begin at a measured-safe low rate, then5MHz only after CRC/sequence/stress validation. A new FPGA front-end can capture nibbles in the bus-clock domain and cross complete bytes or FIFO entries into27MHz sys_clk; this avoids treating the existing synchronized eight-bit frontend's frequency ceiling as a cable limit.

Preserve byte-level request/response opcodes, sequence and CRC where useful, but serialize each byte as low nibble then high nibble. Request VALID boundaries reset nibble alignment; reject odd nibble counts, malformed length, CRC or stale sequence before dispatch. Responses need explicit framing, sequence, length and bound payload CRC; incomplete frames are discarded, never reconstructed. Request FIFO depth2–4 and a response descriptor queue allow short commands to be queued while an earlier response transfers, subject to explicit credits. A second color/depth tile bank is required before computation can modify a tile whose response is still streaming. It costs another4096 bytes of FPGA RAM; otherwise stall writes until readback completes. Additional parallel arithmetic lanes are not implied.

Startup: data outputs disabled; allocate both units/rings and configure fixed directions; hold FPGA request VALID inactive; configure/reset once in official APB→GDMA→Core order; establish clock and settle while no valid data; arm RX ring; enable request producer; verify identification/CRC. Stop/error: block producers, deassert request VALID, finish or explicitly abort outstanding DMA, stop both units, then stop clock and release outputs. No automatic replay or fallback after an unknown packet outcome.

## Cost comparison and decision gates

At5MHz, eight-bit payload capacity is5MB/s and four-bit is2.5MB/s before framing. A160×96 RGB565 frame is30720 bytes: ideal payload time6.144ms versus12.288ms. Existing complete-tile reads already remove most row-sized DMA setup overhead. Fixed4+4 can win only if saved setup/CPU time or compute/transfer overlap exceeds the narrower-link cost; it is not automatically faster.

A candidate four-descriptor RX ring of2176 bytes each uses8704 bytes; a two-block1024-byte TX producer uses2048 bytes. Add one2058-byte validated tile body and2048-byte word staging: approximately14858 bytes plus descriptors, queues and metadata. This is a design budget, not linked RAM consumption. The present long-burst path uses approximately2176-byte DMA storage,2176-byte raw capture,2058-byte body and2048-byte staging (8458 bytes before other state). A continuous embedded-VALID TX ring may need a larger producer budget. Check linker map and heap high-water marks, not these arithmetic estimates alone.

Compare three measured implementations on identical frames: current eight-bit long-burst baseline; optimized eight-bit official DMA lifecycle/alignment; fixed4+4 prototype only if needed. Record total frame time, CPU-active time, device cycles, DMA setup/IRQ counts, RAM/map deltas, FPGA LUT/FF/BRAM/DSP and routed timing. Adaptive pin widths add protocol/state complexity and are a later option, not part of this fixed-direction proposal.

### Existing eight-bit alignment investigation

TRM p660 and section6.4.8 p667 state that GDMA-AXI data addresses and lengths in internal/non-encrypted memory have no alignment requirement (AXI descriptor addresses need8-byte alignment). AXI bursts are always enabled and can be8/16/32/64/128 bytes. Therefore the current24/90-byte EOF lengths cannot be labeled documented misuse merely because they end in a partial burst. Testing32/128 or128/128 captures remains a controlled driver/silicon diagnostic; success would need explanation and repeatability. TRM p663 also says the unused tail of a buffer after a short reception is not reused in the next transaction. These facts help separate FIFO/counter state, descriptor generation and application framing from an assumed universal alignment rule.
