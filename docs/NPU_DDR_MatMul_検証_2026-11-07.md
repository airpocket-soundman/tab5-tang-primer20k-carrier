# 既存4E21によるDDR MatMulの検証（2026-11-07）

## 実装範囲

新しいTransformer専用RTL・コマンド・ピンは追加せず、既存4E21の1×1 Convを一般MatMulとして使用する。ホスト実装は`tab5-fpga-gpu-resume-20261106/main/inference/ddr_matmul.hpp/.cpp`。標準A[M,K]、B[K,N]をpositive-stride FP32 DDR viewで受け、量子化と小さいpanel transposeをホストで行い、**全てのINT32積和を既存FPGA engineへ依頼する**。アプリ側にCPU MatMul fallbackはない。

内部の対応は次の通り。

- `Q_A[k*align16(M)+m] = quant(A[m,k])`：CHWのC=K/H=1/W=M。
- `Q_B[n*align16(K)+k] = quant(B[k,n])`：OIHWのOC=N/IC=K/KH=KW=1。
- M16、N8、K16に分割。入力原点x=M開始位置、入力base=Q_A+K開始位置*channel_pitch、重みbase=当該8列のQ_B+K開始位置。
- Kの最初をfirst、最後をfinalとしてprivate INT32を継続する。最終INT32をDDRの所有済み512byte tileに書く。
- `float(sum)*(A_scale*B_scale[n])*alpha`でFP32に戻す。Aはbatchごとのmax-abs、Bは列ごとのmax-abs、符号付きINT8/zero-point0/half-away-from-zero。bias・softmax等はこの演算器の外。

MatrixViewのrow_stride/column_strideにより、feature-major activation、OI静的重み、QKの転置K、AVを同じ経路で扱う。DeiTの197token、64dim/head、3headsは端数タイルを含む。入力/出力/作業領域を全てFPGA DDRへ置き、ホストWorkspaceは2848byte固定。DDR scratchは`K*align16(M)+8*align16(K)+512`byte。Aは一度だけ量子化し、動的Bは16K×8N panelで列maxと変換を処理する。

未bind/resetのDDR操作をtransportが拒否することを前提に、開始と最終publicationでsession token/generationを確認する。各I/O/tileではcancelを確認。失敗はabortし、途中DDR書込みが残ってもReport.validはfalse。呼出し側は結果全体を捨て、次ノードを実行しない。scratch/sessionは実行中に専有する。

## ホスト検証

ホスト`tests/test_ddr_matmul.py`で通常・UBSan双方20ケース合格。独立INT64 oracleでQK197×64×197、AV197×197×64を各3heads、K35/N11、0入力、両出力方向、head interleave、範囲/重複/非有限値、通信/tile失敗、cancel/session変更、source/guard保持を確認した。`tests/ddr_matmul_mock.hpp`はnative試験専用で、アプリに組み込まない。

実アダプターが出したQK197×64×197の全hardware traceは2477操作（量子化DDR WRITE852、Conv1300、INT32 READ325）。通常・UBSanで同じtraceとなり、SHA256は`8747f96870c03aed4dc14bdc3b16f5680cd05d89cb67353221872590bbb12aaa`。

## 全ピンRTL試験

`fpga/npu/tests/run_matmul_ddr_core.py`が上記traceをLINKフレームへ変換し、既存4E21のframer/core/arbiter/bridge/adapter/kernelへ実際に送り、全INT32 byteを照合する。SYS≈27MHz、USER≈99.56MHz、ホストは500kHz相当、native DDRモデルはAPP_ROW_PAD=1のアドレスを逆変換する。モデルは検証対象scratchの64KiBを持ち、実DDR PHYは含まない。

**全2478フレーム（trace2477操作＋初期binding）合格。1300回の実Conv起動と325回のINT32読戻しが独立oracleと一致した。** 試験結果は`fpga/build/matmul-ddr-pin-proof-final/result.json`と`run.log`、ホスト通常/UBSanのtrace一致と4E21の8ソースsnapshot一致は`provenance.json`に保存した。既存4E21の64コマンド試験による校正喪失・session世代・abort/resetの証跡も引き続き適用する。

DeiT全12block、学習済みモデル精度、実機Transformer推論の完了はこのMatMul単体証跡とは別。全層実装はホストのTransformer graph/serviceで検証する。Linux/MeOSにはこのホストアダプターを移植していないが、既存NPUコマンドの組合せなのでwire仕様変更は不要。旧4E20/4E21ソース・ビットストリームは変更せず、実機操作はこの作業では行わない。

## 同日追記：packed M版（現行）

上記M16版をbaselineとして保存し、既存4E21のOH16×OW16能力を使ってMを最大256pixelへまとめた。197tokenはOH13/OW16、fullH13/fullW16、input_row_pitch16/channel_pitch208として読み出す。qAのbyte列は変更せず、最後の11tokenを0に初期化して結果から除外する。M>256はorigin_yを進め、M1等はH1/W=Mとする。DDR結果領域は8192byte、host Workspaceは3360byte（旧版より512byte増）へ変更した。feature-major出力はOCごとに最大1024byteを連続read/dequant/writeする。

通常・UBSan双方23ケース合格。M257の二つの空間tile、M16、分類器M1を追加し、量子化・FP32丸めはbaselineと同じ。P4 SDKの実compile_commandsを使った単体objectも警告なしで合格した（全アプリbuild/書込みの証明ではない）。

**packed版の全1150wireフレーム合格**（trace1149操作＋binding）。実Conv起動100、DDR WRITE852、INT32 READ197。全QK197×64×197の数値・padを照合した。旧版1300Convから100Convへ減り、既存RTLの変更は不要だった。trace SHA256は`2b4b30a4c658cdfcb39a1538f5634db87a475709bb83f4134cf8ddb8c6b6a425`。

証跡は`fpga/build/matmul-ddr-packed-pin-proof/{result.json,run.log,provenance.json}`。ホストnative/UBSan/P4 objectのsource、trace一致、4E21の8ソースsnapshot一致を保存した。旧2478frame証跡とhost`build/ddr-matmul-baseline/`のsource snapshotは保持している。

DeiT指定寸法での見込みjob数は651084→51468（12block48816＋embedding1152＋classifier1500）。この数は実機時間を表さない。197tokenを208pixelへpadするため、積和数そのものは増える。Report.macsは論理MAC、padded_macsはpadを含む実行MAC。全モデルのサービスmockと実機測定は主担当が行う。
## 同日追記：per-token A量子化（opt-in）

ホストの`Request.activation_per_row=false`を追加した。既定falseは従来のglobal A方式で、packed版の実hardware trace SHA `2b4b30a4c658cdfcb39a1538f5634db87a475709bb83f4134cf8ddb8c6b6a425`と完全一致する。trueは各A論理row/tokenのK方向max-absをscaleに使う。FPGAに送るINT8とdequantのA_scale[row]が変わるだけで、回路・コマンド・pinは変更していない。

scaleはDDR作業領域末尾に`align16(M)*4`byteを追加して保存する。`scratch_required(m,k,true)`を用い、host Workspaceは4384byte。最大256rowのscaleだけをホストで保持し、dequant時に当該panelを読む。Bは従来の列scale、FP32は`float(sum)*(A_scale[row]*B_scale[col])*alpha`。0rowはscale1。

新旧両方式のnative/UBSan31ケース合格、P4 SDK単体object警告なし。QK197×64×197/AV197×197×64の3heads、振幅が大きく異なるrow、0row、M257/258境界、失敗・session等を確認した。

**rowwise M197/K64/N9の全ピンsmoke：121フレーム合格**。trace120操作はWRITE101、実Conv8、READ11（INT32の9列＋DDR scaleの2回）。新policyの全197出力列hardware試験ではない。全197列はnative独立INT64 oracleで確認した。証跡は`fpga/build/matmul-ddr-rowwise-pin-proof/{result.json,run.log,provenance.json}`。4E21の8ソースsnapshot一致、native/P4 source hashとtraceを記録した。

新policy full197列native trace SHAは`534ac4fc55f93acee9029a6a093f2aa57c9a873e75c5cf79241150fa31d9c82a`、hardware smoke trace SHAは`c7f875dbfa5c93a7e8f5fbb5babce8e7c75f4c00becab113ba5bbd5758f9c6a6`。packed globalソース/proofは保存し、量子化方針を明示して全層・実機の検証を進める。
