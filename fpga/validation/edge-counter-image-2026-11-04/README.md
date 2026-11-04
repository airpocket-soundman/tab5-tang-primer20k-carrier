# トラックJ 診断イメージ（ビルド記録、2026-11-04）

実機未接触。Gowin Education 1.9.11.03 でビルド（`builds/dock/build_filtered_edge_cdc.tcl`、ソース commit cc09c6b）。
- 基準 85bac224 の再ビルドは、`//Created Time` 行以外が保存済みFSと同一（`baseline_85bac224_rebuild.json`）。ツールチェーンの再現性の確認。
- `edge_counter_j.json`: USERCODE 0x00004ABF、STA 違反0（setup最小 +0.298ns、hold最小 +0.213ns）。FSは `filtered_edge.fs.gz`（書込み時は展開）。
- 85bac224 のCDC例外SDCをそのまま再利用（`link_reply_raw.v`/`reply_clock_filter.v` を変更したためソース固定の証明は再実行していない）。例外の30組の名前は不変だが再証明ではない。
- 初回ビルド（age 22bitカウンタ）は 216MHz 側で setup -0.874ns 違反だった。カウンタ分割＋飽和フラグ登録で解消（git履歴 b425701）。
- idx19/20（excess／deficit窓カウンタ）追加後の再ビルド。以前のビルド（USERCODE 0x0ABA、0x566F）は破棄。
