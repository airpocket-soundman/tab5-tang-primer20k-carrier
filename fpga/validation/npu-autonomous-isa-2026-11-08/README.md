# FPGA-local RV32 full-model ISA evidence

CURRENT SELECTED PROFILE: v7 (fixed startup/BSS, CPU sequences Matrix using400368hardwareTile requests). BSS352bytes are prefilled0xA5 afterELFloader's initialzero, beforeexecution. Fullv6 andv7 bothcomplete649/57/65 and all1800outputbits match the historical v5 `9a4e...` output exactly. v7 has zero MMIO MatrixCMD2 requests;13067logicalMatrix scheduling jobs remain in firmware. This is actualRV32 softfloat plushostINT64MAC oracle, NOTphysicalFPGA full-model execution. Seev7-checkpoint.json andexactfirmware ELF/BIN.

Firmware BIN must be fullyuploaded/readbackverified beforeEACH RUN. CLEARaloneisNOTwarmrestart becausemutable.data isnot restored bystartup. Originalnative/P4strictnumericFAIL remainsseparate. Theoutputgolden wasfixedbeforephysicalNNoutput, notchosenafterseeinghardware.

## Historical v5 proof and limitations

# Actual RV32 firmware ISA proof, not physical FPGA qualification

HISTORICAL: old v5 linker BSS bounds were later found unsafe; zeroed emulator memory hid it. Do not deploy v5 from this proof. Separate v6/v7 dirty-BSS results supersede deployment eligibility.

Full v5 firmware completed649 nodes/57Conv/65MatMul-Gemm in the pinned RV32IMC soft-float interpreter. All non-MAC, quant/dequant, RGB preprocessing and program control executed guest RV32 instructions. Only integer accelerator MMIO is a host INT64 oracle. No F extension or JIT. No hardware accessed.

`full-v5/output.f32` is the 7200B pre-physical golden for the same immutable v5 ELF, SHA256 `9a4e9b9319e2b2592c9c10d2134c97b71226f0bf32e3b4774dfeb71feca6f715`. Existing native/P4 indexed comparisons remain FAIL; see numerical-comparison.json for separate post-result geometry diagnostics, not AP. The448 host seconds in logs are not a physical runtime prediction. Step budgets are approximate, not exact retired counts.

`negative-payload-crc-v5` is an expected rejection: state5/error5, zeroMAC and output_count0. Its execution_completed=false is preserved. Corrupt input can be reproduced by copying the pinned package and XOR its last byte with1. Large model/image inputs are identified in provenance instead of duplicated here.

`firmware-v5` preserves the exact ELF/BIN and build records. Source copies for the runner and ABI, official upstream license/config and the explicit test-only patch are included. Original full run runner executable was not prehashed separately; the executable snapshot is from the same-source wrapper smoke rebuild after completion, as explicitly recorded in provenance. No physical output was used to select the golden.
