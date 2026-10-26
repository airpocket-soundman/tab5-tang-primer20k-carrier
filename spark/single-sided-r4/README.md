# Spark片面SMT改訂 r4

2026-10-26。両面SMTを廃止。表面移設の試行では特に廉価版で新しい電源配線が成立せず、ユーザーが許可した代替として主電源スイッチを省略した。
この判断は物理的な不可能性の証明ではない。再設計でスイッチを復活させることは将来の別改訂。
フル125×78mm・廉価版A99×78mm、4層、HDMI・USB PDは維持。
旧FPGA停止SW3も除去。J3はC56496をLCSC別購入・手はんだ。

両版とも設計側PCB DRC違反0/未接続0、ERCエラー0（警告Full163件／Lite164件：ライブラリシンボル不一致160／161件＋孤立ピンラベル各3件）、表面以外の搭載SMT0。通信・電源32項目適合。回路図ピン照合Full480/Lite484。
BOM/CPL集合一致：Full101点/43行、Lite103点/43行。J3はBOMとCPLの両方から除外。
J1とJP1のTHT実装工程、部品受理・回転は業者確認。片面SMTであっても、全品がEconomic PCBAで受理されるとは断言しない。

再接続前はEasyEDA API実行が“No EDA window connected”で停止していた。現在は再接続後のネイティブ移植・同側再計算・Spark公開更新を完了している。
過去版の検証結果をr4の新しいEasyEDA実行結果として掲載しない。PoC用の発注データを整備。発注・支払いは未実施。通常の業者受理・実装プレビューは注文時に確認する。
元設計、r2/r3、top-placement-trialフォルダーは保存し現行とは区別する。

## 要求照合

- tab5-linux-fpga c8d4b5689735ae9fc5c1401a9699c49ab2343a04：README、DEVELOPMENT_GOALS、easystick-stamp-p4.dts、tools/fpga-link/transport.pyを確認。物理リンク/DMAは未実装・未検証。
- tab5-fpga-gpu 3b1ace3d91c6305ec0e32378f8819fce208c2aa7：README、Project_B、board_profile.h、link_bus_wrapper.vを確認。BOARD_PROFILE_VERIFIED=0、FPGAバックエンドは未実装。
- esp32p4-linux-fpga-memory e4aa69d09b2643d6f62fe686ef0f3284b109c541：README、Project_A計画を照合。DDR3は明示的データ領域であり透過的Linux RAM増設ではない。

ピン・通信・5V/12V分配に機能変更なし。両用途の共通基板としての設計上の適合を維持するが、物理接続の実証ではない。別ソフト・別ビットストリームで使用。
関連ソフト実装の変更は不要。関連仕様コピーへの今回の電源・実装方針反映は未実施で、このリポジトリを正とする。

## 最終ネイティブ検証

EasyEDA内の実計算はFull207/Lite221件完走。Full電源6/6、Lite18/20（2感度条件は範囲外）、HDMI各35/35。通信の高速エッジは送信側範囲外条件を含み、初期1MHz・弱駆動/SLOWを維持。
両版ネイティブPCB DRC0、回路図fatal0/warn13。117部品と全接続ピン・配線照合一致。
U2の銅箔専用パッドに移植時の不要マスク/ペースト開口があったため、正確なネイティブPAD定義を用いて抑止しAPIから再インポート。PAD APIでの穴単位変換を避け、実Gerberで表面開口8.06mm²・裏面ペースト0、全PTH/NPTHの位置・径・長穴一致を確認。
解析実行プロジェクトUUIDと最終ネイティブUUIDはfinalization.jsonへ記録。最終ネイティブの変更は非電気的な開口のみ。別途、内層銅厚を製造条件15.2µmに合わせて電源モデルを更新し、Full6/Lite20条件を再実行した。

公開確認済み： https://airpocket-soundman.github.io/tab5-fpga-carrier-spark/ 。実サイトのHTML/JS/データ/HDMI図、および固定コミットのFull/Liteネイティブ・BOM・CPLをハッシュ照合済み。

## 発注データ最終化

13警告は両版とも原文ログを取得し全件分類済み。予約信号3、同じ名前の重複ネット2、カスタム部品属性4群、未使用J4ピン94本4群。詳細は各design/easyeda/schematic-warning-review.json。ルール抑止や部品の自動置換はしていない。

CPLは公式LCSCライブラリのピン番号・角度・原点を照合して補正した。J4等の原点差と角度差を修正し、推奨ランド長差による最小二乗位置の偏りは部品中心の移動に使わない。物理配線は変更せず、再出力時にもfinalize_placement.pyを適用する。

製造はJLC04161H-7628、4層1.6mm、外層35µm・内層15.2µm。各order-profile.jsonとASSEMBLY.mdを注文条件として用いる。J3 C56496はPCBA対象外。供給在庫の数量予約、業者のDFM・実装受理、実機の通信・映像・熱・嵌合検証は未実施。
