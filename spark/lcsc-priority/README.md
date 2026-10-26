# Sparkフル機能版：LCSC優先改訂

2026-10-26。125×78mm、HDMI・USB PD12V・バレル12Vを維持する。元設計、A/B/C、直前の秋月版は変更しない。このフォルダーが新しい調達・設計候補。製造承認・Spark応募・購入は未実施。

## 調達と実装

| 参照 | LCSC選定 | 変更 |
| --- | --- | --- |
| J1 | XKB DC-005-5A-2.0 / C381116 | DCジャック。図面に従い端子2をX−5.9mm、端子3をX−3.0/Y4.7mmへ変更。穴は1×3.5mmの長穴。センタープラス12Vを保持 |
| J3 | BOOMELE 2.54-2*15P / C56496 | 裏面のオス2×15。切断不要。接点6mm、はんだ側3mm、樹脂2.54mm。ピン配列と穴を維持 |
| JP1 | Ckmtw B-2100S02P-A110 / C124375 | オス1×2、切断不要。別梱包ショートピンは初期未装着 |
| SW3 | XKB DS-02BLP / C692500 | FPGA停止制御。列間7.62mm・穴1.0mmの専用ランド。初期は両スイッチOFF＝FPGA電源動作 |
| JP1付属 | BOOMELE 2.54 / C5305 | LCSC単品購入、基板に装着せず別梱包 |

4部品ともJLCPCB公式部品ページでExtended、Wave Soldering、Economic and Standardの表示を確認。**103部品・45行をPCBA見積の第一候補とする。これは実装承認済み100%を意味しない。** 表面SMTと裏面J3の波はんだの工程・治具・温度・挿入方向は製造業者の確認が必要。

実装を断られた部品も、まずLCSCで単品購入して手付けする。4部品をすべて手付けにする場合の99部品用BOM/CPLも同梱する。LCSCでも適合品を調達できない場合だけ秋月へ戻す。基板上103部品には全てLCSC番号を選定済み。全品の在庫予約や実装承認はしていない。Tab5とCoreは従来どおりユーザー購入。

- 全基板部品：[lcsc-all-board-parts.csv](lcsc-all-board-parts.csv)
- 手付け時の必要数・最小購入数：[lcsc-manual-fallback-purchase.csv](lcsc-manual-fallback-purchase.csv)
- 新規5品の在庫・価格・出典：[sources/selected-parts.json](sources/selected-parts.json)
- 発注レビュー用：[design/manufacturing/spark-lcsc-review-2026-10-26](design/manufacturing/spark-lcsc-review-2026-10-26)
- EasyEDAネイティブ：[design/easyeda/spark-lcsc-priority-review.epro2](design/easyeda/spark-lcsc-priority-review.epro2)

最小購入数は2台の必要数より多い。全4部品を手付けしショートピンも購入する場合、確認時点の部品代合計は約US$5.54（送料・税別）。PCBAで装着する部品を重複購入しない。LCSC単品購入へのSpark補助は通常支援として確認できていないため、自己負担で予算化する。

## 設計・検証の順序

**KiCadで設計 → KiCad付属NGspiceで解析 → EasyEDA Proへ移植 → EasyEDA内の公式NGspice WASMで同じ条件を再計算して照合**を維持する。製造用回路図全体へSPICEモデルを自動付与したものではなく、実配線から抽出した通信・電源の解析等価回路を両環境で実行する。HDMIの4ポート近似解析は外部解析の範囲であり、EasyEDAのSPICE再計算とは区別する。

最終結果・適用範囲は `validation-summary.json` を参照。シミュレーションに合格したことを実機動作・高速通信・HDMI認証・熱検証済みとは扱わない。初期1MHz、setup/hold250ns、DIR deadtime500ns、弱ドライブ/SLOWの制約を維持する。

## 組立上の確認点

1. DCジャックのセンタープラス、接地・スイッチ接点、実際の電源プラグ嵌合を確認する。新ジャックの中央ピン公称2.0mm・開口6.2mm表記を、旧MJ-179PHの5.5×2.1mm表記と同一寸法とみなさない。5Aは部品単体の定格で、基板や電源全体の許容電流ではない。入力は安定化12V専用のまま。
2. SW3はメーカー図面が対向端子を1–3/2–4と示す一方、このCADでは標準DIPのローカル番号1–4/2–3を使う。**同じ物理列の第1接点をBUCK_EN–GNDへ接続する。** 端子番号だけで別の接点へ置換しない。閉じるとFPGA停止、開くと動作。これは負荷電流を切るスイッチではない。
3. J3は裏面から実装し、ユーザー確認済み鏡像配列を保持する。Tab5と実物で嵌合高さ・端子長を確認する。3mmのはんだ側端子が表面側の部品・Core・カバーへ干渉しないことも確認する。
4. JP1ショートピンは別梱包。初回通電は未装着。USB-C、Coreソケット、HDMIは業者実装を維持する。
5. カバーは以前の概念案をそのまま製造しない。DCジャック外形、SW3高さ5.5mm、ボタン・ヘッダー・スペーサの実物適合を反映する。

未解決：EasyEDA回路図13警告の個別分類、製造プレビュー/DFM/在庫、実物嵌合と筐体、KiCad移植工程のSpark応募資格確認。登録だけで開発費が自動支給される前提にはしない。

## 関連用途との整合

作業開始時にLinux `c1cd5e47f9f07a164bc070b8defe36bb05682c6b` のREADME、DEVELOPMENT_GOALS、DTS、tools/fpga-link/transport.py、GPU `3b1ace3d91c6305ec0e32378f8819fce208c2aa7` のREADME、Project_B、board_profile、link_bus_wrapper、研究側 `e4aa69d09b2643d6f62fe686ef0f3284b109c541` のREADMEとProject_Aを照合した。

GPIO・通信配線・電源回路の機能は変更しないため、両用途の共通ハード仕様・ソフトウェアへの反映は不要。Linuxの物理PARLIO/DMAドライバ、GPUの物理FPGA通信・DDR3は未検証。LinuxとGPUは別ソフト・別ビットストリーム。DDR3は透過的なLinuxメインRAM増設ではない。
