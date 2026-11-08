# FPGA-local CPU FAST_MUL component proof

Only CPU_FAST_MUL(default0) was added and forwarded to the pinned official PicoRV32 ENABLE_FAST_MUL parameter. No firmware, graph, model, wire or floating arithmetic changed. Default0 preserves the prior iterative multiplier path. The original official vendor source remains pinned/unmodified.

The official fast and iterative PCPI units match independent Python arbitraryprecision MUL/MULH/MULHSU/MULHU for1348 vectors:81 edgepairs plus256 randompairs, each4operations. Unsupportedfunction7/DIVopcodes are rejected; reset and no duplicate response are checked. FastPCPI responds in2cycles pervector; iterativeaverage60/max68 inthisfixture. These are unit interface latency, not CPUwholeinstruction or inference time.

Actual PicoRV32/cache/MMIO with identical compiled Tile-only smoke firmware passes14 and20 independent INT32 outputs perrun, twoRUNs each, dirtyBSSA5/epoch37->38. The IC17chain includesnonfinalVALID0/partialaccumulator/DDRguards. DDRrequestcounts stay776/1400; fixturecycles55965->50386 and182589->153166. MAC is an explicitly independent INT32 double; no board inference speed claim.

StandaloneGowinEducation1.9.11.03 profileENABLE_MATRIX0/CPU_FAST_MUL1:Logic5455,FF2016,BSRAM1,RAM16=72,DSPprimitive1MULT36X36,synthesisFmax72.547MHz underreporteddefault100MHzconstraint. This is not integratedfit/PNR/STA. MULT36X36primitivecount mustnotbe confused with onephysical18x18DSP unit. Earlier5824component includedmatrixcommandlogic anditerativeMUL, so do not treatthoseas matchedareaA/B.

The synthesis snapshot only changes parameterdefaults to selecttheprofile; canonicaldefaults remain MATRIX1/FAST0. RootintegrationselectsFAST1explicitly andmustmeasurefull-chipresources/timing/boardnumericsbeforedeployment. Fullfirmwarebinary upload/readback remains required beforeeveryRUN; CLEARaloneisnotwarmfull-modelreentry.
