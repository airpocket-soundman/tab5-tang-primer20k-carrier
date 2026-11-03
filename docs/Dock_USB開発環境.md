# 公式DockのUSB書込み開発環境

対象は **Sipeed Tang Primer 20K Dock + Core**。Dock内蔵のBL702 USB-JTAGを使うため、別売りライターは不要。PCとDockの「USB-JTAG」端子を、データ通信対応USBケーブルで接続する。自作キャリアの電源用USB-Cとは別の経路である。

## 開発コマンド

リポジトリのルートでWindowsのPythonから実行する。

```powershell
python fpga/tools/dock_dev.py setup
python fpga/tools/dock_dev.py doctor
python fpga/tools/dock_dev.py test
python fpga/tools/dock_dev.py build link
python fpga/tools/dock_dev.py build gfx
python fpga/tools/dock_dev.py detect
python fpga/tools/dock_dev.py program link --dry-run
python fpga/tools/dock_dev.py program link
python fpga/tools/dock_dev.py program gfx
```

`setup`は公式OSS CAD Suiteの2026-10-26版からWindows用openFPGALoaderと実行時ファイルを取得する。配布アーカイブのサイズとSHA-256を固定して検証する。ビルド用のYoWASP Yosys、nextpnr、Apiculaも指定版でローカルvenvに用意する。ツール・キャッシュ・結果はすべてGit管理外の`fpga/build/`へ置く。システムPATHやUSBドライバは変更しない。

同じアーカイブからWindowsネイティブのIcarus／vvpも展開する。[全機能テスト計画](全機能テスト計画.md)の`test_features.py --rtl --synth --build`で、NPU・三角形などの要素試験もまとめて実行できる。Cコーデック試験には別途Cコンパイラが必要で、このPCでは既存のZigを`--cc`で指定して通過を確認した。

`doctor`はツールの起動確認、`detect`はJTAG経由のFPGA識別、`program`は現在のビルドをSRAMへ転送する。SRAMの構成は電源断で失われ、次回起動時は既存フラッシュから起動する。フラッシュ常駐化はこのコマンドには含めない。

書込み前に、対象variant、合成・配置配線・packの成功、現在のソースハッシュ、生成`.fs`のハッシュを確認する。ソース変更後は再ビルドする。`--dry-run`は同じ検査を行い、書込みコマンドだけ表示する。USB機器は開かない。実行コマンド、ツール・画像のハッシュ、結果は`fpga/build/programming/`へ記録する。

複数のFTDI機器がある場合は、識別したDockのシリアルを明示する。

```powershell
python fpga/tools/dock_dev.py detect --serial <DockのUSBシリアル>
python fpga/tools/dock_dev.py program gfx --serial <DockのUSBシリアル>
```

## 接続から試験まで

1. 初回はTab5とのジャンパを外したDock単体でUSB認識とFPGA識別を確認する。Coreを確実に装着し、Core電源を有効にする。公式資料ではDockの電源用DIPスイッチ1を下げる指定がある。通信ARM用のSW0とは区別する。
2. `detect`の結果がTang Primer 20KのGW2A-18系であることを確認し、SW0をOFFにしてLINKをSRAMへ書き込む。
3. [ジャンパGFXテスト手順](Dockジャンパ_GFXテスト手順.md)の配線・電圧確認を行い、LINK疎通、GFX読み戻し、Tab5内蔵LCDの順に試す。

WindowsにDockが現れなければUSB-JTAG端子とデータケーブルを確認する。USBとして認識されるがopenFPGALoaderが開けない場合は、対象インターフェースのドライバを確認する。ドライバ変更は接続したDockを特定してから行い、他機器やUART側のドライバをまとめて置換しない。未接続の段階でドライバ問題と決めつけない。

Tab5側は別USB接続・別ESP-IDFファームである。LCD診断ファームのビルド・依存版・プロファイルは[Tab5ホストソフト開発ガイド](Tab5ホストソフト開発ガイド.md)とホストリポジトリ`bringup/tab5`を参照する。

## 参照

- [Sipeed公式 Tang Primer 20K](https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html)：DockのUSB-JTAG内蔵とCore電源。
- [openFPGALoader Gowin手順](https://trabucayre.github.io/openFPGALoader/vendors/gowin.html)：`tangprimer20k`と`-m`によるSRAM転送。
- [openFPGALoader初期手順](https://trabucayre.github.io/openFPGALoader/guide/first-steps.html)：SRAMとフラッシュの区別。
- [固定したOSS CAD Suite配布版](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-10-26)。

ソフトウェアのビルド・論理シミュレーション結果は[検証記録](../fpga/validation/README.md)を参照。実機識別・書込み結果は実際の実行ログで判断する。

2026-10-28の環境確認：WindowsネイティブのopenFPGALoader v1.2.0が起動し、`tangprimer20k`対応を確認した。統合コマンドからLINK/GFXを再ビルドし、以前と同じ`.fs`ハッシュを得た。両版の書込みdry-run、ビルド・書込み・セットアップの18単体試験が通過。実際の`detect`は`device not found`で、WindowsのUSB一覧にもDockは現れていない。USB接続後の識別・ドライバ動作・SRAM転送は未確認。
