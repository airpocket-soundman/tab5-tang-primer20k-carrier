# V15 / FPGA4E24 resident physical qualification

Completed cold CREW and warm ASTRO both PASS all1000 float bits against independent same-P4 CPU references. Same resident cookie, one model open,50 staticB bindings retained,24 dynamic products,12 blocks/74 FPGA products/122 batches/199 operations. Per frame3929 host panel jobs represent51468 derived sequencer tiles. Cycle counters are explicitly unsampled; zero means unavailable.

| Measurement | Cold CREW | Warm ASTRO |
|---|---:|---:|
| Model open |138.133369s|reused|
| Graph |108.445019s|108.673595s|
| Frame |108.667357s|108.979505s|
| Model+frame |246.800726s|not applicable|
| Wire bytes |33,719,450|33,719,450|
| Panel jobs / derived tiles |3929 /51468|3929 /51468|

CPU ASTRO graph62.481998s/total73.224470s remains faster. TX requested10MHz positive-phase persistentDMA, CPU RX; requested frequency is not measured clock. Existing DDR5208-check and matrix1904-check selftests passed. Cold and warm acceptance checks every raw float bit, not only top5. The matrix selftest checks1872 INT32 values including M padding and32 surrounding guard bytes.

The parent will restore FPGA4E23 and flash the separate all25-class YOLO demo. This archive therefore records a qualified historical4E24 candidate, not current device identity. Existing4E23/V14 proof is untouched. No hardware was accessed to produce this archive.

Actual V15 ELF0f69c3c7ab78a7a7b2f75424bd126b3ba9782201d63c316da88c84fba9726e7c is identified by boot-info.json and trial.info; preflight.json intentionally records the previous pre-flash firmware. v15-firmware includes binary/source ZIP/flash/image/boot logs. Carrier source reference ba7e15e and exact vendorFS SHA3d3d2e20211be5d48c8fb3f9c0b0311f2641ee08817ad46d598a8da98129bd69 are in provenance; vendorFS is referenced without duplication. Raw terminal result/log/CPU+cold+warm tensors and LCD screenshots are preserved verbatim. No model weights or fullSDK copied.

YOLO all25 and RTDETR weight-pack progress are separate offline proofs. This physical Transformer run still executes nonlinear operators and INT32-to-FP32 dequantization on P4. It does not include FPGA FP32 epilogue or autonomous whole-model execution.
