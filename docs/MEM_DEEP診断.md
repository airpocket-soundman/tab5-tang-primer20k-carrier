# Optional deeper native MEM observation

Experimental standalone MEM only; no GFX, pin, voltage, native controller handshake, pattern or timeout change. Original cc7a/990E image and its failed14-command/15-data trial remain frozen. SYSQUERY20 returns014f. SYSQUERY21..36 returns16words from the same SNAPSHOT58 generation as32base and11existing014e diagnostic words. Query cap8 remains014e; no implicit fallback. Read SYS flags6 and generation7 after ALL59words; reject stale/context-loss/torn generation. No BIST or recalibration is implicit in diagnostic capture.

## Held bank layout

Words0..3 raw64 bits (unused26..63 zero): bits0..2 command write pointer;3..5 command read pointer;6command full;7command empty;8/9command full delayed1/2;10command accept;11scheduler send_wr;12write almost-full;13write empty;14eye command ownership;15eye address ownership;16..20write read binary pointer;21..25write write binary pointer. Words4..5 count command read-pointer advances modulo8 per USER edge;6..7 count write read-pointer advances modulo32;8..9 count USER cycles with send_wr high. Word10 bit0 marks first-fault frozen observation; all remaining bits/words zero. These counts are controller-side observations, not proven DDR write completions or chip capacity.

All selected sequential source drivers use clk_out. The two exposed combinational event flags are sampled in this same USER domain. No direct taps cross to SYS. The monitor retains observation every busy edge and freezes the last busy-edge observation when the first native transaction fault appears. Later cleanup/CANCEL cannot replace it; START clears it. Pointer modulo rollover, counters, freeze, cleanup, new job and reset are tested. A clock/reset loss invalidates bank freshness through existing sticky quarantine, so a stale held bank cannot claim current hardware state.

## Output-only vendor attribution

prepare_deep_taps.py accepts ONLY public generated VO SHA4d37c875c609a5fa849033d8fbea3e63d3da8270322a663deff01f44874719ed. It adds one64-bit output plus26signal assignments and constant zeros; removing those additions recovers every original byte (including CRLF). No primitive, parameter, input, original wire, protected source or functional driver is modified. The audit records exact original signal names, cell types/ports and actual USER clocks. This is observability fanout, not a functional IP patch. Tcl uses only the transformed public VO in this isolated worktree.

## Compatibility review

Reviewed unchanged host versions: Linux cfc9a6ecf7daa4c5e3decbe3885b22c2bd2f4cd1 (README, DEVELOPMENT_GOALS, Device Tree and current driver absence); MeOS26c8082961b1152901475fb56bbb2e8be192a4da (README, FPGA_CARRIER_REQUIREMENTS and existing scalarGPIO/GFX); Linux memory research e4aa69d09b2643d6f62fe686ef0f3284b109c541 (explicit bounded external-memory study, not transparent main RAM); actual ESP integrated18c763b962bb5de7aafddd63e3ae47e8ba8cf9cc (Project_B requirements, communication/display). All three ordinary OS implementations lack this standalone deep MEM diagnostic; no updates are required for existing GFX. A new isolated GPIO-only ESP diagnostic derivative is required to use014f. This optional capability adds no claim of Linux main RAM or physical DDR capacity.

## Offline qualification

Full official Education1.9.11.03 synthesis/PnR completes; all data setup, hold, recovery and removal negative-path lists are empty. USER Fmax82.369MHz for81MHz, SYS73.893 for27MHz. Existing90finite vendor exceptions unchanged; owned monitor and mailbox remain timed. New held bank uses max60ns plus the existing SNAPSHOT acknowledgement/settle contract;123variable destinations and133constant bits are explicitly audited. Existing152variable014e diagnostic destinations also checked. Pin/CST review unchanged. Tests:21BIST,122mailbox,39reset/abort,7LINK,621C checks, monitor rollover/freeze and nonvacuous vendor clock-init cone. No physical memory success is claimed.

FS SHA256 dbcd88fdc3d12fead7f5de9bd653866d5fbe4ec7eb9a3bd8f71cf4dcb088844b; UserCode00000F25 independently matched FS header/footer. See fpga/validation/mem-deep-diag-prehardware-2026-11-04.json for exact source, transformed VO, constraints, reports and test hashes. Hardware is not authorized by these offline results; parent review/programming is separate.
