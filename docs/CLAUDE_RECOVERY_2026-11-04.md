# Claude開発中断からの回収記録（2026-11-04）

Tab5側8本・FPGA側10本のClaude作業ブランチを回収した。5ワークツリーに残っていた未コミット実装を、それぞれのブランチで保存した。各ブランチの `docs/recovery-2026-11-04/snapshot.json` に回収前のHEAD・変更一覧・試験結果を記録している。

このブランチは回収時mainを起点にした保存索引で、各実験実装を統合したアプリではない。mainや別の実験へ未完成のコードをマージしていない。再開は下表の対象ブランチで行う。

## 回収内容と確認結果

- 常駐モデル描画のホスト統合、中間周波数とドライブ設定、返信クロックのエッジ計測、Fireの参照実装/RTL、返信位相遅延の途中実装を保存した。
- モデル描画ホストの `tests/test_fpga_backend.py` はコンパイル失敗。テスト内のcolors/depths、cube_face_colorが未定義で、main内に値なしreturnもある。修正せず保存した。
- 中間周波数ブランチの `python -m unittest discover -s tests -p test_dma_stream.py -v` はキュー試験合格、プロファイル試験失敗。`dma_scaled_test.cpp:24` のlease下限アサーションが失敗する。
- FireのC/Python参照比較は2試験合格（3005入力の一致を含む）。RTL/Python比較は370ベクトル合格。IcarusのbinとlibをプロセスPATHに追加して実行した。timescaleとreadmemh範囲に警告あり。GPU LABへの統合や合成・実機合格を意味しない。
- 保存済みの統合版実機記録では、FPGA85bac224で20MHz negativeは3シーン全画素一致、20MHz positiveと25MHz両位相は失敗。ジャンパ線の物理上限は未確定。
- 保存済みのDMA最適化記録では、コピー削減の効果は約1〜2%で対照のばらつきと近い。TXリセットpolicy2は最初のバッチで失敗しpolicy0に戻したと記録されている。リセット除去成功とは扱わない。
- 保存済みのDDRペア発行候補では、accepted command/dataは7/7だがschedulerが取り出さずBIST失敗。DDR読み書き成功ではない。
- 回収中にハードウェアへの書込み・ARM・通信試験は行っていない。現在の基板上イメージは再照会していない。

## ローカル生成物

生成済みのTab5アプリBIN、bootloader、partition、sdkconfig、書込み配置、ビルドログをブランチごとに保存し、44ファイルのgzip復元内容をSHA-256で確認した。生成物と未コミットコードが同一であることは未検証。

Track A/FのGit管理外の生計測・PNG・RGB565等720ファイルを `raw-captures.tar.gz` に保存し、全ファイルの復元ハッシュを確認した。圧縮アーカイブと個別SHA-256一覧を同じブランチに収録している。

## リポジトリ間の扱い

FPGAの仕様・RTL・codecはcarrier、ESP-IDFアプリはtab5-fpga-gpuに保持する。今回の作業は中断状態の保存であり、暫定コマンド/ピン/仕様の確定は行っていない。MODEL拡張は実験仕様で、Linux/MeOSでの利用は未実装・未検証。DDRはLinuxメインRAM拡張の実証ではない。

LinuxのDEVELOPMENT_GOALS、MeOSのFPGA_CARRIER_REQUIREMENTS、外部メモリ研究の計画書、ESP-IDFのProject_Bと通信/描画関連ソースを参照した。各要求への適合確認は開発再開時の残作業である。

作業開始前から別の旧ワークツリーにあるDock bringup変更、および `D:/GitHub/tab5-tang-primer20k-carrier` のr5基板設計・README・画像の変更は今回のClaude GPU開発回収に混ぜず、元の場所に保持した。

## 再開方法

下表のcommitをcheckoutするか該当ブランチをfetchして再開する。mainへ統合する前に、モデル描画のコンパイル失敗と中間周波数のlease試験失敗を解消する。未実装・未検証の機能は各ブランチのsnapshot/既存試験記録を確認する。

| Repository | Branch | Saved commit |
|---|---|---|
| tab5-fpga-gpu | `claude/track-a-baseline` | [d55924fb3a](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/d55924fb3a9813d8e15d3163f0a7a0ea6a5475e9) |
| tab5-fpga-gpu | `claude/track-b-host` | [76155469f8](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/76155469f8f919d97ee110db7dd5219e5df3393c) |
| tab5-fpga-gpu | `claude/track-c-link-frequency` | [eb73a713e5](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/eb73a713e55c61dbc373e98ce87885823698cd36) |
| tab5-fpga-gpu | `claude/track-e-dma-opt` | [35d9a098c9](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/35d9a098c9a9269d9bf479bac1065712a7f05263) |
| tab5-fpga-gpu | `claude/track-f-integrate` | [ec8016a70b](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/ec8016a70b9547182212fb9352fbab674964e24a) |
| tab5-fpga-gpu | `claude/track-i-crc-fast` | [c80ffec6d4](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/c80ffec6d4ff6bd834aade88a11810cb6dd609fc) |
| tab5-fpga-gpu | `claude/track-k-model-host` | [55c9017382](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/55c9017382988f22c1cfc432ff5a80bbe2aa1b24) |
| tab5-fpga-gpu | `claude/track-m-midrate-drive` | [ba3a3640a7](https://github.com/airpocket-soundman/tab5-fpga-gpu/commit/ba3a3640a7c0b1d4c51c67b2c21b40442ea39fdc) |
| tab5-tang-primer20k-carrier | `claude/track-b-fpga` | [882a241589](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/882a241589c097ac4fbc59c35b1545404fb513cf) |
| tab5-tang-primer20k-carrier | `claude/track-d-ddr3` | [d1762c42ea](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/d1762c42ea66765f2cc0bac3f91486afeae60049) |
| tab5-tang-primer20k-carrier | `claude/track-g-fractal-dma` | [01c7d8286d](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/01c7d8286d7e254871f7d599c237d1b3edb2db72) |
| tab5-tang-primer20k-carrier | `claude/track-h-carrier-cst` | [9fd826cfe2](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/9fd826cfe208060de537a35788f98abe95bb0671) |
| tab5-tang-primer20k-carrier | `claude/track-i-crc-fast` | [4ba2460999](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/4ba24609994604178f5d34e71d1d6e734952cb51) |
| tab5-tang-primer20k-carrier | `claude/track-j-edge-counter` | [2ad7ec53d2](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/2ad7ec53d2c5c96078c98f641a1b061c9c7d8d18) |
| tab5-tang-primer20k-carrier | `claude/track-l-scenes` | [459480361c](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/459480361c6a3c01280313c313ba180e28f93d35) |
| tab5-tang-primer20k-carrier | `claude/track-n-reply-phase` | [356089b5fb](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/356089b5fbfc81c4a1b571bdffeb01298ca8c8f8) |
| tab5-tang-primer20k-carrier | `claude/track-o-npu-estimate` | [419c9db31b](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/419c9db31bdf53cc1aa84926086cabfc4b290cb8) |
| tab5-tang-primer20k-carrier | `claude/track-p-ddr3-variants` | [e58289eb81](https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/commit/e58289eb810d4d2d08146834fed1ac791ef34555) |
