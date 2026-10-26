# 作業の前提

- 本プロジェクトの目的は、`tab5-linux-fpga` と `tab5-fpga-gpu` の要求を満たす、Tab5 × Tang Primer 20K Core共通キャリア基板を設計・検証すること。
- 作業開始時と仕様変更前に、両リポジトリのREADME・要求資料・関連実装を確認する。Linux側は `docs/DEVELOPMENT_GOALS.md`、Device Tree、通信ドライバ、GPU側は `docs/Project_B_Tab5_FPGA_GPU.md`、通信・表示実装を確認する。実装がない場合は未実装と記録する。
- Linux側の研究要求は、関連する `esp32p4-linux-fpga-memory` の計画書も照合する。研究リポジトリだけの確認でLinux本体の確認を代替しない。
- 参照した版・要求・未確定事項を記録し、両用途への適合性を示してからピン、電源、通信方式を確定する。矛盾があれば仕様へ記録して解消する。
- 共通仕様は本リポジトリを起点とし、変更時は関連プロジェクトとの整合と反映の要否を確認する。
- Linux用とGPU用は別ソフトウェア・別FPGAビットストリームで使用し、初期の同時動作は要件に含めない。
- GPIO、電源、PARLIO DMA、転送性能は未検証の案を実証済みとして扱わない。FPGA DDR3は透過的なLinuxメインRAM増設ではない。
- GitHubリポジトリは所有者に合わせ、`airpocket-soundman` は `D:\github\airpocket-soundman`、`Factory-IoT` は `D:\github\Factory-IoT` 配下に配置する。
