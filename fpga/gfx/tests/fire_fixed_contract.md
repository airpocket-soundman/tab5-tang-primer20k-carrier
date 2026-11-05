# Fire integer_g0 v1 numerical contract

The legacy floating-point Fire renderer remains a separate renderer. This kernel
defines an integer reference for CPU/FPGA comparison; it does not claim pixel
identity with the floating-point renderer.

- Supported dimensions: 640x360, 320x180, 160x96. Loads0/1/2 use2/4/6 octaves.
- `fire_fixed_valid(width,height,load)` must succeed before a host dispatch.
  The reference returns0 for invalid configurations or out-of-frame pixels.
  The RTL finishes without writes for invalid dimensions/load, and writes0 for
  every out-of-frame pixel in an otherwise valid32x32 tile.
- A draw latches origin, dimensions, frame and load. Input changes and start
  pulses during a busy draw do not replace that draw. Reset or abort cancels
  the draw, suppressing write_enable at the asserted reset/abort edge.
- Coordinate normalization uses the listed floor(Q20 reciprocal) constants in
  `fire_fixed.h`. Noise coordinates are Q8. Smoothstep is
  `floor(f*f*(768-2*f)/65536)`. Negative Q8 coordinate division floors toward
  negative infinity. The four hash corners wrap all hash stages to16 bits.
- Two horizontal integer lerps and one vertical lerp truncate after each stage.
  Octave weights are128,64,32,16,8,4 in Q8. A frame advances the vertical noise
  coordinate upward. Frame uses its low16 bits, giving a65536-frame period.
- Temperature combines vertical rise, horizontal narrowing and turbulence.
  Palette conversion clamps separately to produce red/yellow/white RGB565.
  All shifts, wrap boundaries, constants and operation ordering are normative
  in `fire_fixed.h`; Python and RTL implement the same rules independently.
- FPGA writes every tile pixel in address order0..1023, then pulses done.
  There is no host-generated color image upload in this kernel.

## Offline checks on2026-11-05

`run_fire_tile.py` compiled the C reference using Zig, compared it against an
independent Python reference, then compared the RTL write stream against every
golden pixel using Icarus. Fourteen cases cover11,264 exact pixels, all supported
dimensions/loads, frame wrap, negative noise coordinates, partial/outside tiles,
invalid configuration, abort and busy-start/input isolation. All passed.

```powershell
python fpga/gfx/tests/run_fire_tile.py --iverilog D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/iverilog.exe --vvp D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/vvp.exe --zig D:/GitHub/airpocket-soundman/tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe
```

Gowin1.9.11.03 Education standalone synthesis succeeded: Logic1181
(607 LUT,574 ALU),379 FF,0 BSRAM; DSP primitives are1 MULT9X9,
4 MULT18X18,1 MULTALU36X18,2 PADD18. Synthesis estimates73.145MHz.
These are standalone synthesis results, not integrated placement/routing,
hardware correctness, or application speed measurements.
