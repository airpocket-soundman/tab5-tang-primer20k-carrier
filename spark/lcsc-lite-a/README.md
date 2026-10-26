# Spark廉価版A：LCSC優先

2026-10-26。元のlite-a-dualを別フォルダーへ複製した独立99×78mm改訂。HDMI・USB PD12V・バレル12Vを維持。従来設計とA/B/Cは変更しない。

J1 C381116、J3 C56496、JP1 C124375、SW3 C692500へ変更。SW1/SW2はBasic/SMTのC318884、高さ1.5mm。推奨ランドを90度回転してA/B接点をCAD左の1、C/Dを右の2に対応。メーカー実装プレビューで接点群・回転を確認する。ボタンの局所配線変更と不要になったTAB_RSTの片面ビア/1mmスタブ削除を行い、再ロードしてGNDを生成。タイミング対象のパラレルとHDMI配線は維持。

KiCad設計・全severity DRC0/未配線0・ERCエラー0・486接続端子の回路図一致・通信/電源32項目・HDMI導通確認後、KiCad付属NGspiceで21電源+150通信+16周期を計算。EasyEDAへ移植して同じ187条件を公式NGspice46 WASMで再計算し、全判定一致を確認。HDMI4ポート近似は外部解析のみ。validation-summary.jsonに結果を記録。

EasyEDAネイティブはdesign/easyeda/spark-lite-a-lcsc-review.epro2。全118部品・486接続端子のネット/値、PCBの端子・配線・ビアを照合。PCB DRC0、SCH致命的エラー0/警告13。新規4フットプリントの銅箔/穴寸法はnative-land-audit.jsonで一致。

電源19/21が数値範囲内。50mA急変/遅いループの2感度試験は3.3V±5%を外れる。通常局所3.3Vは10mA以下・外部給電なし。通信は受信150/150・送信60/150。初期1MHz・弱ドライブ/SLOW・setup/hold250ns・DIR待ち500nsを保持。実機DMA/DDR3/GPU/HDMI認証/熱は未検証。

PCBA見積第一候補105部品/45行。手付けになった部品もLCSC優先、適合品がない場合だけ秋月。Core/USB-C/HDMIは業者実装必須。C5305は別梱包・初期未装着。筐体、嵌合、在庫/実装プレビュー/DFM、13警告、Spark資格確認が残る。

Linux c1cd5e47f9f07a164bc070b8defe36bb05682c6b、GPU3b1ace3d91c6305ec0e32378f8819fce208c2aa7、研究e4aa69d09b2643d6f62fe686ef0f3284b109c541の要求を照合。GPIO/通信方式の変更と関連ソフトの変更は不要。物理transportとDDR3接続は未検証。用途別ソフト/ビットストリーム、透過的なRAM増設とはしない。

公開用は別リポジトリtab5-fpga-carrier-spark。指定に従いEasyEDAデータとEasyEDA実行結果のみを収録し、内部KiCad成果物・外部solver結果/比較は公開しない。
