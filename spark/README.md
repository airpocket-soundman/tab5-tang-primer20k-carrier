# Spark応募準備：Tab5 FPGAキャリア

> **現行候補は片面SMT・SW3省略r4：** [single-sided-r4/README.md](single-sided-r4/README.md)。J3はLCSC別購入・手はんだ。以下の旧版記録とは混用しない。EasyEDA反映・同側再計算はAPI再接続待ち。

> **改訂前候補：2026-10-26 LCSC優先改訂** — [lcsc-priority/README.md](lcsc-priority/README.md)。手付け予定4品もLCSC/JLC候補へ変更し、103部品PCBAを優先する。[廉価版A LCSC改訂](lcsc-lite-a/README.md)も追加。公開用は別リポジトリtab5-fpga-carrier-spark。以下と従来ZIPは直前の秋月版の記録。


更新：2026-10-26。海外向け **EasyEDA Spark 2026** 用の独立案。従来125×78mm版、廉価版A/B/Cとその発注計画は保持する。

## 方針

- Tab5とTang Primer 20K Coreモジュールはユーザー購入・支援申請対象外。J4はCoreを受ける204端子ソケットで、モジュール本体ではない。
- キャリアは125×78mm・4層・6取付穴。USB PD12Vとバレル12Vの両入力、独立Core5V、HDMIを保持。100mm特価に合わせた縮小は行わない。
- ソケット、USB-C、HDMI（シェル固定端子を含む）、SMD回路、操作ボタンをPCBA優先。THTもStandard等の対応工程で実装可能か見積もる。
- 調達はLCSC優先、LCSCで購入できない部品は秋月電子に集約する。他社通販を例外として追加せず、秋月にも適合品がない場合は代替設計を検討する。Tab5とCoreはユーザー購入枠。
- 応募単位は基板単体ではなく、Tab5・Core・キャリア・保護筐体・実演ソフトを組み合わせた完成システム。最小実演は双方向通信、DDR3書込み/読戻しCRC、1つの演算オフロード。LinuxとGPUは別ソフト・別ビットストリームで使う。
- 製作支援と受賞賞金を区別する。先に完成設計と未払い見積を用意し、材料申請の承認・クーポン発行後に発注する。

## 資料

- [海外版の応募・支援調査](application/ENTRY_RESEARCH_JA.md)
- [英語プロジェクト提案](application/PROJECT_PROPOSAL_EN.md)
- [主催者への確認事項・英文下書き](application/ORGANIZER_QUESTIONS_EN.md)（未送信）
- [設計仕様と要求元の照合](design/DESIGN_SPEC.md)
- [実装・調達方針](design/ASSEMBLY_PLAN.md)
- [開発・検証の現在地](design/VERIFICATION_STATUS.md)
- [実装・手付け・初回通電の指示](design/ASSEMBLY_INSTRUCTIONS.md)
- [EasyEDA API内でのシミュレーション再実行](simulation/easyeda-wasm/README.md)（公式NGspice46 WASM、実計算と従来結果の照合）
- [秋月まとめ買い候補表](design/akizuki-purchase-plan.csv)（2台分。実物適合・在庫確認後に発注）
- `design/kicad/`：独立した125×78mmの工学検討用KiCad設計。応募用EasyEDAネイティブ設計とは区別する。
- `sources/preserved-design-hashes.json`：従来設計の保全確認用ハッシュ。
- `design/easyeda/spark-akizuki-migration-review.epro2`：回路図と基板を関連付けた移植確認版。旧名の中間epro2は使用しない。応募資格・業者DFM承認とは区別する。

## 応募適合性の保留

**KiCadデータはそのまま応募できない。** 海外FAQはEasyEDA Proでの設計を必須とし、公式スタッフは100%同ソフトでの設計と回答。KiCadのインポート後修正で条件を満たすかは確認できていない。工学設計と部品表を参照してEasyEDAで応募用データを作成・検証し、作成経緯を正直に記録する。

未製造・未実機検証。筐体現物適合、PCBAプレビュー、部品在庫、応募者の国籍/年齢/配送地域、設計ソフト条件、個別支援承認は残件。エントリー、材料申請、問い合わせ送信、注文支払いはまだ実行していない。

## 支援予算

公式資料の標準はPCB5枚・PCBA2枚。過去の5枚実装見積151.98ドルは本案の正式見積ではないため転用しない。対象見積額をE、自己購入・非対象分をX、税をTとし、概算自己負担は `0.2×E + X + T`。80%は承認済みの補助率ではなく公式の目安。現時点の確定支援額は0。

LCSC単品購入は支援見込みに算入しない。2026年3月・6月の公式回答は、JLCPCBクーポンによる支援とLCSCポイント交換を区別している。
