# DDR MatMulタイルシーケンサ単体検証（2026-11-07）

`npu_ddr_matmul_sequencer.v` は、DDR常駐INT8行列の1バッチから既存8OC tile loader用descriptorを生成する独立制御部である。既存4E22/4E23、top、通信コマンド、ピンは変更していない。ホストが各タイルを送る方式から、FPGA内の行列単位実行へ移すための[基盤](NPU_常駐重みと連続推論計画_2026-11-07.md)であり、現在の実機bitstreamには未接続である。

## 入出力と配置契約

入力jobは32bitのM/K/N、A/B/C baseとchannel pitch、job_valid/job_ready。M/K/Nは1..65,535に限定し、幅を切り詰める前に検査する。1jobは1batch。AはK×align16(M)のINT8 feature-major、BはN×align16(K)のINT8 OI配置、CはN×align16(M)のINT32である。AのM末尾からalign16(M)までは呼出側が0で初期化し、Cの同じ末尾をシーケンサが所有する。BのK末尾は読まないが、pitch全体を予約する。

baseとpitchは16B整列。A pitch≥align16(M)、B pitch≥align16(K)、C pitch≥4×align16(M)。各領域は保守的にpitch×channel数の全体を予約し、128MiBの範囲内・加算/乗算overflowなし・A/B/C相互非重複を要求する。予約した最後のchannelのpitch末尾も範囲検査へ含める。重複書込みやRMWを許すAPIではない。

Nを8列、Mを256要素、Kを16要素ずつ進め、N→M→Kの順で既存loaderの全descriptorを出力する。cfg_owは常に16、cfg_ohはceil(min(256,remainingM)/16)、kernel/strideは1。input full_w16、full_h ceil(M/16)、origin_y=Mblock/16、row pitch16。A baseはKblock×A pitch、B baseはNblock×B pitch+Kblock、C baseはNblock×C pitch+Mblock×4。C row pitch64、channel pitchはjob指定、tail_owned=1となる。Kの最初/最後をfirst_block/final_blockで示す。

M1でも16幅のpaddingを計算する。Cの数値範囲と末尾所有権は呼出側契約であり、未初期化A paddingを読み込んでよいという意味ではない。INT8全範囲・K≤65,535ならINT32積和の数学的絶対上限は2^31未満だが、接続先loaderの数値エラーも引き続き処理する。

## 制御・失敗時の契約

- descriptor_valid/descriptor_readyで1タイルを受理する。busy/done/error/quarantinedの接続先は、このjobが排他的に所有するloader1個だけとする。
- descriptorとjob入力を受理後に保持し、backpressure中に変更しない。tile_doneが古いままhighなら次を開始せず、timeout対象にする。成功doneは、受理済み・tile_busy=0の後だけ数える。
- 最終ICタイルはtile_result_validも必要。全accepted/completed/expectedが一致した時だけ、行列result_validとout_validを発行する。out_validはout_readyまで保持し、成功result_validは次job・clear・abort・校正喪失まで保持する。
- 部分結果は先行してCへ書かれている場合がある。error/abort時はC全体を無効とし、既存prefixを成功結果として公開しない。
- abort、memory_ready喪失、loader error/quarantine、待ちtimeoutはtile_abortを発行する。in-flightタイルはtile_busyが下がるまでDRAIN_TIMEOUT以内で待つ。下がらなければquarantineをラッチして再利用を禁止する。
- errorはout_readyだけでは解除しない。clearはbusy/outstanding/loader busy/error/done/quarantineがなく、sequencer自身も非quarantineの時だけ有効。tile_abortは失敗後保持するため、実loader接続時のエラー回復には両者の協調reset/clear制御が必要である。単体のclearだけで故障loaderや部分積和を安全に再利用できるとは扱わない。
- quarantine解除は協調resetだけ。実DDR adapter/arbiterを巻き込んだ処理はdrain/quarantine規約に従い、SYS/USER toggleを片側だけresetして再送しない。今回の単体にはsession tokenやUSER CDCはなく、上位がmemory_ready/abortと排他所有権を保証する。

| error code | 意味 |
|---|---|
| 1 | M/K/N範囲不正 |
| 2 | 整列・pitch・128MiB範囲・総tile数overflow不正 |
| 3 | A/B/C予約領域の重複 |
| 4 | loader error |
| 5 | abort |
| 6 | descriptor待ちまたは完了timeout |
| 7 | memory_ready喪失 |
| 8 | loader quarantine |
| 9 | 最終result無効、内部count不一致 |

## 検証と資源

[原本・検証記録](../fpga/validation/npu-ddr-matmul-sequencer-2026-11-07/checkpoint.json)、[SHA256](../fpga/validation/npu-ddr-matmul-sequencer-2026-11-07/SHA256SUMS.json)を保存した。再実行は `python fpga/npu/tests/run_ddr_matmul_sequencer.py`（Icarus/vvp、NumPyが必要）。

M={1,197,256,257}、K={1,16,17,192,768}、N={1,8,9,197,768}の100組と15境界・異常job、計115job/40,001descriptorに合格した。独立Python nested-loop oracleが全descriptorを比較する。hostile fake loaderは受理・完了を可変遅延させ、sticky done、descriptor/output backpressure、8種のerror/abort/校正喪失/timeout、drain失敗quarantine、validation途中のabort/reset後の再試行、公開済み結果の校正喪失による無効化を検査する。

さらに実RTLが出したdescriptorのアドレスを使ってINT8行列を再構成し、独立NumPy INT64 dense MatMulと比較した。1×17×9、197×192×197、256×16×8、257×17×9の計43,179出力とM末尾zeroに一致した。これはアドレスと分割積和の検証で、実Conv kernelやDDR controllerとの統合数値試験ではない。

Gowin V1.9.11.03 Education /GW2A-LV18PG256C8/I7の単体合成はLogic2,381（LUT1,694+ALU687）、FF1,156、DSP0、BSRAM0、合成推定Fmax76.131MHz。範囲/総数計算は共有32サイクルshift-add乗算器を使い、広い組合せ乗算器やBSRAMを増やさない。合成既定100MHz制約自体には未達であり、配置配線・実機・統合STAは未実施。

4E23とFP32 epilogueとの単純加算見積りはLogic16,641/20,736、FF7,554、DSP14.5/24、BSRAM45/46。ただし全chipの配置配線、追加DDR制御、FP32供給、buffer、CDCを含むfitの証明ではない。BRAM残り1個の条件も変わらない。

現DeiTの74 MatMulは122バッチを含むため、この部品をそのまま使うなら122jobとなる。74回のwire commandに減ったとは主張しない。将来のbatch/graph macro、DDR出力epilogue接続、requant、bias/residual、LayerNorm/Softmax/GELU、結果のみの返送は別段階である。全ホストへの能力問合せ・precision/error/session契約をレビューする前に、新ISAや通信コマンドを確定しない。
