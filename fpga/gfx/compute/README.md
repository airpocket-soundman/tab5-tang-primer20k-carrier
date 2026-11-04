# Programmable compute SIMD: offline prototype v0

2026-11-04。Julia専用命令の追加ではなく、同じ演算器へプログラムをロードして計算内容を変更するための独立したRTL試作。既存LINK/GFXの命令、GPIO、電源、ビットストリームは変更しない。ホストへ公開する通信ABIではない。

## 実装した範囲

- 共有PC・共有命令メモリ、各レーン16本の32bitレジスタ、レーンごとの述語。既定2レーン、1/2/4レーンで検証する。
- 加減乗算、Q12乗算、符号付き比較、bit演算、shift、load/store、条件分岐、停止。
- 同じRTLで、Julia反復回数を計算するプログラムと、配列のscale/bias計算を実行する。Juliaというopcodeや専用反復回路はない。
- 命令メモリは停止中に書込み、ジョブ間も保持。毎ジョブはentry、group_base、命令数上限を指定する。レジスタは毎ジョブ初期化する。
- 外部メモリは1要求ずつ、レーン番号順に処理。ready/validと応答チャネルを分離し、受付停止・可変遅延・読書きエラーを試験する。

`rtl/compute_simd.v`が演算器、`model.py`がアセンブラ・ISA参照実行器・サンプルプログラム。JuliaはISA実行器とは別の数式オラクル、配列演算も直接の数式と照合する。RTL試験は全レジスタ・メモリ全256word・要求列・終了状態・命令数を比較する。

これは少数レーンの基礎構成で、完成GPU、汎用シェーダコンパイラ、DDR3コントローラ、ラスタライザとの統合版ではない。計算中のデータ転送重畳・burst/coalescing・local cache・モデル常駐管理も未実装。プログラム保持と一括実行の意味を先に確認する。

## 命令と数値仕様

32bit命令はopcode `[31:26]`、pred `[25]`、dst `[24:21]`、a `[20:17]`。レジスタ演算のbは `[16:13]`、即値形式は `[15:0]`。即値形式ではbフィールドは使用しない。未使用ビットは無視し、アセンブラは0にする。

| opcode | 命令 | 意味 |
|---|---|---|
| 0 | HALT | ジョブ終了 |
| 1 | LDI d,imm16 | 符号拡張した即値を書込む |
| 2 / 3 | ADD / SUB d,a,b | 32bit加減算 |
| 4 | MUL d,a,b | 積の下位32bit |
| 5 | MULQ d,a,b | signed 64bit積を算術右shift12、下位32bit |
| 6 | LT d,a,b | signed比較、結果は0または1 |
| 7 / 8 | AND / XOR d,a,b | bit演算 |
| 9 / 10 | SHL / SAR d,a,b | bの下位5bitで左shift／算術右shift |
| 11 | LOAD d,[a+imm16] | 32bit word読込み |
| 12 | STORE d,[a+imm16] | r[d]を32bit word書込み |
| 13 | JMP target16 | 絶対命令アドレスへ分岐 |
| 14 | ANY a,target16 | いずれかのレーンのr[a]が非0なら分岐 |

すべての演算結果は32bitでwrapし、飽和しない。MULQの負値は負の無限大方向へ丸める。浮動小数点は扱わない。Q12は小数12bit・符号付き32bitの値であり、旧専用フラクタル回路の18bit内部値とは別の数値契約。既存GPU LABの画像・速度との等価性はまだ検証していない。

r0は常に0、書込みは破棄。r1は起動時に`group_base+lane`（32bit wrap）、r2..r15は0。r1もプログラムから変更できる。pred=1の算術・即値・メモリ命令は、その命令開始前のr15が非0のレーンだけ実行する。r15自身への書込みも同じ規則。無効レーンはメモリ要求も発行しない。HALT/JMP/ANYはpred禁止。ANYは全レーンのr[a]を見る。独立PCや自動的な分岐再合流機構はなく、プログラムでactive maskを維持する。

命令メモリは既定256word、PC_BITS=8。ハードウェア上の対応範囲はPC_BITS=1..16、LANES=1..4を想定し、今回の検証はPC_BITS=8・LANES=1/2/4のみ。loaded bitで未ロード命令を拒否する。リセットでloadedを無効化し、再ロードが必要になる。ジョブ間は保持される。命令末尾からのfallthroughを0へwrapしない。busy中のprogram_we/startは無視。停止中に両方が立つとprogram_weを優先する。

`instruction_limit`はデコード命令数の上限。HALT・不正命令も1と数える。未ロードfetchと範囲外fetchは数えない。上限到達後は次の命令を実行しない。0なら起動拒否。`cycles`はbusy中のクロック数で、メモリ待ちも含む32bit wrapカウンタ。クロック周波数・実機速度を保証する値ではない。

| error | 意味 |
|---|---|
| 0 | 正常HALT |
| 1 | 不正opcode／述語付きフロー命令 |
| 2 | 未ロード命令のfetch |
| 3 | entry／実行PC／取られた分岐先が範囲外 |
| 4 | メモリ応答エラー |
| 5 | 命令数上限0または超過 |

doneは正常・異常の両方で1クロックpulse。error、cycles、instructionsは次の起動まで保持。エラー前に完了したSTOREを取り消さない。全レーン一括のトランザクションではなく、再試行は呼出し側が判断する。

## メモリ接続の契約

アドレスはbyteではなく32bit **word index**、`(r[a]+signed imm16) mod 2^32`。LOAD/STOREごとに有効レーンを番号順に直列処理する。同一アドレスSTOREは後のレーンが最後に書く。将来のDDR adapterはword→byte変換、領域検査、128bit等へのpack/unpack、write mask、応答・error・timeoutを実装する。現在のwordアドレスをそのままDDR IPへ接続してはいけない。

要求は`mem_valid && mem_ready`、応答は`rsp_valid && rsp_ready`で成立する。要求受付前は内容を保持し、同時に1要求だけ発行する。書込みも応答が必要。応答は要求受付の次クロック以降に返し、消費まで保持する。rsp_error=1ならデータを使わず停止する。

命令数上限は壁時計タイムアウトではない。メモリ応答が永久に来ない場合、演算器は待ち続ける。外部adapterが待機上限を持ち、受理済み要求を排出してエラー応答すること。リセット時は演算器とadapterを一緒にリセット／drainし、旧応答を新ジョブへ混入させない。この試作にabort/tag機能はない。

## プログラム例

Juliaはxを`memory[id]`、yを`memory[id+32]`から読み、反復回数を`memory[id+64]`へ書く。cx/cy/反復上限は即値。共有ループで各レーンの脱出判定を行い、終了済みレーンのactiveを0に保持する。配列演算も同じ入出力領域で`floor(input*scale/4096)+bias`を計算する。

サンプルの領域配置は小さな試験専用であり、id=0..31の範囲で使う。全画面画像の汎用メモリ配置、最終画素のパレット、フレーム管理は別途実装する。LANES未満の末尾を扱う場合はプログラム側でid境界マスクを作る必要がある。

## 再現

既存Icarus Verilog/vvpが必要。Yosysを指定するとGW2A向けの**部品合成**も行う。インストール、実機接続、書込みは行わない。

```powershell
python fpga/gfx/compute/tests/run_compute.py --iverilog D:/tools/oss-cad-suite/bin/iverilog.exe --vvp D:/tools/oss-cad-suite/bin/vvp.exe --yosys D:/tools/oss-cad-suite/bin/yosys.exe --report fpga/validation/compute-simd-offline-2026-11-04.json
```

生成物は無視対象`fpga/build/compute-simd/`。生の部品合成ログ・統計、プログラムhex、期待値、メモリ要求列を保存する。テストは1/2/4レーン、遅延あり／なし、同じコードを再ロードせず2回起動、reset後のコード失効を確認。数式オラクル、符号・overflow・shift、述語付きメモリ、メモリエラー、未ロード・不正命令・分岐範囲・命令数上限を扱う。

資源集計と試験結果は[検証JSON](../../validation/compute-simd-offline-2026-11-04.json)を参照。合成成功は配置配線・STA・デバイス全体の収容・DDR3併載合格を意味しない。CPUとの速度比較も未実施。

ホスト要求の照合・変更の影響・次の段階は[開発記録](../../../docs/汎用GPU演算器_オフライン開発_2026-11-04.md)に記録する。
