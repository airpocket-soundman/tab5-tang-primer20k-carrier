# Dock三角形・フラクタルタイル仕様

2026-11-03。三角形GFXビットストリームにMandelbrot/Juliaの固定小数点演算を追加する。
既存三角形命令、32×32 RGB565/深度RAM、TRI_ROW応答を維持する。DDR3、DMA、
自作キャリアやHDMIを必要としないDockジャンパ接続用の実験命令である。
通信ピン、電源、バスの方向転換、CRC、タイムアウト、ARMの電気条件は変更しない。
通信速度の段階試験と実測結果は別記録とし、本書のRTL試験を実機速度の根拠にしない。

## 命令

要求・応答は既存v0の8バイト。16bit値はaが下位、bが上位。
成功したTRI_ROWだけ従来どおり74バイトで返す。

| opcode | 命令 | a,b / 値 | 成功時の値 |
|---|---|---|---|
| 30 | FRACTAL_INFO | 通常0,0 | 0107（版1、Mandelbrot/Julia・演算時間計測対応） |
| 31 | FRACTAL_X0 | タイル左上の実部、signed Q4.12 | 設定値 |
| 32 | FRACTAL_Y0 | タイル左上の虚部、signed Q4.12 | 設定値 |
| 33 | FRACTAL_DX | x1画素ごとの増分、1..32767 | 設定値 |
| 34 | FRACTAL_DY | y1画素ごとの増分、1..32767 | 設定値 |
| 35 | FRACTAL_CX | Julia定数実部、signed Q4.12 | 設定値 |
| 36 | FRACTAL_CY | Julia定数虚部、signed Q4.12 | 設定値 |
| 37 | FRACTAL_CONFIG | a=最大反復1..128、b=0 Mandelbrot/1 Julia | a,b |
| 38 | FRACTAL_DRAW | 0,0 | 1024（0400） |
| 39 | FRACTAL_CYCLES_LO | 0,0 | 直前の完成DRAWのサイクル数、下位16bit |
| 3a | FRACTAL_CYCLES_HI | 0,0 | 同上、上位16bit |

31〜37の7設定はreset/ARM解除/描画中timeoutによるabort後に全て再設定する。
MandelbrotでもJulia定数の設定を省略しない。DRAW前のTRI_CLEARは不要。
X0+31*DX、Y0+31*DYはsigned16bit上限32767以下とする。
設定不足はstatus5、不正なCONFIG、DRAW引数、増分、範囲はstatus3。
不正要求は直前の完成画像を書き換えない。新しいDRAW開始時は画像を無効化し、
全1024画素が完成するまで読出し可能にならない。途中abort後は設定と画像を無効化する。

## 数値規則

座標、定数、zの小数部は12bit。整数値4096が実数1に相当する。
タイル画素(x,y)に対してpx=X0+x*DX、py=Y0+y*DY。
Mandelbrotは(zx,zy)=(0,0)、(cx,cy)=(px,py)で開始する。
Juliaは(zx,zy)=(px,py)、(cx,cy)=(CX,CY)で開始する。

反復数i=0から、zx*zx+zy*zy < 4*4096*4096 かつ i<最大反復の間、
旧zx/zyを両方使用して以下を計算し、iを1増やす。

```text
next_x = floor((zx*zx - zy*zy) / 4096) + cx
next_y = floor((2*zx*zy) / 4096) + cy
```

負数の除算も負の無限大方向へ丸める。RTLはsigned算術右シフトを用い、
C正本は`fractal_floor12()`で同じ意味を明示する。zはsigned18bit、積はsigned36bit、
2倍積と大きさ判定は37bitを使用し、中間積の切捨て・飽和は行わない。
脱出判定前に計算した積と、更新前のzx/zyを使用する。

iが最大反復に達した画素はRGB565 0042。その他はn=i*3、
R=32+(n*9 mod224)、G=60+(n*5 mod196)、B=100+(n*3 mod156)を
通常のRGB565へ切り詰める。浮動小数点GPU LABとは境界画素の結果が異なり得るため、
CPU/GPU比較は同じQ4.12設定と本規則を使う。
DRAWは全色画素を上書きし、全深度を0にする。続けて三角形DRAWを使用する場合は
三角形側のパラメータを設定し、その深度規則に従う。

## ホスト要求・参照版

| 対象 | 確認HEAD | 適合性・反映 |
|---|---|---|
| ESP-IDF tab5-fpga-gpu | f8e978f3127e15200942305dc6b5f2aa8bc4f937 | Project B、GPU LAB整数/浮動描画、GPIO診断、LCD経路を確認。CPU/GPU切替デモを並行実装中。反映版とハッシュはホストの記録で固定する。 |
| MeOS tab5-meos-fpga | 26c8082961b1152901475fb56bbb2e8be192a4da | 要求資料、fpga_link.h、GFX CLIを確認。既存LINK/GFXとはopcodeが衝突しない。三角形/フラクタル操作と74バイト読戻しはホスト未実装。今回のソース反映なし。 |
| Linux tab5-linux-fpga | cfc9a6ecf7daa4c5e3decbe3885b22c2bd2f4cd1 | README、DEVELOPMENT_GOALS、Tab5 Device Tree、パッケージ/ドライバ実装を確認。物理FPGA/GPU backendと本命令は未実装。今回のDT/ドライバ反映なし。 |
| 外部メモリ研究 esp32p4-linux-fpga-memory | e4aa69d09b2643d6f62fe686ef0f3284b109c541 | READMEと計画書を確認。DDR3の明示アクセスと外部メモリ研究要求を保持。今回は内部RAMの演算タイルのみで、Linux本体の確認の代用にはしていない。ソース反映なし。 |

プロトコルcodecとC参照の正本は`fpga/host/link_protocol.h`、
`fpga/host/fractal_reference.h`。全OSから同じ命令と整数規則で利用でき、
OS固有のGPIO/DMA/画面更新はそれぞれのホストが担当する。
初期状態ではLINKと矩形GFXの既存ビットストリームは新命令をstatus2で拒否する。
三角形+フラクタルの同時搭載はGFX内の機能追加であり、NPU/MEMとの混載ではない。
合成資源・配置配線・実機の完了状況は、生成manifestと今回の別検証記録で判断する。

## PC検証

`fpga/gfx/tests/run_fractal_tile.py`は独立Pythonオラクルで生成した要求/応答を
Dockピン経由RTLシミュレーションと比較する。Mandelbrot/Julia、最大128反復、
負の丸め、タイル範囲端、Julia初期値での即脱出を含む5viewportで色・深度10,240画素、
全413通信が一致した。不正CONFIG/増分/範囲/DRAW引数/CRC、未設定、
描画中timeout/abort、読戻し途中の切断、reset/ARM解除と旧ビットストリームの拒否も確認した。
既存`run_triangle_rows.py`の410通信・三角形/深度照合も通過した。

実行にはIcarus/vvpの既存実体を`--iverilog`、`--vvp`へ指定する。
OSS CAD SuiteのWindows版は子プロセスのDLL探索のため、そのbinとlibの両方を
実行プロセスのPATHへ追加する。この変更をシステムPATHへ保存する必要はない。
これらはPCでのRTL検証であり、実機書込み・描画時間・通信速度の実測ではない。


C参照と新命令codecは`fpga/host/tests/test_fractal_reference.py`で検証した。
独立Pythonと29viewport・29,696色画素が一致し、負の丸めと設定範囲の拒否も確認した。
全新命令の正常応答と、各応答の全8バイトの改変81ケースをC codecで照合した。
既存codec/三角形/行応答の4テストも通過した。CはZig0.16.0の
`cc -std=c11 -Wall -Wextra -Werror`でビルドした。
PC試験のソースハッシュは[fractal-rtl-2026-11-03.json](../fpga/validation/fractal-rtl-2026-11-03.json)に記録する。


## 1サイクル反復と実機演算時間計測

反復演算を1回あたり1クロックへ変更した。signed18bitのzx/zyからsigned36bitの積を
組合せ演算し、同じ符号拡張、37bitの脱出判定、負の無限大方向の右シフトを保持する。
前の画素のRAM書込みと同じクロックで次の画素の初期値を設定し、画素間の初期化待ちも省いた。
数値規則と全画素の結果を変えず、合成後27MHzの条件に合格したイメージだけ実機へ使用する。

INFOの上位バイトは版1、下位バイトのbit0がMandelbrot、bit1がJulia、bit2が時間計測。
初期版0103は時間計測命令が未実装、追加版0107は39/3aを実装する。
新ホストのcodecは0103と0107を受理し、bit2が立っている場合だけ39/3aを送る。
0103との完全一致しか許可しない旧ホストは0107を拒否するため、追加版を使用する際は
対応したホストへ更新する。MeOS/Linuxにはフラクタル操作自体の実装がなく、今回それらの
ドライバやDevice Treeの更新は不要。後日ホスト実装を追加する場合は同じ能力bitで判定する。

39/3aは、成功したFRACTAL_DRAWが受理されたクロック端から、最後の色・深度画素の
RAM書込みが行われたクロック端までの経過クロック数を32bitで返す。
対象クロックはsys_clk=27MHz。コマンド要求の送信、完了応答、ROWのスナップショット構築、
読戻し、CPU処理、LCD更新を含めない。DRAWの往復時間にはこの演算区間が既に含まれているので、
描画全体の時間へ重複加算しない。
LO/HIの問い合わせの間は値を変えず、次の有効なFRACTAL_DRAW開始時に未確定へ戻す。
reset/ARM解除/renderer abortでも無効化する。完成したDRAWがなければstatus5、
a,bが0以外ならstatus3を返す。新DRAWを開始しない限りCLEARや三角形操作を挟んでも
最後のフラクタル演算の測定値を保持する。

現在の実装では32×32タイルの反復数合計に2,049を加えた値になる。
全画素が即脱出なら2,049、全画素が最大128反復なら133,121クロック。
この関係と独立した整数オラクルによる反復数を用い、LO/HI両半分・繰返し取得・範囲端・
不正引数・abort後の無効化をRTLで検証する。ホストはフレーム内の全タイル分を合計して
27で割ればマイクロ秒へ換算できるが、最終アプリの比較では転送・読戻しを含む時間も併記する。


1サイクル版の最終PC回帰では523通信、6viewportの色・深度12,288画素と
全サイクル値が一致した。全128反復のタイルと初期値で即脱出するタイルを含む。
三角形bboxの2,432通信・65,536画素も再照合し、C参照29,696画素と新旧能力値のcodec104ケースが成功した。
[ソースハッシュと結果](../fpga/validation/fractal-singlecycle-rtl-2026-11-03.json)を参照。
