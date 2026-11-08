# Isolated generic nearest Resize axis-map experiment

Not deployed or promoted. Based ONLY on frozen index32, not combined with CRC-table. Canonical firmware/graph, index32 source/ELF/BIN, CRC candidate, host and RTL remain unchanged; builder records baseline SHA identities and asserts unchanged.

Nearest Resize retains the exact integer floor/clamp expression and input strides. Bounded maps store each axis contribution once; an odometer traverses the same linear output order. The existing index32 contract executes first and guards tensor counts/cross products; eligibility requires equal nonzero ranks<=8 and total output axis lengths<=4096, otherwise original generic Resize remains unchanged. All original x.get(float→double) and put(double→float),128-element chunks,cancellation/read/write order remain intact. No memcpy/no interpolation/no reordered FP math. Input/output overlap follows the original element order.

Native full649nodes,57Conv/65MatMul hardMAC test double matches frozen index32 all1800bits exactly SHA b539d25d1c013808bb15844ed505a1fa48a81d7d49c479e7472e13317f3064fb. Actual generated helper tests six shapes (identity,nonintegral up/down,1D,8D,4096axis bound),NaN payload/signed zero,128chunk cancellation,output guards and four fallback eligibility cases against independent64bit quotient oracle. These are offline tests, not actual RV32 fullNN or physical proof.

RV32 build/BSS guard passes. Disassembly shows helper stack frame17616B (map16384B +values1024B+metadata/saved registers); caller run_graph frame10272B, firmware_main272B: combined28160B before deeper calls. No recursion/new heap allocation introduced; existing stack top0x07fe0000 and heap end0x07000000 are unchanged. This static frame accounting is not a full dynamic stack high-water proof; independent fullRV32 ISA must check minimumSP/canaries before promotion. Map length checks prevent allocating input-dependent unbounded stack.

Metadata node0 is1×3×640×640→same shape, F32nonoverlap offsets4915200→0. Resize nodes123/147 upsample20→40 and40→80 across256channels. `first12-nodes.json` records early graph inventory (Resize,Slice×3,Concat,Mul,Conv,Relu,Conv,Relu,Conv,Relu). Optimization is generic, not model/image-specific.

Run `python verify_axes.py`, `python verify_native.py`, `python build_rv32.py`. `validation/` snapshots numerical gates/source/disassembly; ignored build/ contains candidate ELF/BIN. No speed claim before measurement; source peroutput index DIV/REM/MUL removed, actual hardware/caching performance still to be established.
