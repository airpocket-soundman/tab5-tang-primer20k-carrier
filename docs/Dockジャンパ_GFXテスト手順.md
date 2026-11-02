# Dockジャンパ接続とTab5内蔵LCDのGFX試験

[HTML・SVG配線ガイド（基板上の位置と結線図）](../site/dock-jumper-wiring.html)

2026-10-28。Dock LINK/GFXはOSSツールで合成・配置配線・packまで成功。限定試験モデルによる合成後GFXの機能照合も通過。Gowin EDA、外部I/Oタイミング、実機の通信／LCD表示は未検証。

公式DockはUSB-JTAGを内蔵しており、別売りライターは不要。[USB開発環境のセットアップ・書込みコマンド](Dock_USB開発環境.md)を参照。

## 今回の到達点

Tab5がGPIOで8bitパラレル要求を送り、FPGAが32×32 RGB565画像を内部RAMに描画する。
Tab5が全1,024画素を読み戻して期待値と比較し、合格した**読み戻しデータ**を内蔵LCDに512×512へ拡大表示する。
PCの画像で代用せず、矩形の塗りと点描画はFPGAが行う。DDR3、三角形、HDMI、PARLIO DMA、30FPS評価は次段階。

通常のGPU LABとは独立した診断ファームで、実験名は `dock-gfx-v0`。
LINK（接続確認のみ）とGFX（描画診断）は別ビットストリームとしてビルドする。
基板ピン・電源は既存のDock案を維持し、将来のDDR3 v1プロトコルは今回確定しない。

## 参照版と適合性

| 対象 | 参照した版 | 確認内容・今回の扱い |
|---|---|---|
| キャリア | `e5a386d`を基点とする`codex/dock-jumper-gfx` | 共通仕様、Dock配線表、RTL・移管記録。GPIO・ball・電源の変更なし |
| ESP-IDFホスト | `tab5-fpga-gpu d4d89e3` | README、Project_B、`bringup/tab5/main`、GPU LABの`main/lab.hpp`と`app_main.cpp`。既存GPUバックエンドは未実装。今回は独立診断にxfer／gfxとLCD表示を追加 |
| Linuxホスト | `tab5-linux-fpga cfc9a6e`（fetch後のorigin/main） | README、DEVELOPMENT_GOALS、`linux/dts/easystick-stamp-p4.dts`と`tab5-overrides.dtsi`、FPGA/PARLIO関連ファイル一覧。Tab5側C6のSDIOは8〜13、LCDバックライトは22。GPIOドライバの他ピンへの影響確認は別途必要。`tools/fpga-link/`はこの版のツリーに存在せず、物理通信ドライバも確認できない |
| MeOSホスト | `tab5-meos-fpga 7607793`（fetch後のorigin/main） | FPGA_CARRIER_REQUIREMENTS。双方向転送、起動Hi-Z、回復、HAL/LL＋GDMAの要求。物理backendは未実装。今回のフレームはOS非依存だがMeOSでの通信・表示は追加していない |
| Linux研究 | `esp32p4-linux-fpga-memory e84b59e`（fetch後のorigin/main） | README・Project_A。128MB全域の明示的READ/WRITE、CRC、演算用途。今回の2KiB画像RAMはこの要求の達成にはならない |

Linux／MeOS向け実装と仕様コピーの更新は今回不要。両ホストが使う場合は本試験仕様を参照して物理backendを追加する。
ESP-IDFホストへはキャリア正本`fpga/host/link_protocol.h`を同期し、SHA-256を`bringup/carrier-codec.json`へ記録する。
旧資料の「Linux tools/fpga-linkを使用可能」という記載は参照版と一致しないため、存在を確認してから利用する。

## 配線と初回確認

配線の正本は[Dockジャンパ試験の配線表](Dockジャンパ試験_配線とFPGA構成_2026-10-28.md)。
必要な信号はD0〜7、CLK、DIR、READYの11本と共通GND。AUX0〜3は本実装で不使用なので未接続でよい。

1. Dock単体でヘッダの電源とGND、版、3.3Vバンクを測る。手元のJ5はユーザー確認シルクで1/2番が3.3V、3/4番がGND。保存済み回路図と電源ペアが異なるため、実物に合わせる。J12/J14は資料上1/2番が3.3V、3/4番がGNDで、実物照合は未完了。
2. Tab5とDockの電源レールは結ばず、それぞれ給電。各信号に220〜330Ω、15cm以下、GND線を併走。片側電源断の前には信号線を外す。
3. カメラ／RGB LCD／マイク等のDock周辺機器を外す。SW0はOFF。Tab5の該当GPIOの起動状態を確認する。
4. FPGAにLINKまたはGFXのビットストリームをSRAMへ書き込み、SW0 OFFのままKey_0を押してリセットする。初回はフラッシュ常駐化せず復帰経路を確保する。
5. 両側の電源とTab5の入力状態を確認してSW0をON。SW0がFPGA側ARM、後述の`arm`がホスト側のGPIO有効化。

抵抗はIoff分離の代替にならない。速度や電圧は実測していない。

## FPGAのビルド

### OSSでの生成済み成果物

`fpga/build/dock-bench/`に`dock-link.fs`、`dock-gfx.fs`とハッシュ・生成manifestを保存する。
内蔵LCD描画は`dock-gfx.fs`を使う。`dock-link.fs`はID／echo／反転専用。
ビルドの正本は[build_oss.py](../fpga/builds/dock/build_oss.py)。今回の環境はYoWASP Yosys 0.70、nextpnr 0.11.1、Apicula 0.32。

```powershell
python fpga/builds/dock/build_oss.py gfx --yosys fpga/build/oss-env/Scripts/yowasp-yosys.exe --nextpnr fpga/build/oss-env/Scripts/yowasp-nextpnr-himbaechel-gowin.exe --pack fpga/build/oss-env/Scripts/gowin_pack.exe
```

この例のカレントはキャリアリポジトリ直下。通常のネイティブツールでも実際の実行ファイルを指定して使える。
Apiculaのfamily名は`GW2A-18`。`--sspi_as_gpio`を指定してT10＝SI/D2を通常GPIOへ再利用し、JTAG／MSPI／RECONFIG_NはGPIO化しない。
内部27MHzのみを対象とし、Gowin用SDCや外部I/Oのsetup/hold制約はこのOSSフローでは適用していない。
`bus_clk`の専用経路失敗→一般経路の警告は両版で発生し、抑止せず記録している。

### Gowin EDA用の準備

Gowin EDAで`GW2A-LV18PG256C8/I7`、device family `GW2A-18C`を選ぶ。
[Sipeed公式のIDE導入資料](https://wiki.sipeed.com/hardware/en/tang/common-doc/get_started/install-the-ide.html)と同じ対象。

```powershell
cd D:\GitHub\tab5-tang-primer20k-carrier\fpga\builds\dock
gw_sh build.tcl link
gw_sh build.tcl gfx
```

出力先は`fpga/build/dock-link/`と`fpga/build/dock-gfx/`。
CLIの`build.tcl`はGowin未実行のため、利用するEDA版でコマンドとデバイス指定を確認する。
GUIで作る場合も同じRTL・CST・SDCを登録し、LINKのtopは`tab5_dock_top`、GFXは`tab5_dock_gfx_top`を選ぶ。

- クロックはCoreの27MHz。バスCLKはsys_clkでサンプリングし、RTLのクロックには使わない。
- `tab5_dock.sdc`は内部クロックの制約。外部I/Oの制約・CDC評価は未完了で、タイミング閉塞を主張しない。
- T10はボード上のネット名がFPGA_RSTで、デバイス上はSI/D2。ビルドTclはSSPIのGPIO再利用を指定する。未使用ピン・全バンク電圧をEDAのpin reportと照合する。CSTの受理は実配線検証にはならない。
- LEDは負論理で0=ARM、1=データOE、2=READY、3=heartbeat。CRC／timeout専用LEDではない。
- 実機に渡す前に合成資源・RAM推論・配置配線・タイミングレポートと`.fs`のSHA-256を保存する。

## Tab5ファームのビルドと操作

所有者別の作業先は`D:\github\airpocket-soundman\tab5-fpga-gpu`、ブランチは`codex/dock-jumper-gfx`。
従来の`D:\GitHub\tab5-fpga-gpu`チェックアウトには今回の変更を入れていない。

ESP-IDF環境を有効にしてから:

今回のビルド組合せはESP-IDF 5.5.2、Tab5 BSP 1.3.2、ESP LVGL port 2.6.2、LVGL 9.2.2。
WindowsのComponent Manager 2.4.4の再試行問題を避け、別Python環境の2.4.5で確認した。
Dockプロファイル無効／有効の両構成でビルド成功。[検証記録・バイナリのハッシュ](../fpga/validation/README.md)を参照。

```powershell
cd D:\github\airpocket-soundman\tab5-fpga-gpu
python bringup/sync_carrier_codec.py --carrier D:\GitHub\tab5-tang-primer20k-carrier --check
idf.py -C bringup/tab5 -B build/dock-idf -D SDKCONFIG=D:/github/airpocket-soundman/tab5-fpga-gpu/build/dock-idf/sdkconfig menuconfig
idf.py -C bringup/tab5 -B build/dock-idf build
```

`Dock jumper diagnostic`の`Enable manually reviewed Dock jumper profile`は初期OFF。
上記の配線・起動状態の確認後にONにする。`Show verified ... on Tab5 LCD`はON。
この設定は確認結果を自動保証するものではなく、`verified`のJSON値はこの手動設定を表す。
ファームは起動時にリンクGPIOを操作せず、明示的`arm`まで出力しない。
診断用のパーティションはfactory 4MiB、Tab5のフラッシュ設定は16MiB。既存のOSイメージとは独立したファームであり、実機書込み時は元のファームの復元手順を確保する。
arm時には`gpio_config`で入力・GPIO機能・pullなしを設定し、最小drive strengthを選ぶ。
現行の`arm`はD線を入力、CLK／DIRをLOWに保ち150ms以上待機してFPGAの残留フレームをtimeoutさせ、READY=0を最大100ms待つ。HIGHが続けば`ready_stuck_high`として入力状態へ戻す。物理SW0やKey_0を操作する処理ではない。
GPIO2〜5のpad JTAGやGPIO19のUSB FS機能を併用しない。USB Serial/JTAGのコンソールを使う。

実機へ書き込み、コンソールを開く作業は配線確認後に行う。今回の開発ではUSB／COMを開いていない。
コンソールでの順序:

```text
status
arm dock-jumper-v0
test
arm dock-jumper-v0
gfx
```

`test`はID＋全256値echo／反転の513トランザクション後にdisarmする。
`gfx`はGFXビットストリームでのみ動き、黒クリア、赤／緑／青／白の非対称矩形、右下の黄色の点を生成。
全画素一致後にリンクをdisarmし、読み戻した画像をLCDへ送る。
成功ログは`gfx_pass:true,pixels:1024,lcd_submitted:true`。
LCDへの描画要求成功と、実際のパネル表示確認は区別して記録する。
失敗時はGPIOを入力へ戻し、前回成功画像が残る場合はLCDラベルに失敗を表示する。
中断は`disarm`またはDock SW0 OFF。

## PCからの追加確認

PC上の模擬確認（機器への接続なし）:

```powershell
cd D:\GitHub\tab5-tang-primer20k-carrier\fpga
python tools/dock_gfx_demo.py --mock
python -m unittest discover -s gfx/tests -p "test_*.py"
python -m unittest discover -s host/tests -p "test_*.py"
python tools/run_existing_rtl.py --require
```

C試験はCコンパイラがない環境ではskip。RTL試験はIcarus／vvpが必要。
PCから実リンクを操作する場合はTab5コンソールを閉じ、pyserialを用意して明示指定する:

```powershell
python tools/dock_gfx_demo.py --port COMn --arm --output build/dock-gfx/readback.ppm
```

このPC経路は画像をPCへ保存し、LCDへの表示は行わない。内蔵LCD試験はコンソールの`gfx`を使う。
PC経路も同じ全画素照合を実施し、処理終了時にdisarmする。失敗応答・sequence違い・CRC不一致を検出する。

## 実機記録と次段階

OSコミット、キャリアの版、ビットストリームハッシュ、Tab5液晶型番／SoC revision、Dock版、
線長／抵抗、電圧、CLK波形、513件の通信結果、GFX結果とLCD写真を記録する。
最大5kHzのGPIO診断は速度評価ではなく、通信・描画・読み戻しの成立確認。

次は生成済みOSSビットストリームでの低速実機試験。Gowin EDAでの照合も残る。その後にPARLIO TX/RX、turnaround、DDR3全域、
描画コマンド拡張と大きなフレームへ進む。Linux／MeOS向けの物理backendは別作業。
