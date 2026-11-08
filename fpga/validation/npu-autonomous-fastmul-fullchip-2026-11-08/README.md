# FAST_MUL full-chip candidate

Initial full-chip PNR with place0/route0 FAILED DesRoute/PR0004, despite fitting resource counts. No deployable bitstream was produced. Logic18018/20736, CLS9652/10368, BSRAM46/46, DSP14.5/24; no claim that a particular resource caused routing failure. Source snapshot is preserved in ignored root build/full-v3-fastmul; source identity is recorded by the full-core RTL gate.

Independent actual RV32/cache/8OC MAC/CPU-sequenced MatMul/CDC/DDR adapter RTL gate with FAST_MUL=1 PASSED14 integer outputs,37 packets and token/BUSY/abort/no-stale guards. Only DDR PHY is a double. This is a tiny test, not physical fullNN.
