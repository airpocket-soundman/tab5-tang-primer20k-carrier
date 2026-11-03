# Standalone MEM native-channel diagnostic extension

2026-11-04. Isolated carrier `codex/mem-native-diag`, based on frozen658c893/FS62ffa7262ab2386ef481be53eecacf33d734023cf7d4d12df1cb3da10bcb5592. No handshake, timing frequency, geometry or pin change is authorized in this candidate. It only observes the existing native interface.

## First physical trial, not a memory PASS

Parent performed one64-beat (1024-byte) BIST trial with GPIO-only host acba/ELFb0d2. Official programmer operations2/74/73 all returned0, status6020, UserCode7A8B. IP calibration/readiness was signalled, START acknowledged job1, then WRITE phase failed with native no-progress error3 at8,100,008 USER cycles. Verified beats0 and data mismatch count0 do not prove a write/read succeeded. LINK CRC failure was not reported. No retry was made and software was disarmed.

Frozen source, FS, STA, source/config, program logs and byte-exact raw trial are archived under `fpga/build/archived-mem-guarded-658c893` in the previous worktree. Raw JSON SHA256 b99a97e47741c16ebd2a4dbe809cd20071543584f8da00250a2241076f508303. Archive inventory has50 files. That archive and old worktrees remain unchanged. A native stall is not attributed to the jumper-wire LINK from this evidence.

## Host review before additive ABI

Linux cfc9a6ec README/DEVELOPMENT_GOALS/actualDTS and MeOS26c80829 README/FPGA_CARRIER_REQUIREMENTS/actual low-speed drivers remain unchanged since review; MEM/diagnostic integration is unimplemented. External-memory research e4aa69d0 README/Project_A requires explicit bounded transfers/tests, not transparent Linux RAM. Actual ESP main512cbdb9 and integrated18c763b are GFX-oriented; the isolated MEM probe acac1c0 implements only selectors0..7. The new isolated host derivative is based on acac1c0 and must explicitly require diagnostic capability014e. Existing MEM_CAPS014d, commands50..5c, snapshot32-word layout and selectors0..7 remain unchanged. No other host update is needed for existing operations. All pin/electrical conditions stay unchanged.

## Approved diagnostic selectors

All selectors use existing MEM_SYSQUERY5c, `a=selector,b=0`. Selector8 returns diagnostic capability014e without requiring a snapshot. Old images return invalid-argument3; explicit diagnostic mode fails closed and never silently falls back. Selectors9..19 require a successfully held snapshot and share its generation from SYSQUERY7.

| Selector | Value |
|---|---|
|9|native flags, current or first transaction-fault latched|
|10..11|beat index32, low16 first|
|12..13|accepted native command count32|
|14..15|accepted native write-data count32|
|16..17|received native read-data count32|
|18..19|last accepted native command address27, low16 first|

Flags bits0 command-valid,1 command-ready,2 write-data-valid,3 write-data-ready,4 command-sent,5 data-sent,6 read-pending,7 inter-beat gap,8 read-valid,9 USER reset released,10 calibrated,11 first transaction fault latched,15..12 first transaction fault code. The fault code is the BIST transaction error3/4/5/7/8/9; mismatch6 is already reported by the original snapshot. Before a transaction fault, diagnostic fields reflect current state/cumulative accepted operations. On the first transaction fault they freeze before state flags are cleared, including any handshakes accepted on that edge. Later cleanup CANCEL cannot overwrite that first evidence. Reset/recalibration/new valid job clears the diagnostic epoch. Index and counts describe128-bit native application beats; address is the native rank/bank/row/column word address, not BYTE first-error address from the original snapshot.

USER diagnostic bundle is frozen on the same SNAPSHOT request as the original512-bit bundle. SYS copies both only after the same synchronized acknowledgement/settle interval. The11 diagnostic words are read from a held SYS bank; generation and health/stale flags must be checked after all original/diagnostic words. The new bundle has its own explicit max-delay/hold contract and routed coverage audit. No asynchronous live bus is read directly by SYS.

The host diagnostic action/tool is read-only: explicit software ARM/CAPS, DIAG_CAPS, SNAPSHOT,32 original words,11 diagnostic words, then SYS flags and generation. It must not implicitly configure, START, CANCEL, RECAL, retry or substitute results. A new BIST reproduction, if needed, remains a separate explicit bounded operation by the parent hardware operator.

Next gates: fault-latch/count/backpressure/CDC consistency tests, old regression, guarded official synthesis/PnR/STA/pin checks, exact source/FS freeze, then parent review and hardware operation only. Configured128MiB remains document-based and physical memory correctness/capacity are unproven.

## Diagnostic build qualification

21 native BIST scenarios pass, including command-only, data-only and eight-beat stalls, accepted counters and preservation of the first transaction fault across cleanup CANCEL.105 mailbox commands verify all11 held diagnostic words, unchanged generation and preservation after a stopped-clock deadline.39 native/reset tests and7 pin-level LINK packets remain passing. Portable C codec604 checks and the original non-vacuous116-cell vendor clock-init test pass. No native command/data handshake condition was changed.

The new176-bit held diagnostic bank uses the original SNAPSHOT acknowledgement/settle window (minimum123.457ns) with60ns maximum delay. Routed coverage asserts all152 variable destination bits are present;24 constant-zero bits are the zero extension of three26-bit counters and the26-variable-bit native address. All covered paths have positive slack. Counters fit the bounded maximum job: at most4*8,388,608 accepted commands, plus no-progress/fault handling, within26 bits. Wire representation remains32-bit little-endian words.

Official Education synthesis/PnR/STA pass with unchanged finite90 vendor exceptions and no owned state-reset waiver: data setup+0.927ns, data hold+0.307ns, recovery+2.265ns, removal+0.453ns. USER Fmax87.573MHz for81MHz, SYS72.055MHz for27MHz. Logic5600/20736, registers5801/16173. The66 constrained positive/differential port entries still match balls/types/voltages. This is internal timing/constraint qualification, not a DDR physical success. Native FS SHA256 `cc7a76bd2f98287f9fa53ebf79a1ae464e5b597d495cdf46b303ff8156f0c822`; native UserCode `0000990E`, independently matched between the FS header and footer command. The original first-trial image has UserCode `00007A8B`; the diagnostic image is distinct. Verify image SHA256, programmer UserCode and runtime capability `014e`. Full source/SDC/pin/STA/test hashes are in `fpga/validation/mem-native-diag-prehardware-2026-11-04.json`.

Reproduce using the same full test runner (optional `--zig` and official `--primitive-lib`), `prepare_guarded.py`, `MEM_BIST_GUARDED=1`, official build Tcl, then `record_build.py --guarded`. This isolated branch writes `fpga/build/mem-native-diag` and `mem-native-diag-input`; it does not overwrite the old worktree/first64 archive. Parent review and root-only SRAM operation remain required. This agent performs no hardware operation.
