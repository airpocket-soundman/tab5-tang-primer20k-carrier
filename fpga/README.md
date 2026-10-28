# FPGAソース

Tang Primer 20K Core（GW2A-LV18PG256C8/I7）上のFPGAデバイスのソースと制約を管理する。役割分担は[リポジトリ分担と参照ルール](../docs/リポジトリ分担と参照ルール.md)、機能とビットストリームの構成は[FPGAデバイス構成](../docs/FPGAデバイス構成_ビットストリームと機能.md)。

状態（2026-10-28）：tab5-fpga-gpuからRTLと試験を移管済み（[移管記録](MIGRATION.md)）。Dock用.cst案あり。RTLシミュレーション・合成・実機は未実施。

## 構成（予定）

| ディレクトリ | 内容 | 状態 |
|---|---|---|
| `constraints/carrier/` | キャリア用.cst/.sdc。`kicad/core_pin_assignment.csv`から生成して一致を検査 | 未作成 |
| `constraints/dock/` | 公式Dockジャンパ試験用.cst | [tab5_dock_link_v0.cst](constraints/dock/tab5_dock_link_v0.cst)（案） |
| `platform/` | 基板別top、クロック・リセット、ARM、DDR3コントローラ設定 | 未作成 |
| `link/` | リンク物理層（DIR/READY/OE）、v0/v1プロトコル、CRC | v0 RTL・試験を移管済み |
| `gfx/` | 2D命令、三角形ラスタライズ、Zバッファ、計算描画 | 三角形coverage/depth/fragmentのRTL・試験を移管済み |
| `hdmi/` | DVI/HDMIスキャンアウト（GFXのオプション） | 未作成。参考：`docs/reference/tang-primer-20k/official-hdmi/` |
| `npu/` | INT8 MAC、requant、dot job、構成A/B/C | MAC lane、requant、dot jobのRTL・試験を移管済み |
| `reference/` | RTL期待値用の参照モデル（Python） | 移管済み |
| `tools/` | 既存シミュレータがある場合だけRTL試験を実行 | `run_existing_rtl.py`を移管済み |
| `mem/` | ブロック格納（RAMdisk）、copy/fill | 未作成 |
| `host/` | ホスト共通のプロトコルcodec（C参照実装） | 移管元候補：tab5-fpga-gpu `bringup/tab5/main/link_protocol.h`、tab5-linux-fpga `tools/fpga-link/` |
| `builds/` | ビットストリーム別のプロジェクト（LINK、GFX、NPU、MEM）と合成レポート | 未作成 |

移管時は移管元のコミットSHA、ライセンス表記、テストの実行結果を記録する。試験は`fpga/`をカレントディレクトリとして実行する。参照モデル（C++/Python）のうちRTLの期待値生成に使うものは本リポジトリへ移し、ホスト側のベンチマークやモデル評価は元のリポジトリに残す。
