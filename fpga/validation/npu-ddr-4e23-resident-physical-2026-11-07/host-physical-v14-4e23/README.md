# V14 + FPGA4E23 resident cold/warm physical PASS

Parent-run physical trial completed, both images accepted against independent same-P4 CPU INT8 references with all1000 float bits identical. Archive copied only after result.passed=true. No hardware access by archiving agent.

| Measurement | CREW cold | ASTRO warm |
|---|---:|---:|
| Model open (one-time) |137.301128 s| reused unchanged |
| Graph |115.544047 s|115.796370 s|
| Frame total |115.766763 s|116.100937 s|
| Cold total (model+frame) |253.067891 s|not applicable|
| 1000 unequal bits |0|0|

Both runs:12blocks/199ops/74FPGA products/0CPU products/122batches/51468tiles;50static+24dynamic products. Warm kept same cookie and immutable preparation report, completed frame2, no repeated model preparation. This qualifies this two-image idle-gap trial, not indefinite uptime. Non-MatMul/quantization remain on P4; whole-graph FPGA and CPU speed advantage remain unmet. Requested TX10MHz is not measured wire clock. GPIO RX remains unchanged, DMA opt-in.

Host ELF b348bc185e85e34b151045ebaf2d8945543c11934d4abd76e2a5d6506292bd59 (V14 diagnostics); exact bin/sourcezip/flash in ../v14-diagnostics/. Carrier source00fc961, FPGA FS SHA256966770fb8b142c008470b4189a8d625b8b06e4b49dbbb7a3f51cec5834a122c9; carrier fpga/validation/npu-ddr-4e23-2026-11-07/. Previous V13 warm failure is immutable in ../physical-v13/ and not overwritten.
