# 3案の電源過渡解析（2026-10-25）

結論の機械可読版は `final-summary.json`。3案とも正規12Vの最低条件はモデル内でpass、総合statusはuncertain。これは製造後の保証試験ではない。CADは変更していない。

## 必須条件と結果

正規12V±5%、室内0..50℃、Core定常0.5A、キャリア3V3は外部給電なし・通常10mA以下。Core端子4.5..5.5V、起動後の3V3±5%を評価。Tab5 HVIN負荷1Aは公開最大定格ではなく追加予算感度。Core 1A stepも追加感度。

C11有効容量を公称22uFの30%=6.6uF、LDOループを基準の0.5倍、基準電圧−2%にした通常0→5→10mAでも最低3.1513Vでモデル下限3.135Vを満たす。ただし余裕は約16mVで、メーカーの3.3V品全角保証ではない。

C7 ESR2mΩ、L12uH、C176uF、PWM応答1.25usの250ms解析はCore最低約4.674V、定常区間に持続・増大振動を認めない。一方解析最小位相余裕6.58°は小さい。ESR20/40mΩの最悪感度は29.32/39.15°。コンデンサESR下限が未規定のためプロセス・遅延込み安定性は未保証。

## モデルと校正

TI公式非暗号化TPS5430モデルは無改変で保存。単純な基準回路では500kHzスイッチング、8ms softstart、9/10ms負荷変化を含む11msを完走（3494628点、約759秒）。平均化モデルはTIの誤差増幅器RC・内部補償・入力フィードフォワードを保持し、8.5..10.8msのメーカー波形とRMS0.974mV、最大6.059mV差。メーカーEVM資料の50°/25kHzに対し、対応する公称解析は45.89°/20.16kHz。完全一致の校正ではない。

実配線R・入力保護・LDOを加えたメーカー全スイッチングデッキはngspiceのtimestep errorで0.518msに停止。成功扱いしていない。全案の広いmatrixは校正した平均化モデルによる。理想5V源で置換していない。軽負荷DCM・pulse skipping・hiccup・ICプロセス角は十分再現していない。

XC6206メーカーSPICEは入手できず、公式3.0V系典型曲線（1uF、1→40mA）の最小約2.45V/最大3.5Vに対し2.475/3.525Vに合わせたPI/pass電流モデル。選定3.3V品の典型挙動推定であり、負荷ステップの保証モデルではない。50mA急変では±5%を外れるケースをfailとして残した。実キャリア負荷はA/B約4.81mA、C約4.2mA、OEの高速PWMは禁止。

数値対策は有限入力立上り、gear積分、有限PWM応答、連続antiwindup、明示clamp関数。初期試作の不適切な理想ダイオード逆漏れとB-source limit解釈を修正後、必須matrixを再計算した。コードと結果のdeck hashで照合可能。

## 電源異常と運用条件

PD5→9→12Vは電圧profileのみでCH224K交渉・アダプタ電流制限は未モデル化。9Vでは既存ENA回路がONし得るため『非12Vは必ず遮断』は誤り。正規使用は12Vとし、電源安定まで通信しない。

K50の4.38V監視はCore下限4.5Vの動作保証信号ではない。OFF/brownout時は通信停止、ARM解除、安定後DDR3再初期化を必要条件とする。20us assertionはtypicalで最大保証ではない。Core基板内3V3の保持や異常時逆給電を無条件に保証しない。

長時間逆接2秒ではVIN約−0.411Vを予測しTPS5430絶対下限−0.3Vを外れる可能性がある。SS54漏れ/TVS低電流forwardは近似で、逆接保護保証はuncertain。今回の最低条件は正規正極性12Vであり、追加ダイオードは実装していない。

温度設定はSPICE定数感度であり、基板・ケースの熱FEMではない。インダクタ熱、ダイオード放熱、外部Tab5消費電力、Core最大消費電流は実機確認を要する。

## 再現

Windows Python + numpy/scipy/matplotlib、KiCad10 ngspice.dllを使用。`python prepare_cases.py`、`python prepare_extra_cases.py`、`python run_suite.py --average-only`、`python run_suite.py --extras --average-only`、`python calibrate_ldo.py`、`python loop_margin.py`、`python analyze_results.py`。メーカー単純基準のネットリストはmodels/calibration-vendor-minimal.cirに保存してあり、ngspice_shared.Spiceへそのままload/runできる。メーカー全案失敗もJSONに残す。

raw数百万点NPZと実行ログは `D:/tmp/carrier-power-transient/`。Gitには回路デッキ、case、定量JSON、代表間引きCSV、PNGのみ保持する。解析対象PCB hashは各caseとsummaryにあり、今後CAD変更時は再実行が必要。
