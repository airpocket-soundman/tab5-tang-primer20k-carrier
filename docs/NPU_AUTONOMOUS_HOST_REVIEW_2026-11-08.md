# FPGA内Transformer実行：ホスト要求照合（2026-11-08）

この文書は、新しい自律実行方式を実装する前の読み取り照合記録である。新しいwire opcode/capability、ピン、電源、周波数はここでは確定しない。現行4E24や実機を書き換えていない。

## 参照版と実装

|ホスト|参照HEAD|確認した要求・実装|自律NPUへの対応|
|---|---|---|---|
|Linux|`cfc9a6ecf7daa4c5e3decbe3885b22c2bd2f4cd1`|README、DEVELOPMENT_GOALS、Device Tree、portable LINK/MEMV1 session、GPIO backend、DMA方針|NPU4E24/自律NPU driverは未実装。DTにはFPGA/PARLIOデバイス定義なし。portable LINK/MEMV1のPC試験と実機NPU対応を混同しない|
|MeOS|`78274b4625e889f13360a024988cb01c1b9351b6`|README、FPGA_CARRIER_REQUIREMENTS、fpga_npu_app、drivers/fpga、device ioctl|NPUはCPU算術参照のみ。`--dock ... npu`は明示blocked。自律NPUのwire/loader/sessionは未実装|
|外部メモリ研究|`e84b59e8bf462ab1e2023f9e28f7915c152cbbdb`|README、Project_A_P4_Linux_FPGA_Virtual_MMU|計画書のみ。Linux本体の調査の代替にしていない|
|ESP-IDF|`d5eca7065448b0381f0652a5b80d591595ca5299`|README、Project_B、Wholebody計画、graph/backend/device service、通信/表示|RT-DETR全649演算をP4/FPGA分担で実行。自律NPU loader/RUNは未実装|

LinuxとMeOSの参照作業木には未コミットの別作業がある。HEADだけではその内容を同定できないため、読んだ各ファイルのSHA256を[host-references.json](../fpga/validation/npu-autonomous-host-review-2026-11-08/host-references.json)へ記録した。他ホストの作業木は変更していない。参照リポジトリの旧配置を読み取りに用いたが、新規ソースは所有者に対応するcarrier作業木のみに置く。

## 適合方針と未確定事項

- FPGA内のRV32IMC制御プロセッサ、共通INT8 Conv/MatMul、DDRを組み合わせる実験を行う。Tab5/P4はモデル・画像の搬入、操作、結果表示に限定する。FPGA内ソフトコアによる演算は、各演算の専用並列回路化や高速化の証拠ではない。
- RQG2、モデル/画像同一性、DDRの明示的なアドレス/長さ/所有権を保つ。FPGA DDRはLinuxメインRAMへ透過的に増設されない。
- wire契約は全OS共通にする。既存4E24 opcode/descriptorの意味を変更せず、自律実行の能力を明示的に問い合わせられる新契約が必要。現段階の内部MMIOをwire ABIと見なさない。
- 自律RUN中はホストのpayload書込み、別の演算、DDR masterの同時利用を禁止する。status/abort等の制御と、完了/エラー/部分結果非公開、epoch/token、quarantineからの復帰を別途規定する。
- 制御プロセッサのcode/metadata/stack/mailboxと、モデル定数/活性値/accelerator scratchの非重複を検査する。新領域の案は128MiB範囲内でも、合成・実機・DDR所有権の確認なしに利用可能と断定しない。
- Linux/MeOS向けの能力検出・アップロード・RUN/abort/result処理は今後の各ホスト実装となる。共通仕様に対応できる設計であっても、全ホスト実機適合済みとは呼ばない。

## 現行数値記録との関係

現行RT-DETRは全649演算/57Conv/65MatMul-Gemmの実機実行完了を確認したが、事前の厳密数値比較はFAILである。自律実行へ移しても、この失敗を取り消さない。RV32ソフト浮動小数点、native FMA参照、P4/libm参照、実FPGA整数結果は別の数値条件として固定して比較する。instruction-set emulatorの成功は実FPGA上の実行や性能の証拠ではない。

## 先行検証環境

[公式rv32emu](https://github.com/sysprog21/rv32emu)のMITライセンス付きソースをcommit `ffb041bab9d1513e5329f25f486378778dceed13`へ固定した。WSL Ubuntu24.04のgcc/makeで、SDL/F/JITなしの最小ライブラリをビルド。RV32IMCの実ELFとソフト浮動小数点を実行するためのISA試験に利用する。独自MMIO整数oracleを用いる試験と、実RTL/実DDR/実機の試験は区別する。
