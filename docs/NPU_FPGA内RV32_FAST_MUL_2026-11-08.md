# FPGA内RV32のFAST_MUL候補（2026-11-08）

長時間の全Transformer実行前に、PicoRV32の反復乗算を公式FAST_MUL経路へ切り替える候補を検証した。追加したのは`npu_local_cpu_subsystem.CPU_FAST_MUL=0`と、PicoRV32の`ENABLE_FAST_MUL`へ渡す指定だけ。既定値0を維持し、firmware、NN数値演算、モデル、外部ABIを変更しない。[固定証拠](../fpga/validation/npu-local-fast-mul-2026-11-08/README.md)。

独立Python整数oracleと、実際の公式fast/iterative PCPI回路を1348ベクタ（境界81組＋乱数256組×各4命令）で照合し、MUL/MULH/MULHSU/MULHUが全件一致した。未対応opcode、reset、応答の重複抑止も確認。PCPI単体の応答はfast2cycle、iterative平均60/max68cycleであり、CPU命令全体やNN速度をこの比率で予測しない。

実Pico＋cache/MMIOでは同じtile-only検査firmwareの14値/20値が、各2RUN・BSS=A5・epoch37→38で一致した。IC17連結の非final結果非公開、partial accumulator、DDR guardも含む。MACは明示した独立整数doubleで、全NN実機の証明ではない。DDR要求数776/1400は変わらず、fixture cycleは55965→50386／182589→153166。実DDR PHYや実機NN性能の値とは区別する。

単体合成（Gowin Education1.9.11.03、ENABLE_MATRIX=0/FAST_MUL=1）はLogic5455、FF2016、BSRAM1、RAM16=72、DSP primitive MULT36X36×1、推定Fmax72.547MHz。tool表示の制約はdefault100MHzで、全chip PNR/STAではない。36×36 primitive数を18×18物理DSP使用数へ読み替えない。親の全chip配置配線・資源評価・実機数値試験が必要。以前の5824Logic部品はMATRIX=1/FAST=0なので、面積削減の同条件比較とは呼ばない。

本候補を使う場合も毎RUN前のfirmware全体upload/readbackを行う。CPU/cache CLEARだけでmutable `.data` を初期化したとは扱わない。旧FSを保存し、未検証候補を合格版と上書きしない。

全chipのplace0/route0、および同一netlistを用いたplace1/route0のPNR単独再試行は、いずれも`DesRoute failed`で失敗した。資源数は範囲内だが、原因を特定の資源と断定できない。**FAST_MUL候補は現時点で書込み可能な合格版ではない。** Dock topの指定をFAST0へ戻し、既存FAST0 FSで全モデル実機検証を進める。任意parameterと単体試験は保持する。[全chip失敗と再試行の証跡](../fpga/validation/npu-autonomous-fastmul-fullchip-2026-11-08/README.md)。
