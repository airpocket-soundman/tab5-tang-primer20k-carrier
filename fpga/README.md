# FPGAソース

2026-11-04：実機なしで進める[汎用SIMD演算器の試作](gfx/compute/README.md)を追加。
Juliaと配列演算を同じRTLへロードする命令列で実行する。既存LINK/GFX・DDR3・GPU LABには未統合。
試験・部品合成とホスト要求の照合は[開発記録](../docs/汎用GPU演算器_オフライン開発_2026-11-04.md)を参照。

Tang Primer 20K Core（GW2A-LV18PG256C8/I7）上のFPGAデバイスのソースと制約を管理する。役割分担は[リポジトリ分担と参照ルール](../docs/リポジトリ分担と参照ルール.md)、機能とビットストリームの構成は[FPGAデバイス構成](../docs/FPGAデバイス構成_ビットストリームと機能.md)。

状態（2026-10-28）：tab5-fpga-gpuからRTLと試験を移管済み（[移管記録](MIGRATION.md)）。Dock LINK/GFXはOSSツールで合成・配置配線・packを完了し、`.fs`を生成。内部27MHzの条件を通過し、GFXの画像RAMはBSRAM 1個。RTL全8スイートと、限定試験モデルによる合成後GFXの1,554通信・1,024画素照合が成功。Gowin EDA、外部I/Oタイミング・実機は未検証。[検証記録](validation/README.md)。

公式DockのUSB書込み環境は[セットアップと開発コマンド](../docs/Dock_USB開発環境.md)を参照。`python fpga/tools/dock_dev.py setup`でローカルツールを用意し、ビルド・識別・SRAM転送まで実行できる。

ジャンパ接続の開発入口は[Dockジャンパ／Tab5内蔵LCD試験](../docs/Dockジャンパ_GFXテスト手順.md)。32×32 RGB565の矩形・点描画を全画素読み戻して比較する。[診断用プロトコル](link/DOCK_GFX_V0.md)は将来のDDR3 v1とは別。

Tab5側のドライバ・描画ソフトを実装する場合は[ホストソフト開発ガイド](../docs/Tab5ホストソフト開発ガイド.md)を参照。ESP-IDF／MeOS／Linuxの担当範囲、初期化、転送、復帰、LCDへの受渡しと参照版の記録方法をまとめている。

2026-11-03追記：Dock用LINK v0 topのシミュレーション・合成・配置配線と実機SRAM書き込みを完了。
ユーザーがLED点滅を目視確認。Tab5との実通信、ピン電圧・Hi-Z、DDR3は未検証。
[初回書き込み記録・再現手順](../docs/Dock初回書き込み_2026-11-03.md)を参照。

三角形描画の次段階として、[32×32色・深度タイル診断](../docs/Dock三角形タイル試験.md)を追加。
`build_oss.py triangle`で専用GFXイメージを作る。整数CPU参照との全画素照合を先に行い、速度向上は別途測定する。

## 構成（予定）

企画全体を試験する入口は[全機能テスト計画](../docs/全機能テスト計画.md)。`python fpga/tools/test_features.py --rtl --synth --build`で利用可能なPC試験を実行し、未実装・実機未確認も含む機能別レポートを生成する。

| ディレクトリ | 内容 | 状態 |
|---|---|---|
| `constraints/carrier/` | キャリア用.cst/.sdc。`kicad/core_pin_assignment.csv`から生成して一致を検査 | 未作成 |
| `constraints/dock/` | 公式Dockジャンパ試験用.cst | [tab5_dock_link_v0.cst](constraints/dock/tab5_dock_link_v0.cst)（案） |
| `platform/` | 基板別top、クロック・リセット、ARM、DDR3コントローラ設定 | DockのLINK/GFX topあり。DDR3未作成 |
| `link/` | リンク物理層（DIR/READY/OE）、v0/v1プロトコル、CRC | v0 RTL・試験を移管済み |
| `gfx/` | 2D命令、三角形ラスタライズ、Zバッファ、計算描画 | 32×32三角形/Z・Q4.12 Mandelbrot/Julia・完全タイル読出し。Tab5実機検証済み。HDMI/DDR3は未実装 |
| `hdmi/` | DVI/HDMIスキャンアウト（GFXのオプション） | 未作成。参考：`docs/reference/tang-primer-20k/official-hdmi/` |
| `npu/` | INT8 MAC、requant、dot job、構成A/B/C | MAC lane、requant、dot jobのRTL・試験を移管済み |
| `reference/` | RTL期待値用の参照モデル（Python） | 移管済み |
| `tools/` | 既存シミュレータがある場合だけRTL試験を実行 | `run_existing_rtl.py`を移管済み |
| `mem/` | ブロック格納（RAMdisk）、copy/fill | 未作成 |
| `host/` | ホスト共通のプロトコルcodec（C参照実装） | LINK＋Dock GFX v0を収録、ESP-IDFへハッシュ付き同期 |
| `builds/` | ビットストリーム別のプロジェクト（LINK、GFX、NPU、MEM）と合成レポート | Dock LINK/GFXはOSSランナーで生成成功。Gowin用Tclは未実行 |

移管時は移管元のコミットSHA、ライセンス表記、テストの実行結果を記録する。試験は`fpga/`をカレントディレクトリとして実行する。参照モデル（C++/Python）のうちRTLの期待値生成に使うものは本リポジトリへ移し、ホスト側のベンチマークやモデル評価は元のリポジトリに残す。

2026-11-03のGPU LAB実機開発は[開発記録](../docs/GPU_LAB開発_2026-11-03.md)と
[最終検証JSON](validation/gpu-lab-final-2026-11-03.json)を参照。
ジャンパ8bitの画像受信はPARLIO DMA8MHzで比較試験を通過したが、配線の絶対上限ではない。
既存コマンドは維持し、完全タイル読出しは能力確認を伴うオプション。
全ホストでの高速DMA実装、NPU/MEMとの同時搭載、DDR3動作を実証したものではない。
