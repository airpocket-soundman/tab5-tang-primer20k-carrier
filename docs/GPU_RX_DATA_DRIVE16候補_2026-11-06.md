# RX DATA DRIVE16 独立候補

2026-11-06。7375（FIFO216/PIPE1/FAST1/timerON/registeredDATA1）のDATA8本だけDRIVE8→16へ変更する実験候補。既存CSTと7375 FSは維持する。ピン、LVCMOS33/3.3V、PU/PD、READY DRIVE8、OE制御は不変。共通RTLはbyte同一、topはmodule名以外同一と機械比較した。

## 公式資料で確認した範囲

同梱UG289-2.1.6E revision history PDF p3は2023-02-22版でslew-rate説明を削除したと記録。SUG935-1.4.4E p3は2023-03-31版でslew設定を非表示にしたと記録する。旧公式UG289にはFAST/SLOW構文があるが、現Education版にそのまま適用できる根拠にならない。**未指定SLEWの実既定は未確認。SLEW_RATE=FASTは採用せず、未指定を維持。**

- [現公式DS102資料一覧（2.7.8E、取得にはログインが必要）](https://www.gowinsemi.com/en/document/main/product/38/?order=ASC&page=4&support_search=&type=version)
- [旧公式UG289のFAST/SLOW説明（現版対応の証拠にはしない）](https://cdn.gowinsemi.com.cn/UG289-2.0.2_Gowin%E5%8F%AF%E7%BC%96%E7%A8%8B%E9%80%9A%E7%94%A8%E7%AE%A1%E8%84%9A%28GPIO%29%E7%94%A8%E6%88%B7%E6%8C%87%E5%8D%97.pdf)

repository公式 `docs/reference/gowin/DS102E_GW2A.pdf` はDS102-2.7.8E。表2-1（PDF p18、印刷p8）はLVCMOS33/3.3VのDRIVE4/8/12/16/24を認めており、今回確認対象8/12/16はいずれも許容選択。UG289 §3.5.3はIO_PORT DRIVE構文を説明する。現buildのpin reportでも8本すべてDRIVE16が反映されている。公式manualのpath/hash/pageと自前の所見はofficial-document-proof.jsonに記録した。

## bit別SDF構造遅延

7375とADBAは全bit同値。Q→padはFF CLK→Q（min0.201/max0.232ns）を別途分離した値。いずれも構造的極値で、負荷容量、ジャンパ線、閾値、波形を含む実測値やsensitized timingではない。

|bit|Q→pad min ns|Q→pad max ns|CLK→pad max ns|
|---|---:|---:|---:|
|0|4.227|7.106|7.338|
|1|3.509|5.942|6.174|
|2|3.277|5.568|5.800|
|3|4.038|6.743|6.975|
|4|4.407|7.567|7.799|
|5|3.852|6.446|6.678|
|6|4.620|7.859|8.091|
|7|4.832|8.238|8.470|

bit7が8bit中最大だが、7375で見られたseq B0→30のbit7欠落原因をこの表だけでは断定できない。SDF値がDRIVE変更で変わらないため、改善の有無は親担当の実機CRC/全画素比較で判断する。DRIVE16は規定試験条件の駆動強度であり、出力に常に16mAを流す設定ではない。配線負荷・反射に対する改善も悪化も未検証。

## 保存点と検証

- top `fpga/platform/dock/tab5_dock_drive16_top.v`
- CST `fpga/constraints/dock/tab5_dock_data_drive16.cst`
- build `fpga/builds/dock/build_drive16.tcl`、公式Education1.9.11.03。
- FS `fpga/build/drive16-v1/drive16/impl/pnr/drive16.fs`、UserADBA。
- SHA256 `cf54a2d23e8e3a75ad94d88cd68db93b38b37acefbfcaa84de0af39bdf614f31`。
- STA4種違反0。metadata30例外以外追加waiver0。共有reply/DPBclock、captureDATA/Gray、registered出力8FF/pad経路監査合格。
- 7375との全sharedRTL同一をSHA比較し、既存LINK42/27、control41、ROW/TILE264、serializer18の回帰証拠を再利用。
- 新mapped gate TX40/RX8の15vector（timer、実Wire5recordsと画像、最大TRI/R2/upload）合格。理想PLL/SDFなし。
- `fpga/validation/drive16-2026-11-06/candidate.zip` とmanifest。ZIP CRCと全展開byte一致を確認。

## 全ホストへの適用範囲

これはbaseline電気仕様の変更ではなく、Dockジャンパ接続GFX用の実験drive条件。ESP-IDF `67fa6728`、MeOS `78274b46`、Linux `cfc9a6ec`、メモリ研究 `e84b59e8` の前候補照合を継承する。ホスト電圧/ピン/DIR ownership/Hi-Z/guard/コマンドABIは変えないため、ホストコード反映は不要。MeOS/Linuxでの当候補の実機電気適合・高周波数動作は未検証。既存DRIVE8標準を置換しない。overflow復旧は物理ARM/resetまたはSRAMreloadであり、soft再ARMではない。実機書込と性能/波形比較は親担当。
