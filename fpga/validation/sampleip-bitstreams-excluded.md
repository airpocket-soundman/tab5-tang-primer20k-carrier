# 旧IP（Sipeedサンプル）を含むビットストリームをmainから除外（2026-11-05）

`mem-variant-sampleip*-2026-11-04/mem_bist.fs.gz`（6本）は、Gowin製の暗号化DDR3 IP（Sipeed公開サンプル `e469df4c` の旧IP）を内包するビットストリームで、**再配布条件が未確認**のため、mainからは除外した。ビルド記録（JSON、STA、SHA-256、USERCODE）は残してある。

- 再現：`docs/DDR3_旧IP保管と再現手順_2026-11-04.md`（固定コミット＋SHA検証付きの取得、`fpga/tools/fetch_sipeed_ddr_ip.py`、`build_variants.ps1`）。
- 実機で使った版は、記録のSHA-256で照合できる（例：`sampleip_map_t4` の FS `39ff4409…`、USERCODE 0x0233）。
- ライセンスを確認し、問題がなければ、各ブランチ（`claude/track-p2-ddr3-variants`）の履歴から復元できる。
