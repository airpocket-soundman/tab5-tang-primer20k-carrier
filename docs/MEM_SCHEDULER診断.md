# Optional scheduler observation024f

Isolated from ready-strobe11d7b04/801f/A40E. Native BIST, monitor, DDR configuration, pins and clock constraints unchanged. Only output observation/schema/capability change. SYSQUERY20=024f mandatory;21..36 retain16words under the SAME SNAPSHOT58 generation as32base+11native words. Old014e cap8 preserved. Old014f decoder must reject024f. No native behavior change, fallback, implicit START/retry/recalibration.

## Raw layout and unavailable bits

Original raw0..25/counters unchanged. Raw26/27=head write/read;28=pre_info_valid;29/30=issueW/R;31=init_done_r;32..57=partial bank-state vector;58=refresh;59=self-refresh;60/61/62=separate idle1/2/3;63=init-enable. Words4..9 remain command-read-pointer advances, write-read-pointer advances, send_wr high cycles; word10 bit0 frozen first fault; remaining words zero. These are controller observations, not proven DRAM completions.

Public VO declares26state bits but positions1,4,12,19,23,24 have no bit reference, driver, consumer, whole-vector or dynamic-index connection beyond declaration. Audit checks all references and20actual USERFF sources. OUTPUT ONLY explicitly zeros unavailable positions: valid mask0277EFED, exported unavailable list. Never invent aliases to separately named idle flags or interpret partial vector as numeric state ID. Held bank has155variable+6unavailable zero+95reserved zero bits. First unmasked candidate was rejected by CDC coverage gate and preserved offline, never programmed.

## Equivalence, clocks and host impact

prepare_deep_taps.py accepts exact public VO SHA4d37c875c609a5fa849033d8fbea3e63d3da8270322a663deff01f44874719ed. Removing added output port/assign/mask logic recovers original bytes including CRLF. No original primitive/parameter/wire driver or protected code changed. Sequential and command-RAM drivers use clk_out; recursive issueW/R/init-enable cones terminate only at USER FFs. First-fault last-busy capture precedes cleanup. Existing SNAPSHOT held60ns/ack-settle contract remains; all155new+152old variable destinations audited, constants separately listed.

Reviewed unchanged host versions: Linuxcfc9a6ecf7daa4c5e3decbe3885b22c2bd2f4cd1 README/DEVELOPMENT_GOALS/DTS/driver absence; MeOS26c8082961b1152901475fb56bbb2e8be192a4da README/FPGA_CARRIER_REQUIREMENTS/scalarGPIO/GFX; memory-researche4aa69d09b2643d6f62fe686ef0f3284b109c541 bounded external-memory plan; actualESP integrated18c763b962bb5de7aafddd63e3ae47e8ba8cf9cc Project_B/transport/display. Optional standalone024f remains unimplemented in ordinary Linux/MeOS/ESP GPU; existingGFX unaffected. New isolated GPIO-only diagnostic host required. DDR is not transparent Linux main RAM; configured128MiB documentary, physical capacity unknown.

## Offline qualification only

21BIST/122mailbox/39abort/7LINK/622C, wide-field monitor/faultfreeze,64randomREADY jobs1728events and nonvacuous vendor clock-init model pass. Official Education1.9.11.03 synth/PnR complete; all4STA negative lists empty. Setup+.341ns, hold+.234, recovery+2.281, removal+.575; USER83.300MHz for81, SYS58.439for27. Existing90finite vendor exceptions unchanged, no new blanket exception; pins unchanged.

FS845dd60ac5db134d8e68769883633d28522dbfbf9160f61f0c22387c4c6de169; parsed header/footer User0000579E. Exact manifest fpga/validation/mem-scheduler-diag-prehardware-2026-11-04.json and gz archive adjacent. No hardware by this agent; restricted trial remains parent-reviewed. Root cause unresolved until observations exist.
