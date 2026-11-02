# Dock GFX診断の検証記録

## 全機能の試験準備（2026-10-28）

[全機能テスト計画](../../docs/全機能テスト計画.md)に24項目の準備段階、依存条件、合格条件を整理した。[今回の統合レポート](all-features-2026-10-28.json)では、PC試験33件、WindowsネイティブのRTL試験8系統、要素合成6種、Dock LINK/GFXビルド2種が通過。Cコーデックには既存Zigを明示した。新しい試験管理・ビルド・セットアップの単体試験は別途25件（Dockビルド4、ツール18、要素ビルド3）通過した。

NPUのMAC／requant／dotとGFXのcoverage／depth／fragmentは、I/O padを除くGW2A向け要素合成を行った。資源は合成プリミティブ数であり、実デバイスへの収容、配置配線、タイミング、ビットストリーム生成は示さない。特に三角形部品の大きな乗算器数は統合前に資源確認・最適化が必要。NPUのホストコマンド・統合トップは未実装で、MeOSから呼べるNPU版`.fs`はまだない。

全体の準備段階は9項目が部分実装、15項目が計画段階。実機チェックはすべて未実施として残しており、PC試験の通過を全機能完成として扱わない。`python fpga/tools/test_features.py --rtl --synth --build --cc <Cコンパイラ実体>`で再実行し、ハッシュとログを更新する。

## Dock GFXの個別検証

2026-10-28。最新の成果物・ソースSHA-256とツールログの参照先は[dock-oss-build-2026-10-28.json](dock-oss-build-2026-10-28.json)。
OSS合成と再ARM復帰を追加する前の初回記録は[dock-gfx-2026-10-28.json](dock-gfx-2026-10-28.json)として保持する。現在のファイルやバイナリとハッシュが一致するとは限らない。
両リポジトリの`codex/dock-jumper-gfx`作業ツリーを検証し、未コミットの内容は記録内のハッシュで識別する。

| 確認 | 結果 |
|---|---|
| Icarus RTL | 全8スイート成功：LINK、Dock GFX、coverage、depth、fragment、MAC、requant、dot |
| Dockピン経由GFX | oracleと1,572トランザクション一致、非対称画像の1,024画素一致、CRC／範囲／未初期化／timeout／disarm／resetを確認 |
| PC単体試験 | GFX17、NPU9、host4件を確認。hostのGCC codec試験はWSLで成功、Windowsではコンパイラ未検出でskip。OSSランナー4件も成功 |
| 既存ESP-IDFホストC codec | WSL GCCで793ベクタ成功 |
| ESP-IDF診断ファーム | IDF5.5.2、BSP1.3.2、ESP LVGL port2.6.2、LVGL9.2.2で成功。Dockプロファイル無効／有効の両構成 |
| 共通codec同期 | ESP-IDF snapshotとキャリア正本のSHA-256一致 |
| OSS合成／配置配線／pack | LINK・GFXとも成功、`.fs`生成。内部27MHz条件を通過。Gowin EDAは未実行 |
| 配置ピン照合 | 両版22ポートのball・BEL・IO属性がCSTと一致。余分なI/Oなし |
| 再ARMの復帰待ち | 実際のCヘルパーをWSL GCCで試験。150ms idle、READY低待ち最大100ms、stuck HIGH時の解除を確認。Tab5両構成を再ビルド成功 |
| 合成ネットリストの動作シミュレーション | 同梱SPX9は空blackbox、IOBUFモデルにも方向の問題。事前検出してblockedと記録し、成功扱いしない |
| 実機通信／LCD表示 | 未実施。USB／COMアクセス・書込みなし |

### OSSレポート

| 構成 | LUT4（ツール表示） | DFF | BSRAM | 内部sys_clkの配置配線後推定値 |
|---|---:|---:|---:|---:|
| LINK | 421 | 172 | 0 | 189.54MHz（27MHz条件PASS） |
| GFX | 773 | 280 | 1 | 166.25MHz（27MHz条件PASS） |

使用ツールはYoWASP Yosys 0.70、nextpnr-himbaechel Gowin 0.11.1、Apicula 0.32。
外部I/O遅延制約を与えておらず、この推定値はバス速度や実機到達クロックではない。
両版の`bus_clk`に専用配線経路を使えなかった警告があり、一般配線で完了。警告は抑止していない。

C7のbank番号はCore回路図のFPGA主図とApiculaがBank6、コネクタ注記がBank4だった。
主図のC7/IOL40BとVCCO6=+1V5を描画して確認し、古い番号注記として文書・CSTコメントを訂正。ball／LVCMOS15／電源は変更していない。
T10はSI/D2のSSPI兼用なので、[Gowin UG290のpin reuse規則](https://www.gowinsemi.com/upload/database_doc/41/document/5b96299fe6aa7.pdf)と[Sipeed公式HDMI設定](https://github.com/sipeed/TangPrimer-20K-example/blob/main/HDMI/impl/project_process_config.json)に照合し、packに`--sspi_as_gpio`を指定した。JTAG／MSPI／RECONFIGのGPIO化は指定していない。

合成後GFXの機能シミュレーションは、限定した試験用SPX9/IOBUF/ALUモデルを明示して1,554トランザクション・1,024画素の照合を通過した。[結果とハッシュ](dock-synth-simulation-2026-10-28.json)、[モデルの範囲・根拠・再実行方法](../simulation/README.md)を参照。ALUはIcarus内部エラーを回避する等価式で、元モデルと全16入力を比較した。ベンダーモデル、配置配線後のタイミング検証、実機動作の代替ではない。

`python gfx/tests/run_synth_bench.py`は同梱モデルの不足を検出して停止する。上記の限定モデルを使用する場合は`--model-overlay simulation/gowin_bench_models.v`を指定する。モデル判定自体は代替モデルの正しさの認証ではない。

Icarus 12.0はWSL上でDebianパッケージを`fpga/build/iverilog/`に展開して使用した。
WSLのシステムパッケージ管理に既存の未完了処理があったため、既存環境の修復やシステムインストールは行っていない。
Windowsの通常PATHにはiverilog/vvpを追加していない。ローカル展開した実体を`--iverilog`／`--vvp`で指定するか、これを自動選択する`test_features.py --rtl`を使用する。
通常のIcarus環境では`fpga/`で`python tools/run_existing_rtl.py --require`を実行する。

WindowsのComponent Manager2.4.4の再試行エラーは、既存SDK環境を変更せず`tab5-fpga-gpu/build/idf-python`へ2.4.5を用意して解消。
LVGL版変更前の生成設定を流用しないよう、診断専用sdkconfigを使用した。依存componentのソースは変更していない。

最新の試験用一式は`fpga/build/dock-bench/`。LINK/GFXの`.fs`、Tab5 app両版、bootloader、partition-table、ログ、pin-audit、manifestを収録する。
Tab5側の元成果物は`D:/github/airpocket-soundman/tab5-fpga-gpu/build/dock-artifacts/`。
`default-unarmed.bin`はプロファイル無効、`dock-profile-enabled.bin`はプロファイル有効。
**両方とも起動時はdisarmed**で、設定有効は電気的な検証済みという意味ではない。
bootloaderは0x2000、partition-tableは0x8000、appは0x10000用。factory app領域4MiB、flash16MiB。
実機書込みは[配線・試験手順](../../docs/Dockジャンパ_GFXテスト手順.md)に沿って別に実施する。

実装中に発見した描画タイムアウトの中断漏れは修正し、途中CLEARからの復帰をRTLで確認した。
制約Tcl／SDCの構文と参照ファイル存在、CSTの22ポート・ballの重複なしをPCで確認したが、Gowin EDAでの制約受理の代替にはならない。
