# Spark片面SMT改訂 r4

2026-10-26。両面SMTを廃止。表面移設の試行では特に廉価版で新しい電源配線が成立せず、ユーザーが許可した代替として主電源スイッチを省略した。
この判断は物理的な不可能性の証明ではない。再設計でスイッチを復活させることは将来の別改訂。
フル125×78mm・廉価版A99×78mm、4層、HDMI・USB PDは維持。
旧FPGA停止SW3も除去。J3はC56496をLCSC別購入・手はんだ。

両版とも設計側PCB DRC違反0/未接続0、ERC0、表面以外の搭載SMT0。通信・電源32項目適合。回路図ピン照合Full480/Lite484。
BOM/CPL集合一致：Full101点/43行、Lite103点/43行。J3はBOMとCPLの両方から除外。
J1とJP1のTHT実装工程、部品受理・回転は業者確認。片面SMTであっても、全品がEconomic PCBAで受理されるとは断言しない。

EasyEDA API実行は2026-10-26に“No EDA window connected”で停止した。r4のネイティブ移植・同側再計算・Spark公開更新は未完了。
過去版の検証結果をr4の新しいEasyEDA実行結果として掲載しない。ローカル見積もり候補のみで製造未リリース。
元設計、r2/r3、top-placement-trialフォルダーは保存し現行とは区別する。

## 要求照合

- tab5-linux-fpga c1cd5e47f9f07a164bc070b8defe36bb05682c6b：README、DEVELOPMENT_GOALS、easystick-stamp-p4.dts、tools/fpga-link/transport.pyを確認。物理リンク/DMAは未実装・未検証。
- tab5-fpga-gpu 3b1ace3d91c6305ec0e32378f8819fce208c2aa7：README、Project_B、board_profile.h、link_bus_wrapper.vを確認。BOARD_PROFILE_VERIFIED=0、FPGAバックエンドは未実装。
- esp32p4-linux-fpga-memory e4aa69d09b2643d6f62fe686ef0f3284b109c541：README、Project_A計画を照合。DDR3は明示的データ領域であり透過的Linux RAM増設ではない。

ピン・通信・5V/12V分配に機能変更なし。両用途の共通基板としての設計上の適合を維持するが、物理接続の実証ではない。別ソフト・別ビットストリームで使用。
関連ソフト実装の変更は不要。関連仕様コピーへの今回の電源・実装方針反映は未実施で、このリポジトリを正とする。
