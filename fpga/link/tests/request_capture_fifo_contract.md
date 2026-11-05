## Integration update 2026-11-05

The original unit-only record below is preserved. A separate default-OFF LINK
candidate now connects this FIFO with PHYSICAL_FF=1 (explicit DFFC DATA/CLK).
See `docs/GPU_TX_216MHz_FIFO候補_2026-11-05.md` for actual mapped/STA results,
physical ARM versus host soft ARM, required tail guard, and untested hardware scope.

# Request capture FIFO offline candidate

This module is not connected to any existing LINK, board top or constraints.
It has not been synthesized, placed, timed or programmed. Existing commands,
pins and normal demo defaults are unchanged.

## Data path

- Oversample request CLK at216MHz using a three-stage edge detector. Sample
  DATA through two corresponding216MHz stages and enqueue that same byte.
- Only DIR0 with ARM/reset released accepts request bytes. Slow or stopped
  request clocks do not need a source-generated FIFO clock.
- A16-byte FIFO uses registered binary/Gray pointers and two-stage pointer
  synchronization. Storage has no reset; reset pointers/valid make old words
  unreachable. Local session-reset release is synchronized in each domain.
- SYS54 uses registered storage reads and ready/valid. Fetch and consume take
  at least two SYS clocks, giving an ideal steady-state peak27MB/s at54MHz.
  A stalled consumer holds the same valid/data. This is necessary because
  the LINK header-to-batch-start transition cannot safely drop a next byte.
- Source overflow is sticky across DIR changes and synchronizes into SYS.
  Once SYS sees overflow, byte_valid closes; the entire transaction must be
  rejected by the future parser integration. Clearing requires ARM low or
  global reset. A DIR round trip alone deliberately cannot recover overflow.
- DIR/ARM/reset assertion immediately masks valid and resets the private FIFO
  session. Sampling keeps track of already-HIGH CLK while inactive. Startup
  priming prevents that level becoming a fake first byte after reset/rearm.

This is a byte transport, not a protocol parser or a packet-commit mechanism.
Already-delivered prefix bytes can exist before overflow crosses to SYS. A
future integration must reject such partial transactions and preserve CRC,
framing, cancellation and timeout handling. Existing LINK modules are untouched.

## Offline unit results

The test uses legal1290-byte legacy TRI_BATCH64 packets with header/trailer
CRC. DATA is stable from a falling transmitted CLK to the next falling CLK.
At20MHz,32 SYS/216 phase points span all four relatedPLL edge classes plus
eight fractional offsets per class. The long stream also walks its phase
relative to216MHz. Two digital CLK-delay models,0ns and10ns, are exercised.

All64 combinations passed five complete packets each:320 packets and412,800
exact bytes. Each test also covers consumer backpressure, header transition
pause, partial-request DIR/ARM/reset interruption, inactive reply clocks,
stopped-HIGH CLK rearm, FIFO overflow, sticky fault and explicit recovery.

```powershell
python fpga/link/tests/run_request_capture_fifo.py --tools D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin --phases 32
```

The0/10ns delays and finite phase grid are simulation assumptions. They are
not measured cable skew, continuous-phase coverage, metastability/MTBF or
electrical qualification. The current54MHz request pipeline was observed
elsewhere to map DATA registers into RAM16S4; no mapped-cell assumption is
made here. Before any integration, inspect/explicitly constrain actual sampling
cells, prove FIFO CDC/storage timing and satisfy the216MHz clock constraints.
Prioritize the smaller explicit-DFF fix before considering this FIFO on hardware.
