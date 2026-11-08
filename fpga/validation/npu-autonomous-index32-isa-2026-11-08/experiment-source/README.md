# Bounded index32 experiment (not deployed)

The canonical FPGA-local firmware, pinned host source and RTL are untouched. This experiment changes ONLY unsigned integer address/index/coordinate hot-loop arithmetic in a generated graph.cpp. It does not reduce FLOAT/DOUBLE precision, change signedINT64 tensor data/Node attributes, use a different model, or replace hardware MAC with software. GridSample andTopK headers are unchanged. Model.load is copied byte-for-byte with its original64bit CRC/range/binding validation.

This is a model-specific experiment for the current RQG2 RT-DETRv2-R18 derived300 metadata (nt952/nn649/metadataCRC763848396/sourceSHAa4e1d5c...). Preflight additionally bounds graphDDR to80MiB, all tensorcounts below2^25, dimension products, physical tensor and packedweight/scales extents. Type100's UINT64_MAX opaque offset remains64bit and never becomes a physical32bit address. Resize's cross-product, Slice endpoints, transpose/broadcast shapes, pooling coordinates and reduction layouts are checked before narrowed loops run. This is not arbitraryONNX/shape support or cryptographic authentication byCRC.

## Reproduce

`python prepare.py` writes generated/rtdetr_graph.cpp plus provenance. `python verify_native.py` compiles canonical and generated graph with the same FFPOFF compiler flags, real full649-node service and existing generic integer hard-MAC double. It checks all1800 outputfloat bits against each other and the prior nativeOFF reference. Source package/input stay in the host build workspace; no weights/images are copied into this experiment.

Native full-service gate PASS:649nodes/57Conv+65MatMulGemm, all1800bits equal to canonicalOFF SHA b539d25d1c013808bb15844ed505a1fa48a81d7d49c479e7472e13317f3064fb. Eight UBSan preflight negative cases also pass. An initial overly broad offset guard rejected the valid type100 opaque sentinel; that was corrected to retain its64bit semantics before this passing run. The initial failed run remains under ignored build/native, not relabeled asPASS.

`python build_rv32.py` uses the canonical builder/flags/startup/transport/backend, replacing only graph.cpp and adding this guard-header path. It writes the experimental image under build/rv32. ISA profiling/numerical comparison belongs to the separate rv32emu audit; do not infer speed from narrower types or native wall time. The correct RV32 comparison target is the canonical RV32 firmware output (9a4e... as recorded by audit), NOT nativeOFF b539...: platform libm already differs. All instruction count/runtime/FPGA speed claims remain UNMEASURED here.

`contract_check.cpp` can be built with the same generated graph and UBSan to rerun bounds rejection. Small raw native outputs/commands/metrics/contract andRV32-build provenance are frozen under validation/native. The actual firmware ELF/BIN and native executables remain ignored build artifacts. Nothing is automatically promoted to canonical firmware or uploaded to a board.
