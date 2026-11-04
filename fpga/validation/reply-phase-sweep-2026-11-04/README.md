# トラックN 応答位相イメージ（ビルド記録、2026-11-04）

実機未接触。Gowin Education 1.9.11.03、ソース commit 742ba86、`make_phase_variant.py --ticks N`。85bac224のCDC例外SDCを再利用し、
シリアライザ／BSRAMのクロック網 `core/reply_clk` に同じ54MHz条件のクロック制約を付けた（付けないと未制約クロック扱いで偽の-13ns違反になる。初回ビルドで確認）。
FSは `*.fs.gz`（書込み時は展開）。REPLY_FINE_DLY(IODELAY)の変種は未ビルド。

| イメージ | USERCODE | FS SHA-256 | setup最小(ns) | hold最小(ns) | 違反0 |
|---|---|---|---|---|---|
| phase_t1_f0 | 0x0000B4CE | `cc3da687983c96c1e940a1a7ff8e64c36f5ea735b3ef7f6d1a6bb92d87592185` | 1.135 | 0.124 | True |
| phase_t2_f0 | 0x0000D36D | `1bf32d77a35677c29b3cf7d1552df4de42a71289a6b3c4f0e7a98086a8cd07e9` | 0.826 | 0.074 | True |
| phase_t3_f0 | 0x0000F8F5 | `7d57766cb204e017ae7c6782f4b9560be6d97a51fa0c42c7c95227ddea839a95` | 0.912 | 0.074 | True |
| phase_t4_f0 | 0x00003194 | `05c51ab257d4af24e50b52a47dc110b995ae87b6552bfcbdee9cba1059317bb8` | 0.899 | 0.074 | True |
| phase_t5_f0 | 0x0000DC80 | `5d1b468cbedb2a56742eb968a4f7ebc9b6943defd8b69eb3d6d685a789315563` | 0.715 | 0.074 | True |
| phase_t6_f0 | 0x0000E655 | `3195da49a17fa98a5bb7ce4d4838e22048fa6b9cd08b5608e2b0c347609b9d71` | 0.822 | 0.074 | True |
| phase_t7_f0 | 0x0000D075 | `ce0d452415666e64ae4b3b44d2bbc0dce779035e9987ea4fe59868d7863dbafb` | 0.698 | 0.074 | True |
| phase_t8_f0 | 0x00009428 | `d15d33dd9e17f4da1d1048d901f359f2f3e4d686cb47dc31a057454e128d4688` | 0.917 | 0.074 | True |
