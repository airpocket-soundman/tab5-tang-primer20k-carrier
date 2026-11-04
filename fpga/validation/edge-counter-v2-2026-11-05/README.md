# トラックJ2 診断イメージ v2／v2.1 のビルド記録（2026-11-05）

**最新は v2.1（USERCODE `0x0000A7D0`）。** v2（`0x0000D535`）は実機で「健全点で全窓が異常、deficit 659件」となったため、v2.1で完了判定を直した（`docs/CLK_edge_monitor.md` の「v2の実機結果と、v2.1での修正」）。v2の記録は下に残す。

実機未接触。Gowin Education 1.9.11.03、`builds/dock/build_filtered_edge_cdc.tcl`、ソース commit `0d89736`。**書込みはしていない。**

| 項目 | 値 |
|---|---|
| USERCODE | `0x0000D535`（v1は `0x00004ABF`、基準85bac224は `0x0000E368`） |
| FS SHA-256 | `79d143a9fac5b82835cc83af7d6de4367d503fd9b0fb075ad6935e2b681a7073`（`filtered_edge.fs.gz` を展開した値。`//Created Time` 行を含む） |
| BIN SHA-256 | `c31d34efa85685227964f4a21b3d9213c8d377275dc5a0618acd3560e0f8be83` |
| STA | 解析パス 25,471／エンドポイント 8,491、**setup違反 0、hold違反 0** |
| 最小スラック | setup **+0.048ns**（薄い）、hold +0.074ns、recovery +2.211ns、removal +1.074ns |
| Fmax | sampler216 218.261MHz（目標216）、core54 67.710MHz、conditioned_reply54 79.849MHz |

**余裕は小さい（setup +0.048ns）。** 216MHz側（`reply_edge_monitor`）のロジックを足しているため。ソースを少し変えるだけで違反が出る（下記の履歴）。再ビルドの結果が変わり得るので、書込みに使うFSはこの記録の SHA-256 と一致するものに固定すること。

## 履歴（STA違反は隠さず保存）

| 試行 | 内容 | USERCODE | setup違反／最小 | 記録 |
|---|---|---|---|---|
| 1 | 初版（14bitタイムアウトカウンタ、CEに深い論理） | `0xDCAE` | 8／−0.104ns | `edge_counter_v2_try1_sta_violation.json` |
| 2 | イベントゲートのレジスタ化、カウンタ分割（比較は未パイプライン） | `0x0284` | 17／−0.342ns | `edge_counter_v2_try2_sta_violation.json` |
| 3（採用） | 比較のパイプライン化、終了判定のレジスタ化（`last_hit`） | `0xD535` | **0／+0.048ns** | `edge_counter_v2.json` |

違反経路は毎回216MHz側（`min_h/min_l` の比較→CE、`sp_diff`→`first_pos` のCE、`vact` の次状態、14bitのタイムアウトカウンタ）。

## 注意

- 85bac224 のCDC例外SDC（`triangle54filtered_batch_cdc.sdc`、30組の例外）をそのまま再利用。`link_reply_raw.v` / `reply_clock_filter.v` / `link_bringup_filtered.v` を変更したので、ソース固定の証明（`generate_metadata_cdc_constraints.py --verify`）は**再実行していない**。例外の30組の名前は不変だが再証明ではない。
- スナップショットのSYS側への受け渡し（トグル同期＋窓終了時に確定）は、新たなCDC経路として例外SDCに入っていない。
- FS／RPT／TR／SDF は `*.gz`。FSは書込み時に展開する（展開後のSHA-256が上の値）。

## v2.1（採用版、ソース commit `a226622`）

| 項目 | 値 |
|---|---|
| USERCODE | **`0x0000A7D0`** |
| FS SHA-256 | `8be7ffb9a460e730263c4fe2e126a13ccebd1121b380d4faaf08448490545c1d`（`v2_1_filtered_edge.fs.gz` を展開した値） |
| BIN SHA-256 | `e016a969b4bd9805f104cde3b9bbd99d2118bf1f16c66c34c3e12ade57072a33` |
| STA | 解析パス 25,396／エンドポイント 8,454、**setup違反 0、hold違反 0** |
| 最小スラック | setup **+0.300ns**、hold +0.076ns、recovery +2.025ns、removal +1.209ns |
| Fmax | sampler216 230.993MHz（目標216）、core54 67.202MHz、conditioned_reply54 77.815MHz |

記録は `edge_counter_v2_1.json`、成果物は `v2_1_filtered_edge.fs.gz`／`v2_1_filtered_edge.rpt.txt.gz`／`v2_1_filtered_edge_tr_content.html.gz`。変更は主に54MHz側（完了判定・deficit・異常窓）で、216MHz側は「runtを最初の異常から外す」だけなので、v2より余裕が増えた（setup +0.048ns → +0.300ns）。CDC例外SDCは85bac224のものを再利用（再証明していない）。**書込みはしていない。**
