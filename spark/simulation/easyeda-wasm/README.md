# EasyEDA API内でのNGspice再計算

このフォルダは実行結果と再現用入力。計算はEasyEDA API Gatewayのブラウザーコンテキスト内に作成したWorkerで行う。公式 `easyeda/eext-simulation-with-ngspice` の未改変NGspice46 WASM・ローダー・XSPICEモジュールを使用し、版とSHA-256を `runtime-manifest.json` に固定する。現行クライアントは3.2.149、公式拡張全体のインストールやクライアント更新は行わない。

## 2026-10-26の結果

| 再計算 | 計算完了 | 従来解析との一致 |
| --- | --- | --- |
| 平均モデルの5V電源 | 6/6、全条件で4.5～5.5V内 | 電圧指標の最大差0.0173mV、Core波形の比較最大差0.0148mV |
| 通信15信号×5条件×双方向 | 150/150 | 全150の合否分類一致。電圧極値の最大差0.0253mV、整定時間の最大差0.00913ns |
| 1/10/20/40MHz周期モデル | 16/16 | 全16の閾値判定一致。サンプル電圧の最大差4.21mV。1MHzは4/4合格 |

通信は受信端150/150合格、送信端60/150合格。高速駆動90条件での不合格を再現しており、回路の全条件合格とはしない。初期1MHz・弱駆動/SLOWと実機確認の必要性は変わらない。電源のPD入力プロファイルだけ、0Ω抵抗を1e-12Ωへ置き換える警告1件がある。全172ケースに計算エラーはない。

## 実行範囲

- 製造用回路図全体の自動SPICE化ではなく、従来の解析用等価回路をEasyEDA内で再計算した。
- エンジンへの入力、実際の数値出力、診断を保存する。外部計算済みの値をSIMULATION_RESULTへ注入して済ませる処理はない。
- Pythonはモデル入力の準備、API呼出し、計算後の比較・図化だけを担当し、この再実行のSPICE計算は行わない。
- HDL、DDR3コントローラ、Linux/DMA、PD交渉、熱、完全なIBIS/3D電磁界解析は対象外。

## 再現手順

作業ディレクトリはリポジトリルート。EasyEDAと既存API Gatewayの接続を維持する。

1. `python spark/bootstrap_easyeda_wasm.py` で固定した公式ランタイムを検証・取得する。既存クライアントへインストールはしない。
2. `python spark/prepare_easyeda_wasm.py` で電源6条件の入力を作成する。`.include` を展開し、cp1252コメントをデコード。展開後のライブラリにもPSpice構文処理を適用するため `psa` を使う。回路の方程式・解析時間・負荷は変更しない。
3. `power-input.json` を `active-input.json` へコピーし、`python spark/easyeda_call.py spark/design/easyeda-run-wasm.js spark/simulation/easyeda-wasm/power-all-run.json` を実行する。
4. `python spark/prepare_easyeda_parallel.py`、`python spark/run_easyeda_batches.py parallel --force` で通信150条件を再実行する。
5. `python spark/prepare_easyeda_periodic.py`、`python spark/run_easyeda_batches.py periodic --force` で周期16条件を再実行する。
6. `compare_easyeda_power.py`、`compare_easyeda_parallel.py`、`compare_easyeda_periodic.py` で既存結果と比較する。各スクリプトは `spark/` 下。電源の全波形比較は従来解析のNPZ（`D:/tmp/carrier-power-transient/`）も必要。なければ従来の `spark/simulate_power.py` を明示的に再実行して比較基準を作る。

`--force` なしでは、入力ハッシュが同じ既存の計算結果を再利用する。再計算を要求する場合は `--force` を指定する。通信は10条件、周期モデルは1条件ずつAPIを呼び出して直列実行し、各条件のWorkerは終了時に破棄する。

周期解析はソルバーの可変刻み波形が10万点を超えたため、計算完了後にNGspiceの `linearize` で元の `.tran` 出力間隔100psへ補間してから書き出す。ソルバーの回路方程式・時間刻み設定・終了時間は変えない。元の可変刻みplotはWASM内の出力上限により書き出さず破棄する。周期16条件の判定はこの補間出力を使い、従来の可変刻み波形からの判定と比較した。通信150条件の過渡極値は補間せず可変刻みの全出力から求める。

## 結果と原データ

- `power-comparison.json`：電源6条件の電圧・波形の比較。
- `parallel-comparison.json`：150条件の端子電圧・整定時間・合否分類の比較。
- `periodic-comparison.json`：1/10/20/40MHzの閾値判定比較。
- `power-waveform-comparison.png`：独立に再計算した電源波形の重ね合わせ。
- `results/*.json`：各ケースの実計算結果、実行環境、診断、入力ハッシュ。`ok` は数値計算の完了を指し、回路の全電圧条件合格とは区別する。
- エンジンから取得した大きな波形データは `D:/tmp/easyeda-ngspice-wasm/raw/`、ハッシュは `raw-waveform-manifest.json`。電源/通信は可変刻みの全出力、周期解析は上記100ps補間出力。電源の可搬な間引き波形を `results/*.csv` に残す。

比較許容値は電圧25mV・通信整定時間1ns、全合否分類の一致を要求する。これは計算環境間の照合基準で、回路の許容電圧・実機性能の合格基準を緩和するものではない。PD入力ケースの0Ω抵抗はエンジンにより1e-12Ωへ置換され、その警告も残す。
