# Experimental RAW-clock tagged reply frontend

Status: isolated `codex/gfx-fastreply` worktree based on54MHz vivid46dad1. This is not a measured cable limit. Canonical,27MHz verified, PLL54 baseline and PLL54-vivid worktrees are not modified. No pins, electrical settings, command values, packet lengths, capability values or CRC definitions change. Build variant: `triangle54fast`.

## Why this variant

The preceding54MHz synchronized frontend passed three10MHz CPU/GPU pairs, but the first16MHz TILE response failed payload CRC despite a valid header. Repeated data expected4d3a was observed as0e3a and periodically0a3a. That observation is consistent with a sampling/pipeline limitation and does not isolate a jumper electrical limit. Raising the system clock again could move the boundary, but it would retain the same round-trip synchronization dependency. This variant clocks tagged response progression directly from the existing T7/GCLKT_3 input instead.

Reviewed interface context: the actual ESP-IDF host/visual requirements and implementation at1810425c, Linux requirements/actualDTS atcfc9a6ec, MeOS carrier requirements at26c80829 and external-memory plan ate4aa69d0, as recorded in the palette/tile compatibility reviews. This change preserves their existing wire format. It adds no DDR or generic GPU implementation. Requests and untagged replies retain the existing SYS54 path; experimental higher clock points refer to tagged response RX, not a claim of40MHz GPIO request submission.

## Domains and ownership

| Domain | Owns |
|---|---|
| SYS54 | request CRC/parser, renderer and RAM writes, completed response metadata, packet offer, timeout and completion acknowledgement |
| RAW bus_clk | tagged byte index, current word/lookahead tags, header/payload CRC, done/started/error and progress state |
| Tile RAM | SYS read/write portA plus RAW synchronous read-only portB; contents immutable throughout the offered response |

The RAM has no producer racing the RAW reader. All1024 words exist before an offer, and SYS blocks subsequent commands/writes until done acknowledgement or abort. Therefore no asynchronous word FIFO or cross-domain cache watermark is required in this version. The inventory is the complete immutable tile. Existing row-cache data is also frozen until acknowledgement; its asynchronous byte-selection mux is controlled by RAW index. Computation/readback overlap would require separate banks and is outside this change.

Gowin [UG285 BSRAM guide](https://cdn.gowinsemi.com.cn/UG285E.pdf) describes independent port clocks in dual-port mode; the [official older guide](https://www.gowinsemi.com/upload/database_doc/6/document/5b5852bfdb1b1.pdf) and installed Yosys Gowin DP mapping expose CLKA/CLKB. For RAW-enabled builds, SYS write/read use the same portA address; writes imply tile_stream=false, so this is equivalent to the original renderer address. Tests assert this invariant. If technology mapping replicates RAM instead of sharing a dual port, report the actual cost; do not force an unsafe inference merely to preserve a block count.

## Four-phase packet handshake

1. SYS finishes the renderer/error/ordinary response and holds `valid`. It snapshots six header bytes plus bulk/tile flags before raising `fast_offer`. Snapshot registers remain unchanged through acknowledgement.
2. READY exposes the offer before DIR=1. The existing host guard and DIR=0 clock handoff hold RAW index at0; the first eight consumed RAW edges serialize exactly eightc3 prefix bytes. Metadata passes through two RAW register stages during that prefix, without adding any prefix bytes. Header bytes are not used until those stages have settled.
3. The master samples the old byte at physical rising CLK; the RAW serializer advances the next byte after that edge. Header CRC is folded once for each of six sampled header bytes; header CRC bytes are skipped in the bound CRC, and each sampled payload byte extends it once. Prefix is outside both CRCs. Header8, ROW74 and TILE2058 bodies remain unchanged.
4. Sampling the final CRC byte sets RAW done. READY and output enable drop immediately, before the later SYS synchronizer acknowledges completion. Done is held until SYS removes the offer and a RAW edge resets the packet state. Every following request supplies DIR=0 edges before a new offer, so a stopped RAW clock does not prevent recovery.

A RAW progress toggle every16 bytes crosses two SYS stages for watchdog progress; normal slow bus edges still drive the original watchdog path. Completion is a held level, not a pulse that can disappear between clocks.

## One-word lookahead in the RAW domain

RAW RAM portB loads word0 during the prefix and primes word1 during prefix/header clocks. A current16-bit word plus the RAM output form the two-word pipeline. Sampling low byte of wordN requests wordN+2; sampling high byte loads the already-read wordN+1. Both operations are in the same RAW domain. Address tags/valid flags are checked before use; a mismatch aborts rather than sending a stale complete image. There is no SYS54 index-to-RAM round trip between payload bytes and no full response array.

## Abort and reset

Raw ARM/reset/PLL-lock loss remove output drive asynchronously even when bus_clk is stopped. DIR=0 immediately removes drive; after a response has started it also drops READY and SYS cancels the outstanding offer. DIR=0 before the first read is legal and leaves READY available for the host handoff. SYS timeout removes offer/valid and hence output drive without needing a RAW edge. A new request resets RAW packet state before its next offer. No partial or CRC-invalid frame is accepted as a successful image.

Control tests stop CLK both HIGH and LOW, abort before/during payload, change DIR/ARM/reset, exercise PLL lock loss/relock, and verify next-packet recovery. Assertions check metadata stability and no RAM writes during RAW ownership. Only the parent hardware campaign may establish physical behavior.

## Constraints and verification limits

Actual nextpnr SDC explicitly constrains oscillator27MHz, internal core54MHz and RAW bus40MHz. No timing-allow-fail is used. The generic nextpnr parser's [set_false_path implementation](https://github.com/YosysHQ/nextpnr/blob/main/common/kernel/sdc.cc) currently reports that it is a no-op; this build does not pretend such an exception was applied. The reference SDC lists the intentional metadata/offer/done/progress crossings for a full CDC/STA review. Second synchronizer stages, same-domain CRC/index paths and both RAM clock domains must remain timed.

Host sample setup/hold, clock-to-pad delay and outgoing/return flight time require IO timing or waveform evidence. Three clock constraints do not certify those analog conditions. Models use fixed assumed delays and Tco values, not measured ones. RAW clocks are clock enables within sequential logic; no combinationally gated clock is introduced. The input remains T7 on the existing3.3V Dock wiring.

## Model matrix

- Ideal50% clocks5/8/10/12.5/16/20/25/32/40MHz; nine SYS phases and assumed one-way0/5/10ns. ID, ROW and pseudo-random address-varying TILE, both planes across the cases.
- Additional11/12/12.5/12.307692/13.333333/14/14.545454/15/16/20/25/32/40MHz TILE cases use assumed160MHz divider N/N+1 periods and shorter/longer half-cycle patterns, three phases, assumed Tco2/5ns and one-way0/5/10ns. Actual divider ordering/duty is not claimed measured.
- Every response byte and both CRCs are compared, not just a header. A separate assumed2ns host setup budget rejects zero-margin combinations even if ideal event ordering happens to match bytes.
- Legacy full golden suite runs with FAST_REPLY_ENABLE=1, so it exercises the changed RAM-port mapping while preserving the ordinary untagged path. Tagged tests include nonuniform polygon/fractal, legacy/vivid palettes, ROW/TILE color/depth, multiple sequences and malformed requests.

Before physical testing: freeze sources; pass technology mapping, resources and routed54/40MHz timing; inspect clock-domain reports/intentional CDC crossings; then run same-image5/8/10MHz controls before increasing frequency one point at a time. Save first-failure raw data and distinguish FPGA/P4 sampling, digital timing and electrical causes. No higher model pass is a cable-limit claim.

## Frozen build and regression evidence (2026-11-04 JST)

The first implementation mapped the SYS read-before-write behavior into distributed RAM and failed placement. The corrected RAW-enabled portA holds its read output during writes (NO_CHANGE); that output is unused while writing. Legacy non-RAW builds retain their original behavior. Installed Gowin TDP technology mapping supports this mode. The corrected routed build uses BSRAM2/46, RAM16SDP4=0, LUT5343/20736, DFF2141/15552 and MULT18X18 21/48.

The actual SDC initially logs bus_clk40MHz, but the aliased final platform.bus_clk report uses the stricter default54MHz target. It reports89.75MHz for that domain and68.66MHz for core54, both passing the logged54MHz targets. No timing-allow-fail is used. This is routed internal timing evidence, not precise external40MHz IO signoff.

Final regressions: 264 tagged/mixed wire transactions; 39 stopped-clock/control packets; RAW-enabled ordinary goldens ROW410, fractal991, bounding-box2432 and scalar10334; PLL/top reset and recovery checks. All1197 frequency-model cases match complete bytes/CRCs. Six assumed40MHz/10ns-wire/5ns-Tco cases fail the separate2ns host setup budget, leaving1191/1197 budget passes. These assumed values are not cable measurements.

Frozen image SHA256: `5b93ac88ffd9d45ad959e19da50e8af433dd8ca3fbc8ccb8f4e80ff1a1c391cb`. Parent hardware operator owns programming and physical validation; these tests performed no hardware access.
