# FPGA単独推論：長時間試験の保存点

2026-11-08 21:02 JST時点で、RT-DETRv2-R18 derived300の実機試験はnode8/649、2つ目のConvへ進んでいる。最初のConvとReLUを通過し、同boot/run・error none。全モデルの実機完走・最終数値一致・速度優位は未確認。FPGA内RV32IMCが非MAC演算と量子化等、共通INT8 MACが積和を担当し、P4はSD・搬入・監視・表示のみ。全演算の専用並列回路化ではない。

実機の固定物と停止・復旧手順はホスト `docs/引継ぎ_FPGA単独推論_2026-11-08.md`。FPGAは4E30/FAST0、FS SHA0325998685d3d41badd243829c979881fbb80e04fbb3d11c55affdf8126e49d8、P4 ELFa5f0401b2b3ccf3b5ba62149448eb72dbcf31311e90d567ee0145d37043dcf9f、CPU BIN4cb0d8dc7fd836c02fbd19df9c06f6ecfe647e9b375338d92a060c00060f44a8。14整数実機試験は262971µsで合格。STA未収束を含む実験版で、製品認定ではない。

## 稼働中プロセス

Host worktreeは `D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106`、branch `codex/resume-20261106`、HEAD `80cfc1d0dc1012558edc6844c70b335f896778c6`。verifier runtime PID60776（venv launcher63916）、root exec session31155がCOM4を専有する。boot3406824109/run3/image0。PIDと作成日時は再利用に注意して確認する。

結果は `build/rtdetr-autonomous-device/full-index32-first`、consoleは隣の `full-index32-first-console.log`。一度限りの完了監視を21:02:40 JSTにhiddenで起動済み：launcher62488/runtime57236、ツールSHA df30ce4e85a82741245f59725eb34bbcc7a9ae32b4275a4a08bac9c6ae1a71d4。監視はデバイスに接続せず、元プロセス終了とfinished_utcを待つ。終了後はfreshな `docs/validation/rtdetr-autonomous-host-2026-11-08/physical-full-index32-first` へ証跡・HTMLを保存し、branch/HEAD/indexのguardに合格した場合だけarchiveのみをcommit/pushする。開始情報は `build/rtdetr-autonomous-device/completion-watcher-launch.json`。

停止は既存verifier用STOPファイルで行い、別COM接続・再ARM・書込み・再bindで試験を壊さない。進行中のpassed:falseは終端失敗ではない。完了監視の結果は `full-index32-first-completion-watcher.json` を確認する。作業継続でHEADが変われば自動Git操作は拒否され、保存物を人手で回収する。

## 検証範囲と次回候補

現行P4のJSON tensor APIは負のゼロ符号を失う。将来verifierがJSON再構成一致を返しても、raw1800bit全部の証明としない。raw未検証を完了監視が別に表示する。符号を保持する次回用 `tensor_bits` は、分離host branch `codex/autonomous-raw-tensor-20261108` の `b8c3342` に保存・pushした。300patternの実cJSON/Python往復と専用SDK buildに合格、実機未適用。NN/firmware/UIは変更せず、Linux/MeOS向けFPGA wire変更もない。

現在の試験に混ぜない独立候補はいずれも実RV32 ISAで649演算・1800出力raw bit一致。ただし実機速度ではない。

|候補|index32比のISA実行予算減|判断|
|---|---:|---|
|CRC table|0.727%|初期検証の64→14命令/byte、table読出し増。未適用|
|nearest axis map|0.0865%|メモリアクセス増、実機性能の根拠は弱い。未適用|
|F32 buffer|3.672%|中間double変換除去、callback合計4.453%減。未適用|

証跡は `fpga/validation/npu-autonomous-{crc-table,nearest-map,f32-buffer}-isa-2026-11-08`。各候補はindex32から別々に分岐し、組み合わせていない。FAST_MUL回路は2回のPNR配線失敗を保存し、実機へ投入しなかった。
