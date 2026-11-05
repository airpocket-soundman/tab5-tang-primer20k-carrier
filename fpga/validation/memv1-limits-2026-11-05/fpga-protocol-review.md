# A0A9／MEMV1の周波数・プロトコル限界調査（2026-11-05）

読取り専用の設計調査。実装・FPGA・ファーム・配線・実機設定は変更していない。現在のA0A9・同速TX/RXの実証点は8MHz・対象条件の20000要求PASS。別FPGA D7F5では、過去にTX2MHz／RX20MHzの非対称条件も反復PASSしている（次節）。10MHzは最初のWRでFORMAT応答となり不合格。以下の式から計算する値は、実測帯域や今後の認定周波数ではない。

## 対象版と再現用参照

FPGA作業ツリー：`D:/github/airpocket-soundman/tab5-carrier-memv1-fastreply`。実FSを読んでSHA-256 `46dbb0b99e3b2d79660d6c9c6ac5226dd0c4a84bb937531317aaa04c06e7a114`、PNR記録`fpga/validation/memv1-fastreply-pnr-2026-11-05.json`のUSERCODE A0A9と一致確認した。FS／ベンダーIPは本ノートへ複製していない。生成済みRTL・SDCを対象とし、主なローカルSHAは末尾に記す。

実機結果の根拠は親の`fpga/validation/memv1-tx-reuse-2026-11-05/restore-8mhz-wrrd10000.json`、`pilot-restore-10mhz-wrrd10.json`等。ホストの最適化で結果・帯域が変わっても、FPGA A0A9のPHY自体が変更されたことにはならない。

## 過去のRX20MHz到達点と現在条件の区別

D7F5 phase3＋ホストELF `0195a00bd1ef4ab4f667e6f4b155eaaeba4dabffc07e57b0d10a88ffa20471d6`では、TX2MHz positive／RX20MHz positiveの`phase3-rx20-100.json`が202段階・617フレームPASS。これは実測済みの受信20MHz到達点であり、現在のA0A9・TX8/RX8MHzだけが過去の最高RX条件という意味ではない。同一旧ホストでA0A9へ戻した`baseline-rx20-control-100.json`はSTATUS段階でFAIL（完了1段階）しており、D7F5とA0A9を同じPHY条件として扱えない。

D7F5の返信phase変更はRX側の有効窓を変える別bitstream。過去の20MHz PASSはTX2MHz・旧ホスト・当時の配線等を含む一組の条件である。最新TX8MHz negative＋preamble1とD7F5のRX20MHz positiveを再結合する候補は**未検証**で、過去と現在の成功を足して認定済みとしない。ファームの準備・DMA再利用・GPIO復元経路も変わっているため、FPGA版・ELF・設定を固定して読取りから再評価する必要がある。

実効8MB/sという目標は、WRとRDの方向別に評価する。読取りではTX要求が19clock程度と短く、既知のRX20MHzを使う研究の優先性がある。一方、WRの4KiB payloadは主にTX側へ流れるため、RX20MHz化だけで書込み実効8MB/sへ近づくとはいえず、27MHz SYS request samplerの制約とTX有効窓を別に扱う。

参考としてTX8MHz／RX20MHzで公称RD4096だけを読むなら、request19/8MHz＋capture4122/20MHz=208.475µs、payload換算約19.6474MB/sがwireのみのモデルになる。これは未検証組合せの理想値で、準備・DDR・待機・検証等を含まない。逆のWRはrequest4115/8MHz＋ACK24/20MHz=515.575µs、約7.9445MB/sのwire上限モデルで、固定費を足すと8MB/sを下回る。現在のWR＋RD合計job_MBpsと、方向別8MB/sを同じ指標にしない。

## 現在の配線・クロック・制約

CSTはCLK=T7（GCLKT_3）、DIR=N8、READY=L9、D0..D7=T12/T11/P11/R11/M15/M14/J16/J14。LVCMOS33、DATA/READY drive8mA。8本のDATAは複数bankに分かれる。単一CLK・DIRで向きを切り替える8bit半二重リンクで、READYはFPGAが駆動する。ジャンパの遅延・立上り・skew・負荷・反射はCSTだけでは定まらない。

SYSは27MHz（SDC周期37.037037ns）、DDR memory clock398.25MHz、user clock99.5625MHz。応答専用samplerは216MHz。SDCのconditioned_reply周期18.518519ns（54MHz相当）は内部STAモデルで、54MHzの外部GPIO通信を認定した値ではない。ソースの実filterは下記の43.2MHz間隔制限も持つ。

現SDCにはCDCの初段pin例外・held bundle最大遅延等があるが、外部Tab5からDATA/CLKへ来るboard-levelのset_input_delayや、Tab5へ出るDATAのset_output_delayによる完全な外部I/O契約はない。PNR内部setup/hold違反0と、ジャンパ経由で外部setup/holdが満足することは別である。

## TX：27MHz非同期strobe受信が先に制限する

memv1_sysはbus_clkを3bit clk_syncへ入れ、clk_sync[1]と[2]の差でriseを検出する。そのriseをSYSのalwaysで処理する際に、DATAのdata_iを直接読んでheader／payloadへ取り込む。DATAをbus_clkの元のエッジで一緒に取り込むsource-synchronous入力FFではない。

名目上、raw CLKの立上りから実際のDATA採取までの遅延は2〜3 SYS周期、約74.074〜111.111nsとなる（メタステビリティ・ピン／配線遅延等を除く論理モデル）。TX negative＋preamble1で一つのbyte区間のずれを吸収できても、SYSとの位相により採取点が次byteへ跨がる問題までは解消しない。

物理位相の根拠は`slogic-8mhz-caps/short-caps-analysis.json`で、TXの共通9バイト完全一致位相はphysical rising−20／−10ns。これはその時刻にプローブで見えた値であり、SYSが採ったbyte番号やP4のdata更新時刻を直接示すものではない。preamble1と最終CRC保持2µsを含めた一組の条件で8MHzを確認している。遅延採取が一つ先のbyteを見ることを先頭zeroで補償している可能性もあり、「raw riseで表示されるbyteがそのまま74〜111ns後に採取される」と決めつけない。以下の余裕計算はbyte区間とdata更新の仮定に依存する設計モデルで、観測setup/hold値でも、8MHzの保証marginでもない。

DATAがraw立上り付近で切り替わり、次の立上りまで保持されると仮定すると、そのbyte区間モデルでnominal最悪3 SYS周期を1byte周期内へ収める条件はf_bus≲27/3=9MHz。8MHzの125ns周期では約13.889ns残るが、10MHzの100ns周期は約11.111ns不足し得る。これは8MHz成功／10MHz FORMATと整合する制限候補であって、失敗原因の最終確定ではない。実際のデータlaunch位相、同期器の解決時間、IO遅延・skew・jitterを含めた保証値ではない。

50%dutyのhigh/lowを27MHzサンプルで見落とさないための単純な周波数条件はf_bus<13.5MHz程度だが、それだけでは遅延後に同じbyteを読めることを保証しない。クロックedgeが検出できる限界と、byte境界に対するDATA採取の限界を混同しない。

ESP32-P4の160MHz PLLから8MHzは整数20分周、10MHzは16分周で生成できる。分周値が整数で正しく読戻せても、Tang側27MHz発振器と位相同期したことにはならない。理想値でも8MHzでは8byte周期／27SYS周期、10MHzでは10byte周期／27SYS周期で位相関係を巡回し、両発振器の差でも動く。

参考候補160/19≒8.421MHzの名目余裕は約7.639ns、160/18≒8.889MHzでは約1.389nsしかない。現在のジャンパ／同じstrobe方式でこれらを安全な次段階として推薦できる根拠はない。10MHz以上を狙う本筋は、専用のsource-synchronous入力FF＋CDC FIFO、または十分速い専用request samplerへ作り替え、DATAを一緒に保持することである。SYS全体を27→54MHzへ変えるだけの案は、既存CDC・timeout・CRC経路等の再設計／STAが必要で、無検証のclock変更ではない。

## RX：216MHzフィルタと出力窓

reply_clock_filterはraw CLKを2段同期し、2回一致を確認してclean clockを生成する。名目raw rise→clean riseは216MHzの3〜4tick、約13.889〜18.519ns。これにserializerのclock-to-Q・routing・出力pad・ジャンパ・Tab5入力側の遅延が加わる。host側の論理positive/negativeという名前を、そのまま観測したピン上の取得位相や内部取得点と同一視しない。

filterは出力後cooldown=4を入れ、最短の次rise間隔は5tick=23.148ns、論理上の上限43.2MHz。raw high/lowの2sample一致条件もあり、短パルスのアナログ除去幅を保証する回路ではない。43.2MHzはfilterロジックの間隔上限で、外部DATAの有効窓・Tab5能力・配線を合わせた通信保証ではない。

A0A9はold DATAをraw rise付近で取得した後に、conditioned riseで次byteへ進める設計。高周波化で有効窓が狭まり、DDR read buffer先読み・CRC・READYの返りも含めて確認が必要になる。応答専用のD7F5 phase3試験結果はA0A9へ混ぜない。現在のTX=RX8MHzではTX側SYS受信制約も同時に存在する。

## 4KiB WR＋RDの公称wire下限

1clockで1byteを運ぶ、preamble1／tagged prefix8／capture margin16の現在条件。

| 処理 | TX request clocks | RX DMA capture clocks | 小計 |
|---|---:|---:|---:|
| WR4096 | 4114+1=4115 | ACK body8+margin16=24 | 4139 |
| RD4096 | 18+1=19 | RD body4106+margin16=4122 | 4141 |
| WR＋RD1組 | 4134 | 4146 | **8280** |

各margin16はprefix8＋追加slack8。両方向の有効payloadは4096×2=8192B、効率8192/8280=98.9372%。8MHz raw8MB/sに対し、公称capture clockだけの理想帯域は約7.9150MB/s（1組1035µs）。5MHzなら4.9469MB/s、10MHzなら9.8937MB/sだが、10MHzは実機不合格である。

guardを3回×2µs×2要求の12µsだけ追加した上限目安は8192/(1035+12)≒7.8243MB/s。さらに現在の固定turnaround待ち2+2µs／要求とTX末尾保持・解放待ち各2µs／要求も含めると、計28µsの明示待機を足した約7.7065MB/sが目安となる。ただし、これもDMA設定・GPIO操作・割込み／タスク起床・FPGA DDR完了待ち・検証等を除いた下限時間のモデルで、実測値ではない。

**8280は公称DMA capture budgetであり、ピンの全CLK立上り実数ではない。** RXではfree-clockがEOF後、ソフトウェアが止めるまで継続することがあり、原SLogicには余分なtail clocksが残る。これを削除／修復して理想値へ合わせない。短いACKでは特に、この起床・停止費用の方が数十byteのheaderより大きい場合がある。

追加slackだけを両応答から8ずつ取り除いても16/8280≒0.193%のclock削減。tagged prefixも含め32clock減らしても約0.386%。4KiBでは全88clock overheadそのものが約1.063%なので、header削減だけで現実の数MB/sを8MB/s近傍へ倍増することはない。大きい差は準備・停止・起床・検証等と、その重なりを調べる必要がある。

## DDR内部とblockサイズ

物理DDR3 x16、398.25MHz DDRの理論値は398.25MHz×2edge×2B=1.593GB/s、128bit user interface99.5625MHz×16Bも同じ。mainへ記録されたstandalone burstの約1.48GB/sはDDR内部の別実装・別測定で、MEMV1 LINKの到達値ではない。

A0A9のmem_v1_topはapp_burst_number=0、native BL8を1個の128bit／16B user beatに対応させる。mem_adapterは最大256beat、読取りpending1件で、各read validを待ってstageへ保存し次へ進む。standalone長burstと同じ多重発行・連続帯域を自動的に使う構造ではない。SYSとUSERのheld bundle handshake、4KiB write staging／read buffer、返信準備までが別の遅延になる。

blockを8KiBにするだけのwire効率向上は2P/(2P+88)から約0.53%程度に留まる。本当の狙いは要求ごとのCPU/DMA/GPIO固定費を減らすことである。現仕様は256beat／4KiB上限で、8bit RAM address・buffer・フレーム長／カウンタ・ホストのMAX_REQUEST/MAX_CAPTURE・DMA descriptor span等を一緒に変える必要がある。先の短EOF／複数descriptor退行もあり、長さだけを増やして認定しない。全ホストOSのABI適合とCAPSの上限値・仕様版を確認する作業になる。

## 当面の計画：8MHz基準の実効改善を優先

今回のユーザー方針は、直ちに40MHzで運用することではなく、確認済み8MHzで準備・解放・cache・pack・試験検証費を詰め、実効を上げること。8MHzでの同一FW・同一要求列の累積A/Bを先に行う。上記の高周波・新配線案は将来設計の予測であり、現在の運用条件へ自動適用しない。

現在の8MHzはNEG位相・preamble1・CRC末尾保持・配線を含む実験条件の認定で、IOの正式な外部setup/hold契約から導いた保証ではない。配線変更や位相変更後は原波形を保持して再確認する。10MHz FORMATは失敗として残すが、27MHz delayed samplingだけを確定原因として修正しない。

将来PHYを変更するなら、bus_clk専用入力FFへDATAを同時に取り込み、byte順序を保持するCDC FIFOでSYSへ渡すsource-synchronous方式を第一候補にする。入力FFの取得edge／IODELAY、DATAとCLKの外部input delay、FIFO深さ・CRC処理能力・abort/reset所有権を明示し、方向切替と最初／最後のbyteも検証する。既存のpreamble補償に依存した遅延サンプリングと区別する。現8MHzの全試験を退行対照にしてから、必要になった場合に次周波数を検証する。

## 別配線／full-duplex案の位置付け

8bit TXと8bit RXを別配線・別clockへ分ければ、理想的には各8MB/sを同時に運び合計16MB/sとなり得る。しかし現在のDATA8本共有＋単一CLK/DIRのままではfull-duplexにならない。追加DATA8本以上とclock／制御のpin・電気条件の設計が必要で、現在未使用AUX4本だけでは足りない。

さらに、現MEMV1は要求→完了→応答と単一buffer所有権で直列化しており、同一addressのWR後RDには依存関係がある。別線だけで2倍になるわけではなく、複数outstanding／credit／bufferと、新しいプロトコル・FPGA・全ホストへの反映が必要。半周期両edgeを使うDDR並列リンクも現在のrise-only PHY／P4設定とは別設計であり、既存の16bit DMA packを8bit DDR転送と解釈しない。

## 公式FPGA IO資料の適用範囲

ローカル`docs/reference/gowin/DS102E_GW2A.pdf`（DS102-2.7.8E）の表3-18／19（印刷37頁、PDF47頁）はGW2A-18 C8/I7・LVCMOS33・8mA・15pFでPin-LUT-Pin最大3.83ns、HCLK0.82ns、GCLK1.77ns、および専用GCLK経由GPIO入力registerのsetup/holdを示す。この専用IO-register条件を、現在のSYS27同期strobe＋DATA直読へそのまま代入しない。表3-21のPLL入力500MHz／出力625MHzもPLL回路の条件で、ジャンパGPIOプロトコルの上限ではない。

一次資料：[Gowin DS102公式PDF](https://cdn.gowinsemi.com.cn/DS102E.pdf)、[Gowin UG289 GPIO公式PDF](https://cdn.gowinsemi.com.cn/UG289E.pdf)、[公式文書一覧](https://gowinsemi.com/en/document/main/database/1/?order=ASC&page=2&support_search=&type=category)。公式CDN検索結果の版はローカル固定版と異なる場合があるため、数値と頁は上記ローカル2.7.8Eを根拠にした。専用SERDES・LVDS等の高速値は現在のLVCMOS33 SDR並列へ流用しない。資料だけから、現在のジャンパ配線での汎用最大MHzは確定できない。

## 主なソースSHA（読取り時）

- `fpga/build/memv1-fast/rtl/memv1_sys.v` SHA-256 `4c1b4f043a411c1ac9a8958d94346e0454415dd7f087dca3044f48cab27c4a95`
- `fpga/build/memv1-fast/rtl/reply_clock_filter.v` SHA-256 `dd9d4f92f6dbeb0b3d8601ab77ac94aab86f410753112a9fa6dde529e6575cb1`
- `fpga/build/memv1-fast/rtl/memv1_reply_raw.v` SHA-256 `0319dc6cd81bc4d77546fb0e96ae93478a691439740c7df5334a4fa16761f609`
- `fpga/build/memv1-fast/rtl/mem_v1_top.v` SHA-256 `bdb12e0b48059ca9f687074e0f30908c3250502aee6f5653c2a9d3d8170bc825`
- `fpga/build/memv1-fast/rtl/mem_adapter.v` SHA-256 `5e11f425b6199a7311e5b654e8d975b80e8826f71411f016596c052f271e7a96`
- `fpga/build/memv1-fast/mem_v1.sdc` SHA-256 `30940b761a17e5e2c5d048d35eb366ba8ee26dcadfd5aef64a94d8db67a8a25c`
- `fpga/mem/config/mem_bist.cst` SHA-256 `30ad69d4444572557d1b6e5b4d24261945c965694876f50c1d71eb2c676e4916`
