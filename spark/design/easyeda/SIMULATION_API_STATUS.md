# EasyEDA内シミュレーションのAPI確認

2026-10-26。ユーザー指定によりComputer Useは使わず、接続済みAPI Gatewayで確認。

`simulation-api-capabilities.json` は実クライアントからの応答。現行Spark回路図を開いて次を確認した。設計要素は変更せず、試験用イベントリスナーは登録後に解除した。

| 項目 | 実確認 |
| --- | --- |
| SCH_ManufactureData.getSimulationNetlistFile | 関数あり。現行の製造用回路図からはファイルを返さない。製造用ネットリストと解析用ネットリストは別 |
| SCH_Event.addSimulationEnginePullEventListener | API Gatewayの拡張コンテキストから登録・解除に成功 |
| SCH_SimulationEngine.pushData | 関数あり。ただし公開SpiceイベントはSIMULATION_RESULT/VALIDATION_RESULT/LOG_RESULT/ERROR_RESULTであり、解析開始命令ではない |
| シミュレーション用ショートカット一覧 | Simulation Menuのみ。解析用文書種別12/13が対象 |
| 解析ページ作成・モデル設定・開始の一括API | 導入済みSDK0.2.53と公開API資料では確認できず。通常回路図の編集APIだけで内蔵解析を開始できるとは結論しない |

実装ソースの読取りでも、pushDataは結果イベントの中継であることを確認。結果イベントへ既存の外部計算値を流して「EasyEDA内で再計算した」と扱わない。

上記は当初のAPI機能確認。その後、公式拡張のNGspice46 WASMをAPI Gateway内のWorkerで実行する経路を確立し、電源6条件と通信150条件の再計算・従来結果との照合まで完了した。専用の開始APIは不要だった。製造用回路図の自動SPICE化ではなく、既存の解析モデルをEasyEDA内で再実行した結果である。GUI操作は再開していない。

周期モデル16条件も追加し、計172ケースの実計算と比較を完了した。現行の再現手順・ハッシュ・比較結果は `../../simulation/easyeda-wasm/README.md` を参照。`pushData` に外部計算値を注入する処理は使用していない。波形はEasyEDAプロセス内で新たに計算された実出力から取得した。

公式参照：
- https://prodocs.easyeda.com/en/api/reference/pro-api.sch_simulationengine.pushdata.html
- https://prodocs.easyeda.com/en/api/reference/pro-api.esch_spicesimulationenginepusheventtype.html
- https://prodocs.easyeda.com/en/api/reference/pro-api.sch_event.addsimulationenginepulleventlistener.html
- https://prodocs.easyeda.com/en/api/reference/pro-api.sch_manufacturedata.getsimulationnetlistfile.html
