# 作業の前提

- 本プロジェクトの目的は、Tab5 × Tang Primer 20K Coreの共通キャリア基板と、その上で動くFPGAデバイス（全ビットストリーム）の仕様・実装・検証を一元管理すること。ホストOS（ESP-IDF、MeOS、NOMMU Linux）の各リポジトリは、本リポジトリの仕様を参照してホスト側を開発する。役割分担と参照ルールは `docs/リポジトリ分担と参照ルール.md` に従う。
- 本リポジトリで管理するもの：基板設計、接続仕様（ピン、電気条件、リンクプロトコル）、FPGAソース（共通基盤、LINK、GFX、NPU、HDMI、RAMdisk）、.cst/.sdc、ビットストリーム構成と使い方（コマンド、能力問合せ、エラー）、FPGA側の検証（RTLテスト、参照モデル）。
- 作業開始時と仕様変更前に、ホスト側リポジトリのREADME・要求資料・関連実装を確認する。Linux側は `tab5-linux-fpga` の `docs/DEVELOPMENT_GOALS.md`、Device Tree、通信ドライバ、MeOS側は `tab5-meos-fpga` の `docs/FPGA_CARRIER_REQUIREMENTS.md`、ESP-IDF側は `tab5-fpga-gpu` の `docs/Project_B_Tab5_FPGA_GPU.md`、通信・表示実装を確認する。実装がない場合は未実装と記録する。
- Linux側の外部メモリ研究要求は `esp32p4-linux-fpga-memory` の計画書も照合する。研究リポジトリだけの確認でLinux本体の確認を代替しない。
- 参照した版・要求・未確定事項を記録し、全ホストへの適合性を示してからピン、電源、通信方式、デバイスのコマンド仕様を確定する。矛盾があれば仕様へ記録して解消する。
- 仕様・コマンド・ピンを変更した場合は、影響するホスト側リポジトリへの反映の要否を確認し、反映した版を記録する。
- ビットストリームは機能別（LINK、GFX、NPU、MEM）に分け、どれも全ホストOSから使える形にする。異なる機能の同時搭載は、資源・性能の計測で問題がない組合せだけとする。
- GPIO、電源、PARLIO DMA、転送性能、合成結果は未検証の案を実証済みとして扱わない。FPGA DDR3は透過的なLinuxメインRAM増設ではない。
- GitHubリポジトリは所有者に合わせ、`airpocket-soundman` は `D:\github\airpocket-soundman`、`Factory-IoT` は `D:\github\Factory-IoT` 配下に配置する。
