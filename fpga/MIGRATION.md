# tab5-fpga-gpu からの移管記録

2026-10-28。ユーザー指示により、tab5-fpga-gpu の RTL、接続試験RTL、RTL用テストベクタ生成と、その期待値を作る参照モデルを本ディレクトリへ移管した。方針は[リポジトリ分担と参照ルール](../docs/リポジトリ分担と参照ルール.md)。

## 移管元

- リポジトリ：airpocket-soundman/tab5-fpga-gpu
- コミット：`3b1ace3d91c6305ec0e32378f8819fce208c2aa7`（main、2026-10-23 "docs: record successful host CI and explicit unexecuted RTL status"）
- 対象ファイルの履歴：`10a1a9b`、`a6ae7a1`、`8d846c2`、`f50a634`。作成者はすべて airpocket-soundman。

## ライセンス表記

移管元リポジトリにはLICENSE等のファイルがなく、対象ファイルにもSPDX・著作権表記はない。本リポジトリにもLICENSEはない。同一所有者のリポジトリ間での移管であり、ライセンスの付与・変更はしていない（移管元と同じく表記なし）。第三者へ配布する場合の条件は未定のため、配布前に決める。

## 変更点

内容は移管元と同一。ディレクトリ構成の変更に合わせて、パス文字列だけを書き換えた（`bringup/rtl`→`link/rtl`、`bringup/tests`→`link/tests`、`rtl/game`→`gfx/rtl`、`tests/rtl_game`→`gfx/tests`、`rtl/compute`→`npu/rtl`、`tests/rtl_compute`→`npu/tests`）。テストベンチの`$readmemh`と実行スクリプトは `fpga/` をカレントディレクトリとして動く。

参照モデル `reference/*.py` はtab5-fpga-gpu側のホスト試験・ベンチマークでも使うため、移管元にも残る。RTLの期待値の正は本ディレクトリの版とし、変更時は両者の差分を確認する。

## ファイル対応

SHA-256は移管元blob（改行をLFに正規化）の先頭16桁。

| 移管元 | 移管先（fpga/） | 内容 | 移管元SHA-256 |
|---|---|---|---|
| `rtl/game/triangle_coverage.v` | `gfx/rtl/triangle_coverage.v` | 同一 | `229e996701d7fcd2` |
| `rtl/game/triangle_depth.v` | `gfx/rtl/triangle_depth.v` | 同一 | `de970c1412f827a1` |
| `rtl/game/triangle_fragment.v` | `gfx/rtl/triangle_fragment.v` | 同一 | `164a23321804c210` |
| `tests/rtl_game/depth_expected.mem` | `gfx/tests/depth_expected.mem` | 同一 | `aa85d6effa3c13fb` |
| `tests/rtl_game/depth_inputs.mem` | `gfx/tests/depth_inputs.mem` | 同一 | `831a460f0cc5caac` |
| `tests/rtl_game/depth_manifest.json` | `gfx/tests/depth_manifest.json` | 同一 | `7edf41a5fed0afce` |
| `tests/rtl_game/expected.mem` | `gfx/tests/expected.mem` | 同一 | `6311c1b832cae661` |
| `tests/rtl_game/fragment_expected.mem` | `gfx/tests/fragment_expected.mem` | 同一 | `5ee72da7c1105149` |
| `tests/rtl_game/fragment_inputs.mem` | `gfx/tests/fragment_inputs.mem` | 同一 | `06036bf2ffa8ff68` |
| `tests/rtl_game/fragment_manifest.json` | `gfx/tests/fragment_manifest.json` | 同一 | `08bd5e65a3b576a7` |
| `tests/rtl_game/generate_depth_vectors.py` | `gfx/tests/generate_depth_vectors.py` | 同一 | `e88b5c298d69a254` |
| `tests/rtl_game/generate_fragment_vectors.py` | `gfx/tests/generate_fragment_vectors.py` | 同一 | `ba33035e35d8c917` |
| `tests/rtl_game/generate_vectors.py` | `gfx/tests/generate_vectors.py` | 同一 | `70c9a8f460861551` |
| `tests/rtl_game/inputs.mem` | `gfx/tests/inputs.mem` | 同一 | `73449dbfc2f6cf82` |
| `tests/rtl_game/manifest.json` | `gfx/tests/manifest.json` | 同一 | `fb0e69473ee206b9` |
| `tests/rtl_game/run.py` | `gfx/tests/run.py` | パスのみ変更 | `12ac2774349801e6` |
| `tests/rtl_game/run_depth.py` | `gfx/tests/run_depth.py` | パスのみ変更 | `3ce4676a1590b3af` |
| `tests/rtl_game/run_fragment.py` | `gfx/tests/run_fragment.py` | パスのみ変更 | `a0cda20f9b97b03f` |
| `tests/rtl_game/tb_triangle_coverage.v` | `gfx/tests/tb_triangle_coverage.v` | パスのみ変更 | `4517f25b5e542432` |
| `tests/rtl_game/tb_triangle_depth.v` | `gfx/tests/tb_triangle_depth.v` | パスのみ変更 | `79c63197a17d7c34` |
| `tests/rtl_game/tb_triangle_fragment.v` | `gfx/tests/tb_triangle_fragment.v` | パスのみ変更 | `20d718c6957aa4aa` |
| `tests/rtl_game/test_depth_vectors.py` | `gfx/tests/test_depth_vectors.py` | 同一 | `0ac6560b2273001b` |
| `tests/rtl_game/test_fragment_vectors.py` | `gfx/tests/test_fragment_vectors.py` | 同一 | `309c33db8ebb72cb` |
| `tests/rtl_game/test_vectors.py` | `gfx/tests/test_vectors.py` | 同一 | `ae470a673ef43322` |
| `bringup/rtl/link_bringup.v` | `link/rtl/link_bringup.v` | 同一 | `344f0bcb45ebf8ff` |
| `bringup/rtl/link_bus_wrapper.v` | `link/rtl/link_bus_wrapper.v` | 同一 | `8c29203720c5763f` |
| `bringup/tests/generate_vectors.py` | `link/tests/generate_vectors.py` | パスのみ変更 | `0cbda767cc9409bc` |
| `bringup/tests/link_vectors.json` | `link/tests/link_vectors.json` | 同一 | `8b1d8e2a9339ffce` |
| `bringup/tests/link_vectors.mem` | `link/tests/link_vectors.mem` | 同一 | `e554e85c2af37066` |
| `bringup/tests/run_rtl.py` | `link/tests/run_rtl.py` | パスのみ変更 | `b3bae384712f7051` |
| `bringup/tests/tb_link_bringup.v` | `link/tests/tb_link_bringup.v` | 同一 | `44b274db4c51cd34` |
| `bringup/tests/tb_link_vectors.v` | `link/tests/tb_link_vectors.v` | パスのみ変更 | `c6d09a31e959b51c` |
| `rtl/compute/int8_dot_job.v` | `npu/rtl/int8_dot_job.v` | 同一 | `0f985e2b1d8a1e41` |
| `rtl/compute/int8_mac_lane.v` | `npu/rtl/int8_mac_lane.v` | 同一 | `07199c3a6c4354c5` |
| `rtl/compute/int8_requantize.v` | `npu/rtl/int8_requantize.v` | 同一 | `12873790ccdc313a` |
| `rtl/compute/README.md` | `npu/rtl/README.md` | パスのみ変更 | `907affcc4f000b11` |
| `rtl/compute/REQUANTIZE.md` | `npu/rtl/REQUANTIZE.md` | パスのみ変更 | `a775215cf7230280` |
| `tests/rtl_compute/generate_dot_vectors.py` | `npu/tests/generate_dot_vectors.py` | 同一 | `9e6e7f8a40a0fc85` |
| `tests/rtl_compute/generate_requant_vectors.py` | `npu/tests/generate_requant_vectors.py` | 同一 | `be4c7e96f4f38ac1` |
| `tests/rtl_compute/generate_vectors.py` | `npu/tests/generate_vectors.py` | 同一 | `435b6c1b3610cc2a` |
| `tests/rtl_compute/test_dot_vectors.py` | `npu/tests/test_dot_vectors.py` | 同一 | `970f60df749c0faa` |
| `tests/rtl_compute/test_requant_vectors.py` | `npu/tests/test_requant_vectors.py` | 同一 | `480247336b94de91` |
| `tests/rtl_compute/test_vectors.py` | `npu/tests/test_vectors.py` | 同一 | `50615d32dae18477` |
| `reference/compute_reference.py` | `reference/compute_reference.py` | 同一 | `23d48e8b2959db7b` |
| `reference/game_gpu_reference.py` | `reference/game_gpu_reference.py` | 同一 | `67bd5d81aba5b982` |
| `reference/link_protocol.py` | `reference/link_protocol.py` | 同一 | `235f503d053a275e` |
| `tools/run_existing_rtl.py` | `tools/run_existing_rtl.py` | パスのみ変更 | `1f48a0f5ab521b94` |

移管しなかったもの：`bringup/tests/run_codec.py`、`bringup/tests/test_codec.c`（Tab5ファームのCコーデック試験。ホスト側）、`bringup/generate_cst.py`、`bringup/profiles/`、`bringup/build-manifest.json`、`bringup/tab5/`（ESP-IDFホスト）。CST生成はキャリアのピン表から作り直す（`constraints/carrier/`、未作成）。

## 移管後の試験（2026-10-28、Windows、Python 3.12、`fpga/`で実行）

| コマンド | 結果 |
|---|---|
| `python -m unittest discover -s gfx/tests -p "test_*.py"` | 9件成功 |
| `python -m unittest discover -s npu/tests -p "test_*.py"` | 9件成功 |
| `python gfx/tests/generate_vectors.py --check` ほか depth、fragment | 3,328 / 1,154 / 436ベクタ一致 |
| `python link/tests/generate_vectors.py` | 583ベクタを再生成し、移管元の `link_vectors.json`・`.mem` と一致 |
| `python npu/tests/generate_*vectors.py --output build/rtl-compute` | MAC、requant、dotのベクタとテストベンチを生成 |
| `python tools/run_existing_rtl.py` | **未実行**：iverilog/vvpがなく、導入もしていない。RTLシミュレーション・合成は移管前と同じく未実施 |

移管前の移管元でも `tests/rtl_game`、`tests/rtl_compute` の単体試験は成功している（同日確認）。

移管元での後処理：tab5-fpga-gpu ブランチ`docs/fpga-device-ownership`の`d4d89e3`で移管済みファイルを削除し、ホストCIからRTL関連ステップを外した。同ブランチのホスト試験は56件成功（5件スキップ）。`bringup/tests/run_codec.py`はローカルにCコンパイラ`cc`がなく未実行。
