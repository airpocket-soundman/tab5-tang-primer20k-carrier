# 整形BATCH: 限定CDC適合とrouting閉塞

2026-11-04。独立worktree `tab5-tang-primer20k-carrier-filtered-batch-hold`、base `43137e7`。FPGA source9eb8の機能を保ち、root承認のmetadata非同期first-stage30組だけを除外した候補。rootによるpeer reviewと実機試験は別ゲートであり、本記録は実機適合ではない。

## 変更と解釈

serializerのoffer入力だけを`LUT1 INIT=2'h2`の恒等式へ接続した。元のfast_offerによる即時OE/READY遮断、SYS lifecycle、metadata保持は変更しない。`audit_offer_identity.py`は、この恒等式を取り除けばbase sourceと完全一致することと、真理値表0→0/1→1を検査する。

実際のGowin mapped VOでは独立LUT1は吸収された。従って「物理bufferが遅延を増やした」とは主張しない。これは**identity-equivalent source / routing-closed candidate**である。通常STAの実経路が全て閉じたことを根拠にする。完全netlist形式検証ではなく、source恒等性、公開mapped構造、独立CPU oracle、CRC/制御回帰の組合せによる検証である。

既存のmetadata hold31/30本の失敗、限定CDC後のfast_offer hold−0.021ns失敗は元worktreeへ保存済み。後で開始したsyn_keep専用buildも別出力へ保存し、本candidateと混同しない。

## 内部適合ゲート

- exact30のsource-Q→metadata_meta/DだけをCDC exceptionとする。source SHA、mapped FF数、各stage0 Qの唯一fanout=同bit metadata_bus/Dを再検査。
- metadata stage0→stage1はsetup/hold各30/30本を全数報告。最小setup+16.777ns、hold+0.539ns。
- actual core54、conditioned54、sampler216を通常STA。aggregate setup0/hold0。全体最小setup+1.155、hold+0.126、recovery+2.615、removal+1.106ns。sampler meta→sampledも例外なし。
- control41とCDC assertions（prefix361、stage1整合41646edges）、BATCH48、polygon10334transactions/7draw、fractal991transactions/24576color+depth pixelsの12legacy/vivid viewportを再実行して合格。
- controlには停止CLKでのDIR/ARM/reset/timeout、shortpulse、RAM write/read ownership、反復plane/seqを含む。CRC破損BATCHはatomic no-execute。

FS SHA256 `85bac22420a81bbaaef26a2edff81a3deb0e2bb114a97f106c1deede8062d717`。source、FS、STA、SDF、VO、試験ログと全SHAは生成manifestを正とする。build Tcl `fpga/builds/dock/build_filtered_batch_cdc_qualified.tcl` はbuild前にsource SHAと生成制約を再照合する。

これは「例外なし」の設計ではない。2FF resolving、source保持、8byte prefixとindex2 consumerの整合性を明記した限定CDC例外がある。metastability MTBF、pad往復、ケーブル上限、任意高周波性能は保証しない。旧6c5aの実機結果をこの新しいFSの成功へ転記しない。
