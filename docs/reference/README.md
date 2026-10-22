# 参考資料（一次資料）

取得日：2026-10-22。各ファイルの著作権は発行元に帰属します。設計判断の根拠確認のためのローカルコピーです。

## Tab5（M5Stack）— `tab5/`

| ファイル | 内容 | 取得元 |
|---|---|---|
| Tab5_Schematics_PDF.pdf | Tab5回路図（5頁）。M5-Busは3頁目 | https://m5stack-doc.oss-cn-shenzhen.aliyuncs.com/1132/Tab5_Schematics_PDF.pdf |
| Tab5_Overall_Design_Block_Diagram.pdf | 全体ブロック図 | 同 `/Tab5_Overall_Design_Block_Diagram.pdf` |
| C145_Pinmap_Overview.png | ピンマップ概観（HVIN 6～24V表記あり） | 同 `/C145_Pinmap_Overview.png` |
| C145_Model_Size_page_01.png | 外形寸法図 | 同 `/C145_Model_Size_page_01.png` |
| Tab5.stl | 筐体3Dモデル（機構干渉確認用） | https://github.com/m5stack/M5_Hardware（Products/C145_Tab5/Structures） |
| Tab5_Keyboard_SCH_V1.0.pdf | Tab5用キーボード（A164）回路図 | https://m5stack-doc.oss-cn-shenzhen.aliyuncs.com/1241/SCH_Tab5_Keyboard_SCH_V1.0_20251109_2026_05_06_16_24_34.pdf |
| esp32-p4_datasheet_en.pdf | ESP32-P4 データシート v0.5 | M5Stack docs 同梱リンク |
| ES7210.PDF / INA226.pdf / IP2326.pdf / RX8130CE_cn.pdf / ST7123_SPEC_Preliminary_V0.5.pdf | Tab5搭載部品（SYS I2C上のアドレス確認等に使用） | 同 |

未取得：ES8388.pdf（M5Stack側リンク404）。必要なら Everest Semiconductor の公開データシートを別途取得。

## Tang Primer 20K（Sipeed）— `tang-primer-20k/`

取得元：https://dl.sipeed.com/shareURL/TANG/Primer_20K/

| ファイル | 内容 |
|---|---|
| SOM-3961_Schematic.pdf | Core基板回路図（1頁。SODIMMエッジ204ピンと各ネットの対応を含む） |
| core_sodimm_pinmap_raw.csv | 上記回路図の座標付きテキストから**機械抽出した**SODIMMピン対応（未検証・欠落あり）。確定表は回路図とibomで必ず目視照合すること |
| Core_3690_BOT_Assembly.pdf / Core_3690_Dimensions.pdf | Core基板の部品配置・外形寸法 |
| Core_3690_Net_Length.xlsx | Core基板の配線長 |
| Core_3690_STEP.7z → step/ | Core基板3Dモデル（STEP） |
| Footprint_20230724.7z → footprint/ | KiCadフットプリント（DDR3 SODIMM） |
| Dock_3713_Schematics.pdf / Dock_3714_Schematics.pdf | 公式Dock基板回路図（Coreの使われ方の参考。HDMI等） |

未取得：`Sipeed Tang Primer 20K Datasheet V1.0.pdf`（10MB以上のファイルは配布サイト側で認証コード入力が必要なため、手動取得をお願いします。取得先 `01_Specification`）。

### SODIMM（Core側）から読み取れた電源・バンク情報
- `+5V`：ピン4・6（Core入力）。`+3V3`：ピン22付近（Core側で生成）。
- `VCCO0&1`：ピン164・166。既定3.3V。他電圧入力時は **R5を外す**。
- `VCCO7`：ピン170・174。既定3.3V。他電圧入力時は **R9を外す**。
- DONE(C13・ピン136)/READY(A13・ピン98)/RECONFIG(B10・ピン96)、JTAG TDI(A6・ピン153)がSODIMMに出ている。TCK/TMS/TDOの引き出し有無は未確認。
