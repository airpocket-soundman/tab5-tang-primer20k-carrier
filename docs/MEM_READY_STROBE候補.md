# Strict-ready native strobe candidate

Isolated from frozen08ef3a4/dbcd88/0F25. No change to GPIO, DDR geometry, generated IP logic, burst, data width, patterns, timeouts, independent command/data sent bookkeeping or optional014f deep ABI. Exactly two BIST equations now gate command enable with native command-ready, and write enable/end with native data-ready. Address/data remain eligible pending state until accepted. GPIO-only host3b1deb07 / ELF63ca5301 remains compatible and needs no firmware change.

## Evidence and limits

The prior restricted trial accepted7commands/8data, index7, last command48; coherent deep bank showed command full, no command-read-pointer advances, no write-read-pointer advances and no send_wr high USER cycle. The difference from prior14/15 is not proof of a phase cause. Physical DDR writes/readback remain unproven. Exact raw records are frozen in the deep worktree4ba87d7; no retry performed by this agent.

Official IPUG281-2.6E (https://www.gowinsemi.com/upload/database_doc/2009/document/696a8c052f84e.pdf), PDF19-22, says native command/data transfer is accepted when corresponding ready and enable are asserted. It supports1:4 BL8 one128-bit application data beat; no basis for eight beats/command or burst changes.

prove_ready_entry.py uses ONLY public VO SHA4d37c875..., exact original primitive definitions and truth tables. With eye ownership0, input LUT8'hAC passes rawcmd_en into registered app_en. Command FIFO RAM write enable LUT8'h70 equals app_en AND NOT(full_r AND full_rr), using delayed full stages, rather than a front-end gate on current ready. Data LUT16'hF088 registers wr_data_en AND wr_data_end before its delayed full protection. Under a prescribed ready-low history, old held enables inject6extra registered requests, ready-strobed0. This is an input/delayed-full cone proof, NOT whole-controller FIFO overflow proof or root-cause confirmation; protection may absorb some requests. The zero-drain scheduler cause could persist.

## Independent checks

Old08ef and candidate run side-by-side under64randomized READY schedules:1728accepted events have identical command/address/data/mask/order and accepted bookkeeping. Existing21BIST/122mailbox/39reset-abort/7LINK/621C cases and deep monitor/vendor-init models pass. Every native clock asserts enable implies ready. First-fault valid bits intentionally reflect strobes now (LOW under backpressure); sent flags and counters retain their meaning. Halt test stops USER while a pending request is ready-blocked, then raises READY with USER halted and verifies the SYS watchdog asynchronously suppresses asserted valids without any USER edge. No automatic restart is introduced.

All four routed STA negative lists empty. USER81.196MHz for81MHz, SYS73.060 for27MHz; worst setup+0.030ns, hold+0.234ns, recovery+2.265ns, removal+0.323ns. Setup margin is narrow and this does not prove board/PVT/electrical behavior. Existing90finite vendor exceptions unchanged;123deep +152native held CDC destinations audited, pins unchanged. Same reviewed Linuxcfc9a6e/MeOS26c8082/memory-researche4aa69d/ESP integrated18c763b requirements and unimplemented optional MEM status as MEM_DEEP診断.md. No host command reflection required.

FS SHA256801f478d1a49d13208168374880e042da0246bf90b2e773205b18ced05a2799b; parsed header/footer UserCode0000A40E agree. Manifest fpga/validation/mem-ready-strobe-prehardware-2026-11-04.json; exact gz reports/FS/proofs in mem-ready-strobe-offline-2026-11-04. Hardware trial requires parent review; this candidate is not a proven fix.


## First restricted hardware trial: FAIL, not a fix

Parent programmed801f/A40E with all programmer operations0 and unchanged host3b1d/ELF63ca. Explicit pre-START idle014f snapshot: commandW/R0/0,full0,empty1; writeW/R24/24,full0,empty1; no owners or send_wr. After64-beat attempt: CMD7/DATA8,index7,lastnative48, commandW7/R0,full1,empty0; writeW0/R24,full0,empty0; no command/write read-pointer advances or send_wr cycles; firstfault3 at8100008USERcycles. Both diagnostic captures coherent; software disarmed. Exact raw and programming logs are in fpga/validation/mem-ready-first64-2026-11-04 and full offline archive fpga/build/archived-mem-ready-first64-11d7b04.

Idle evidence rules out an initial queued calibration command in this trial. Strobe gating eliminates the previous extra command-pointer wrap (oldW0 versus strictW7) but does not restore scheduler drain. Eight accepted data beats explain24-to0 modulo32 with unchanged read pointer. None of this proves DDR writes completed or establishes physical capacity.

Unchanged public VO scheduler cone: commandaccept=!commandempty AND(issueW OR issueR) (LUT0E), send_wr_next=pre_info_valid AND issueW (LUT8). FIFOdata-read=send_wr AND NOTwriteempty (LUT4). All39external inputs of the bank-scheduler cells were enumerated; none comes from the write FIFO. Therefore there is no hidden eight-data availability threshold at that scheduler boundary. The first command encodes write000/read001 through valid/decode into FIFO head bits27/28; actual head bits at the stalled hardware are not yet observable. IssueW requires four internal state/timing groups simultaneously; issueR has its own state prerequisites. init_done_r is USER-registered(ddr_init_internal OR eye_calib_start). Existing diagnostic does not expose scheduler state/head/prerequisites, so a new output-only observation revision is proposed, not a further handshake change.
