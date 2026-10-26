# EasyEDAの現行成果物

使用するファイルは **spark-akizuki-migration-review.epro2**。125×78mm、HDMI/USB PD付きSpark版の工学移植・レビュー用。PCB DRC0、回路図重大エラー0/警告13。応募資格、筐体の現物適合、業者DFMは未確認。

基板の全配線・ネット照合は `electrical-migration-audit.json`、回路図の全値・接続照合は `schematic-migration-audit.json`、秋月2部品のランド照合は `manual-footprint-audit.json`。`akizuki-rules-before.json` と `akizuki-rules-aligned.json` で設計ルールの移植前後を比較できる。

**使用禁止の中間版**：`tab5-spark-engineering-review.epro2` は配線/ネット欠落、`spark-pcb-migration-review.epro2` は旧部品の基板単体。旧プロジェクト/失敗のログも原因追跡用に残すが、応募や製造データとして選ばない。

`corrected-schematic-source.txt` は変換作業用の入力で、最終ネイティブ原本は `akizuki-schematic-source.txt` と上記epro2。主資料は `../VERIFICATION_STATUS.md` を参照。
