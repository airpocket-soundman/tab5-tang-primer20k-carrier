# FAST_MUL full-chip candidate

Initial full-chip PNR with place0/route0 FAILED DesRoute/PR0004, despite fitting resource counts. No deployable bitstream was produced. Logic18018/20736, CLS9652/10368, BSRAM46/46, DSP14.5/24; no claim that a particular resource caused routing failure. Source snapshot is preserved in ignored root build/full-v3-fastmul; source identity is recorded by the full-core RTL gate.

Independent actual RV32/cache/8OC MAC/CPU-sequenced MatMul/CDC/DDR adapter RTL gate with FAST_MUL=1 PASSED14 integer outputs,37 packets and token/BUSY/abort/no-stale guards. Only DDR PHY is a double. This is a tiny test, not physical fullNN.

PNR-only retry with place1 (official routability priority) / route0 also FAILED DesRoute/PR0004. The copied project used the exact same synthesized netlist SHA256 `a1da23459ab3b87004515c7486752fc232189d9e1b2404f33347e15c1aab05fe` before and after execution. Logic18018, FF8461, CLS9663, BSRAM46/46 and DSP14.5/24. See `failed-place1` for console, reports, commands, official command references and provenance. Failed v3 remains intact. No further PNR attempts were made.

FAST_MUL is currently **not deployable**: component and RTL tests passed, but neither routing attempt produced a qualified bitstream. The dock top explicitly selects CPU_FAST_MUL=0 again; optional parameters and tests remain available. Full-model physical validation uses the existing FAST0 FS identified by root as 032599, not this failed candidate. No board operation was performed by the offline retry task.

PNR-only retry with place1 (official routability priority) / route0 also FAILED DesRoute/PR0004. The copied project used the exact same synthesized netlist SHA256 `a1da23459ab3b87004515c7486752fc232189d9e1b2404f33347e15c1aab05fe` before and after execution. Logic18018, FF8461, CLS9663, BSRAM46/46 and DSP14.5/24. See `failed-place1` for console, reports, commands, official references and provenance. Failed v3 remains intact. No further PNR attempts were made.

FAST_MUL is currently **not deployable**: component and RTL tests passed, but neither routing attempt produced a qualified bitstream. The dock top explicitly selects CPU_FAST_MUL=0 again; optional parameters and tests remain available. Full-model physical validation uses the existing FAST0 FS identified by root as 032599, not this failed candidate. No board operation was performed by the offline retry task.
