# GFX frame timing v1

The optional `FRAME_TIMING_ENABLE` parameter defaults to0. Existing
FRACTAL_INFO values and the per-tile CYCLES_LO/HI commands are unchanged.
This extension changes control traffic, not the fractal calculation.

| Opcode | Zero-argument success |
|---|---|
| 79 FRAME_TIMING_CAPS | 0120: version1,32-bit sum |
| 7a FRAME_TIMING_RESET | 0000: enable timing, reset total and overflow |
| 7b FRAME_TIMING_LO | low16 bits |
| 7c FRAME_TIMING_HI | high16 bits |

With the feature disabled, all four commands returnstatus2. With it enabled,
nonzero arguments returnstatus3 before checking initialization. Reads before
RESET or after overflow returnstatus5. Reset/abort invalidate the counter.
RESET alone makes a zero total readable; a complete tile is not required.

Each successful final FRACTAL_WRITE for pixel1023 adds precisely
`fractal_cycles+1`, the same value stored in existing `last_fractal_cycles`.
Only completed fractal tiles contribute; clears, drawing other primitives,
readback, LINK traffic and incomplete/cancelled tiles do not contribute.
The33-bit addition detects carry and latches overflow until RESET.

The host must explicitly negotiate CAPS, RESET before each frame, finish all
tile DRAWs and then read LO/HI without issuing another DRAW between the two
reads. The API does not add a separate LO-triggered snapshot latch. A failed
frame must not use a partial sum as a complete render measurement.

For640x360 there are240 tiles. RESET+LO+HI replaces480 per-tile timing queries
with3 per-frame commands, excluding the once-per-ARM capability negotiation.
The timing scope remains the sum of the original tile computation intervals;
this is not communication-inclusive device time and is not a measured speedup.

## Offline verification

`run_frame_timing.py` checks the native response validator and portable/vendor
RAM wrappers. Both passed115 commands covering exact old per-tile sum equality,
independent RESET frames, zero count, disabled feature, invalid arguments,
overflow, abort and reset. Overflow testing injects a near-2^32 total before a
real completed DRAW to exercise the carry path; it is not billions of elapsed
simulation cycles. Existing default0 fractal regressions also passed in both
wrappers:991 transactions,24576 color/depth pixels and stable DRAW cycles each.

No hardware qualification is implied by these offline tests.
