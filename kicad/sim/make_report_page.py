"""Builds site/hdmi-simulation-r2.html from the simulation outputs (run after make_report_figs.py).

python -X utf8 kicad/sim/make_report_page.py
Numbers come from tmds_summary.json, report_sparam.json, report_variants.json, continuity_report.json (nothing is typed by hand
except the text and the audit baseline values that are marked as such).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "..", "site")
idx = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
style = idx[idx.index("<style>"):idx.index("</style>") + 8]
J = lambda n: json.load(open(os.path.join(HERE, n), encoding="utf-8"))      # noqa: E731
summ, sp, var, cont = J("tmds_summary.json"), J("report_sparam.json"), J("report_variants.json"), J("continuity_report.json")
PAIRS = ["D0", "D1", "D2", "CK"]
GH = "https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/"
AUD = "docs/%E3%82%B7%E3%83%9F%E3%83%A5%E3%83%AC%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E6%96%B9%E9%87%9D%E3%81%A8%E7%9B%A3%E6%9F%BB%E8%A8%98%E9%8C%B2.md"
HDOC = "docs/HDMI_%E4%BF%A1%E5%8F%B7%E5%93%81%E8%B3%AA_%E8%AA%BF%E6%9F%BB%E3%81%A8%E6%96%B9%E9%87%9D.md"
IMG = 'style="width:100%;height:auto;display:block;border-radius:6px"'

worst11 = max(sp[k]["s11_max_1500"] for k in PAIRS)
worst21 = min(sp[k]["s21_742"] for k in PAIRS)
zmin = min(summ[k]["zmin"] for k in PAIRS)
cont_ok = "全8線で連続" if cont["ok"] else "不連続あり"
rows_len = "".join('<tr><td>%s</td><td class="c">%.2f / %.2f</td><td class="c">%.2f mm</td><td class="c">%.0f / %.0f</td><td class="c">%.1f / %.1f mm</td><td class="c">%.0f %%</td></tr>\n'
                   % (k, summ[k]["len_p"], summ[k]["len_n"], summ[k]["skew"], summ[k]["zmin"], summ[k]["zmean"],
                      summ[k]["branch_C"][0], summ[k]["branch_C"][1], summ[k]["coupled"]) for k in PAIRS)
rows_sp = "".join('<tr><td>%s</td><td class="c">%.1f / %.1f dB</td><td class="c">%.1f dB</td><td class="c">%.2f / %.2f dB</td><td class="c">%.2f dB</td></tr>\n'
                  % (k, sp[k]["s11_371"], sp[k]["s11_742"], sp[k]["s11_max_1500"], sp[k]["s21_371"], sp[k]["s21_742"], sp[k]["s21_1500"]) for k in PAIRS)
rows_var = "".join('<tr><td>%s</td><td class="c">%.1f dB</td><td class="c">%.2f dB</td></tr>\n' % (k, v["sdd11_max_1500"], v["sdd21_742"]) for k, v in var.items())
rows_pol = "".join('<tr><td>%s</td><td class="c">%s</td></tr>\n' % (k, "一致" if v["same_order"] else "<b>不一致</b>") for k, v in cont["polarity"].items())

page = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HDMI信号品質 シミュレーション評価レポート（是正後）</title>
<meta name="description" content="Tab5 × Tang Primer 20K キャリア基板のHDMI（TMDS）配線の評価。監査指摘の是正、再解析の結果、限界。">
""" + style + """
</head>
<body>
<header class="top"><div class="wrap">
 <p><span class="badge">シミュレーション評価レポート</span><span class="badge">監査指摘の是正後・再提出版</span><span class="badge">推定値（3D解析は較正中）</span></p>
 <h1>HDMI信号品質 シミュレーション評価（是正後）</h1>
 <p class="sub">キャリア基板 v2.1 のTMDS 4組を、実際の配線データから評価。更新：2026-10-24　／　<a href="index.html">← 企画・設計仕様に戻る</a></p>
</div></header>
<nav class="toc"><div class="wrap">
 <a href="#summary">結論</a><a href="#fixes">是正の実施</a><a href="#scope">範囲・基準</a><a href="#method">手法</a><a href="#valid">検証</a><a href="#result">配線結果</a><a href="#channel">チャネル推定</a><a href="#variants">感度</a><a href="#em3d">3D解析</a><a href="#limits">限界</a><a href="#repro">再現・記録</a>
</div></nav>
<main class="wrap">

<section id="summary">
 <h2>結論</h2>
 <div class="kpi">
  <div><b>0.00 mm</b><span>ペア内スキュー（4組すべて）</span></div>
  <div><b>約%(zmin).0f Ω</b><span>結合区間の差動インピーダンス（目標 100Ω ±15%%）</span></div>
  <div><b>≤ %(w11).1f dB</b><span>SDD11 最大（〜1.5GHz、悪い方のペア）</span></div>
  <div><b>%(w21).2f dB</b><span>SDD21 @742MHz（悪い方のペア。499Ω負荷の約−0.4dBを含む）</span></div>
 </div>
 <div class="callout ok"><b class="t">監査指摘への対応</b>独立監査の2つの必須指摘を是正し、再配線・再抽出・再解析しました。①TMDS用ESDは<b>信号線を連続した銅配線にし、ESDを分岐として接続</b>（部品内部の導通に依存しない。TMDS %(cont)s）。②499Ω抵抗の枝は、以前の21〜53mmから<b>%(bmin).1f〜%(bmax).1fmm</b>に短縮し、解析に含めました。DRC違反0、未接続0。</div>
 <div class="callout warn"><b class="t">まだ残っていること</b>D1のN側の枝（%(d1n).1fmm）は「数mm以下」の目標に届いていません。チャネル推定は<b>準静的モデル</b>で、3D解析（openEMS）は較正前のため結論に使っていません。目標は<b>短いケーブル・限定モニタでの720p60のPoC動作</b>で、動作保証・全機器互換・HDMI規格適合を意味しません。</div>
</section>

<section id="fixes">
 <h2>1. 監査指摘と是正の状況</h2>
 <div class="tw"><table>
  <thead><tr><th class="c">#</th><th>指摘</th><th>是正</th><th>確認結果</th></tr></thead>
  <tbody>
   <tr><td class="c t-ok">A</td><td>TMDS用ESD（C293965、DOWO製）の入力・出力が内部でつながる保証がない</td><td>ESDの入力側ピン（1/2/4/5）と出力側ピン（10/9/7/6）を、<b>基板上の銅の細線で接続</b>し、線路は常に連続した銅配線にした。ESDは分岐（タップ）。内部導通があっても無くても成立する</td><td>銅だけで Core のパッド → コネクタのパッドに到達（<code>check_continuity.py</code>）：<b>%(cont)s</b>。P/Nの上下順（Core側とコネクタ側）：下表</td></tr>
   <tr><td class="c t-warn">B</td><td>499Ω抵抗の枝が長い（21〜53mm、CKNは53.5mm）</td><td>抵抗の位置を固定し、枝をTMDSの直後・サイドバンド線より先に配線。枝は解析から除外せず、実長で<b>終端付き線路</b>としてモデル化</td><td>枝 %(bmin).1f〜%(bmax).1fmm（以前21〜53mm）。D1のN側が%(d1n).1fmmで目標（数mm以下）未達。P/Nの長さは非対称（モード変換は未評価）</td></tr>
   <tr><td class="c t-ok">C</td><td>目標速度：1080p60はGW2Aのシリアライザ上限を超える</td><td>目標を<b>720p60</b>に限定（記録・ページを訂正済み）</td><td>観察帯域は〜1.5GHz（720pのNyquist 371MHz、742Mbps）</td></tr>
   <tr><td class="c t-ok">D</td><td>解析コード・記録の精度（区間の並び順、間隔の丸め、枝のメタデータ欠落、ESD容量、層のモデル化）</td><td>区間を配線の接続順にたどる方式／間隔0.13mmを補間して直接使用／枝と主経路を<b>ルータが直接出力</b>（<code>tmds_roles.json</code>）／ESD容量は0.2〜0.5pFを感度範囲に／全層を同じマイクロストリップ表で近似（仮定として明記）</td><td>下記の各節</td></tr>
  </tbody></table></div>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">P/Nの上下順がCore側とコネクタ側で一致</th></tr></thead>
  <tbody>
""" + rows_pol + """  </tbody></table></div>
 <p>D2はTX5のP/Nを物理的に入れ替えて接続しています。FPGA側で、TMDSエンコード後・差動バッファ前の<b>全シリアルビット</b>を反転して補償してください（RGB値の反転とは異なります。クロックでは使えません）。</p>
</section>

<section id="scope">
 <h2>2. 範囲と基準</h2>
 <div class="tw"><table>
  <thead><tr><th>区間</th><th>扱い</th><th>理由</th></tr></thead>
  <tbody>
   <tr><td>キャリア基板</td><td><b>実形状から解析</b>（主対象）</td><td>自分たちの設計物</td></tr>
   <tr><td>Core基板内</td><td>理想100Ω線路（38.4mm）。85〜115Ωを感度解析</td><td>配線データは未取得（公開を確認できず）。公式配線長表のみ。長さ一致は100Ωの証明にならない。TX4はN側が1.9mm短いため不使用</td></tr>
   <tr><td>SODIMM接点</td><td>集中定数の感度解析</td><td>公式に電気特性データなし</td></tr>
   <tr><td>HDMIコネクタ</td><td>100Ω・11mmの理想線路</td><td>実形状モデルなし</td></tr>
   <tr><td>ケーブル・シンク</td><td>対象外</td><td>HDMIの測定はコネクタ端子で行う規定</td></tr>
  </tbody></table></div>
 <div class="tw"><table>
  <thead><tr><th>項目</th><th>基準</th><th>根拠</th></tr></thead>
  <tbody>
   <tr><td>差動インピーダンス</td><td>100Ω ±15%（85〜115Ω）</td><td>HDMI 1.4 のTMDS線路の一般的な要求</td></tr>
   <tr><td>ペア内スキュー</td><td>5mm未満（自主目標）。参考：720p60の0.15×Tbit ≒ 200ps</td><td>TI SLLA414A §2.3：ペア内0.15×Tbit、ペア間0.20×Tcharacter。5mmは保守的な自主値</td></tr>
   <tr><td>SDD11（反射）</td><td>−10dB以下（〜1.5GHz）</td><td>自主目標（規格値ではない）</td></tr>
   <tr><td>SDD21（挿入損失）</td><td>1dB程度以内（742MHz）</td><td>自主目標</td></tr>
   <tr><td>対象速度</td><td><b>720p60（0.74Gbps/レーン）</b>。1080p60は保証対象外</td><td>GW2Aのシリアライザ上限1200Mbps（DS102 Table 3-17）を超える</td></tr>
  </tbody></table></div>
</section>

<section id="method">
 <h2>3. 手法とツール</h2>
 <div class="tw"><table>
  <thead><tr><th>層</th><th>手法</th><th>実装</th><th>状態</th></tr></thead>
  <tbody>
   <tr><td>(a) 解析式</td><td>IPC-2141／Hammerstad式</td><td>手計算</td><td>検証の基準値</td></tr>
   <tr><td>(b) 2D準静的</td><td>有限差分でラプラス方程式を解き、容量行列から Z0／偶奇モード／εeff</td><td><code>microstrip2d.py</code>（自作）</td><td class="t-ok">主力</td></tr>
   <tr><td>(c) チャネル推定</td><td>配線を0.1mm刻みの区間に分け、局所の差動インピーダンスでABCD行列をカスケード。ESDは分岐点の並列容量、499Ωは終端付き線路の枝として実長・実位置で挿入。損失は tanδ 0.02 と表皮効果</td><td><code>tmds_channel.py</code>, <code>tmds_sparam.py</code></td><td class="t-ok">主力</td></tr>
   <tr><td>(d) 銅の連続性チェック</td><td>KiCadの接続グラフで、銅（配線・ビア・パッド）だけを通って到達できるかを確認</td><td><code>check_continuity.py</code></td><td class="t-ok">新規</td></tr>
   <tr><td>(e) 3D電磁界</td><td>FDTD（openEMS 0.37.0）</td><td><code>openems_*.py</code></td><td class="t-warn">較正中（8章）</td></tr>
  </tbody></table></div>
 <h3>スタックアップ（想定）</h3>
 <p>JLCPCB 4層 JLC04161H-7628（1.6mm）：L1 銅35µm／プリプレグ 0.2104mm（εr 4.4）／L2／コア 1.065mm／L3／プリプレグ 0.2104mm／L4。ソルダマスクは無視。<b>発注時にこの積層（インピーダンス管理）を指定する必要があります。</b></p>
 <h3>モデルの前提・簡略化</h3>
 <ul>
  <li>差動モードのみ（コモン⇔差動のモード変換は評価しない。P/Nの枝の長さが違う分は未評価）。</li>
  <li>全ての銅層を、F.Cuのマイクロストリップの表で近似（<b>仮定</b>。In2.Cu・B.Cuは実際の帰路が異なる）。ビアの寄生は未考慮。</li>
  <li>AC結合キャップは ESL 1.4nH（差動）。ESDは信号線への分岐の並列容量として、差動0.2〜0.5pF（基準0.35pF）を<b>仮定の感度範囲</b>で使用（DOWO資料：I/O−GND 0.4〜0.5pF、I/O−I/O 0.2〜0.3pF）。</li>
  <li>499Ωの枝：0.127mm幅（単線約85Ω）の線路＋499Ω終端。P/Nの枝は、線路対地の直列合成（Y_P·Y_N/(Y_P+Y_N)）で差動の並列負荷にした。</li>
 </ul>
</section>

<section id="valid">
 <h2>4. 2Dソルバの検証</h2>
 <div class="tw"><table>
  <thead><tr><th>ケース</th><th class="c">2Dソルバ</th><th class="c">解析式</th><th>参考</th></tr></thead>
  <tbody>
   <tr><td>単線 w=0.35mm</td><td class="c">51.7Ω</td><td class="c">IPC式 約50.0Ω</td><td>JLCPCB公表 50Ω用（0.35mm前後）と一致</td></tr>
   <tr><td>単線 w=0.20mm</td><td class="c">66.2Ω</td><td class="c">IPC式 67.2Ω</td><td>—</td></tr>
   <tr><td>差動 w=0.20／間隔0.13mm</td><td class="c">約103〜104Ω</td><td class="c">IPC-2141差動式 約98.7Ω</td><td>式は概算（±10%程度）。以前の107Ωは0.15mmの値の代用だった（訂正済み）</td></tr>
  </tbody></table></div>
 <p>単線は±3%で一致。2Dソルバと概算式の一致をもって、保証できる誤差とは言いません。差動値は<b>約±8%の不確かさ</b>を見込みます。</p>
 <figure><img src="img/sim_zdiff_r2.png" alt="差動インピーダンスと線幅・間隔" """ + IMG + """>
  <figcaption>図1　差動インピーダンスと線幅・ペア内間隔（2Dソルバ）。採用した線幅0.2mm・間隔0.13mmは100Ω付近。</figcaption></figure>
</section>

<section id="result">
 <h2>5. 配線の結果（是正後）</h2>
 <p>P/Nを1本の太い線として引いて2本に分けるペア配線です。Core側は入れ子の縦レーン、キャップ→ESD→コネクタは直線レーン。ESDの足は銅の細線でつないであり、線路は連続した銅配線です。</p>
 <figure><img src="img/sim_compare_r2.png" alt="導入前後の比較" """ + IMG + """>
  <figcaption>図2　配線方式による改善（最初の配線との比較）。</figcaption></figure>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">P/N長 (mm)</th><th class="c">スキュー</th><th class="c">Zdiff 最小/平均 (Ω)</th><th class="c">499Ω枝 P/N</th><th class="c">F.Cu結合割合</th></tr></thead>
  <tbody>
""" + rows_len + """  </tbody></table></div>
 <figure><img src="img/sim_route_r2.png" alt="TMDS実配線" """ + IMG + """>
  <figcaption>図3　TMDS 4組の実配線（細線=P、太線=N、黒細線=499Ω枝）。</figcaption></figure>
 <figure><img src="img/render_top_r2.png" alt="基板3Dレンダリング" """ + IMG + """>
  <figcaption>図4　基板全体（右辺の上寄りがHDMI）。DRC違反0件、未接続0件。</figcaption></figure>
</section>

<section id="channel">
 <h2>6. チャネル推定（Sパラメータ）</h2>
 <p>Core基板内（理想100Ω・38.4mm）、キャリア基板の実配線、AC結合キャップ、ESD（0.35pF）、499Ω枝、コネクタ（100Ω・11mm）をカスケードしました（差動モード、基準100Ω）。観察帯域は720p60に合わせ、〜1.5GHzまでを見ています。</p>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">SDD11 371/742MHz</th><th class="c">SDD11 最大(〜1.5GHz)</th><th class="c">SDD21 371/742MHz</th><th class="c">SDD21 1.5GHz</th></tr></thead>
  <tbody>
""" + rows_sp + """  </tbody></table></div>
 <figure><img src="img/sim_sparam_r2.png" alt="Sパラメータ推定" """ + IMG + """>
  <figcaption>図5　差動S11／S21の推定と、Core側配線の差動インピーダンス。先頭の約2.4mmはパッド直後の細い単線スタブ。</figcaption></figure>
 <p>499Ωの対地抵抗だけで、差動998Ωの並列負荷になり、SDD21が約−0.4dB下がります（理想の系との差）。「直流のみで影響しない」という以前の扱いは誤りでした。</p>
</section>

<section id="variants">
 <h2>7. 是正の効果と、仮定値に対する感度</h2>
 <div class="tw"><table>
  <thead><tr><th>条件（4組のうち悪い方）</th><th class="c">SDD11 最大(〜1.5GHz)</th><th class="c">SDD21 @742MHz</th></tr></thead>
  <tbody>
""" + rows_var + """  </tbody></table></div>
 <figure><img src="img/sim_variants_r2.png" alt="是正の効果と感度" """ + IMG + """>
  <figcaption>図6　是正前の枝（21〜53mm）では反射が約−4dBまで悪化。是正後は理想に近い。ESD容量とCore側インピーダンスの仮定に対する感度。</figcaption></figure>
 <ul>
  <li>是正前の枝のままだと、SDD11が−4.2dB、SDD21が−2.6dBまで悪化する（<b>是正の効果は大きい</b>）。</li>
  <li>ESD容量が仮定の上限（0.5pF）、またはCoreが85Ωだと、−10dBの自主目標に近づく（−13.1dB／−11.1dB）。Coreの実インピーダンスは不明。</li>
 </ul>
 <h3>SODIMM接点の寄生</h3>
 <figure><img src="img/sim_sensitivity_r2.png" alt="接点の感度解析" """ + IMG + """>
  <figcaption>図7　SODIMM接点の直列L（差動）と並列C（差動）に対する反射（左）と挿入損失（右）。実機の値は確認できていない。</figcaption></figure>
</section>

<section id="em3d">
 <h2>8. 3D電磁界解析（openEMS）の状況</h2>
 <p>openEMS 0.37.0（公式配布のWindows版、専用の環境）を導入しましたが、<b>較正が済んでいないため結論には使っていません</b>。</p>
 <div class="tw"><table>
  <thead><tr><th>ケース</th><th class="c">openEMS</th><th class="c">2D／解析式</th><th class="c">差</th></tr></thead>
  <tbody>
   <tr><td>単線 w=0.35mm、メッシュ0.1mm</td><td class="c">47.7Ω</td><td class="c">51.7／50.0Ω</td><td class="c">−8%</td></tr>
   <tr><td>単線 w=0.35mm、メッシュ0.05mm</td><td class="c">47.9Ω</td><td class="c">同上</td><td class="c">−8%（収束済み）</td></tr>
   <tr><td>差動 w=0.2／間隔0.13mm、メッシュ0.1mm</td><td class="c">75.3Ω</td><td class="c">約104／98.7Ω</td><td class="c t-bad">−22〜24%</td></tr>
  </tbody></table></div>
 <p>3D側の設定（ポート定義、境界条件、基準面、抽出式）に系統的な誤りがある可能性が高く、2D値に合うまで調整することは検証ではありません。解決の手順は、既知例での再現確認、導波管ポートへの変更、PML境界、抽出方法の見直しです。</p>
</section>

<section id="limits">
 <h2>9. 限界と残課題</h2>
 <div class="tw"><table>
  <thead><tr><th>事項</th><th>状況・対応</th></tr></thead>
  <tbody>
   <tr><td>499Ω枝の短縮（D1のN側 %(d1n).1fmm ほか）</td><td>数mm以下の目標は未達。P/Nの枝長が非対称。次版で抵抗の配置を見直す。それまでは終端付き線路として評価に含める</td></tr>
   <tr><td>ESDの実フットプリント</td><td>DOWO DFN2510-10L（端子は0.2×0.38mm）。KiCad標準のUSON-10パッドで代用しており、<b>製作前にメーカーの推奨ランドパターンと照合</b>する</td></tr>
   <tr><td>Core基板内・SODIMM接点の実特性</td><td>感度解析で範囲を提示。公式Dock（同じCore・同じ構成）との比較測定が有効</td></tr>
   <tr><td>内層・ビア・モード変換</td><td>3D解析の較正後に確認</td></tr>
   <tr><td>積層指定</td><td>JLC04161H-7628（インピーダンス管理）を発注時に指定</td></tr>
   <tr><td>製作後の最低限の成功条件（PoC）</td><td>短いケーブル・限定モニタで、640×480→720p60の固定パターンを30分程度表示（点滅・色化け・同期抜けなし）。720pが不安定なら「低速PoC成功・720p未達」と記録。1080p60の失敗を基板不良とは判定しない</td></tr>
  </tbody></table></div>
</section>

<section id="repro">
 <h2>10. 再現手順と記録</h2>
 <ul>
  <li>方針・前提・判断の記録（監査用）：<a href="%(GH)s%(AUD)s">docs/シミュレーション方針と監査記録.md</a>（§10に今回の是正と再評価）</li>
  <li>調査と設計判断の経緯：<a href="%(GH)s%(HDOC)s">docs/HDMI_信号品質_調査と方針.md</a></li>
  <li>ソース：<a href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/tree/main/kicad/sim">kicad/sim/</a></li>
 </ul>
 <div class="tw"><table>
  <thead><tr><th>コマンド</th><th>内容</th></tr></thead>
  <tbody>
   <tr><td><code>kicad/gen/make_pcb.py</code></td><td>配置・配線（<code>tmds_roles.json</code>＝主経路と枝を出力）</td></tr>
   <tr><td><code>check_continuity.py</code>（KiCad python）</td><td>銅だけでの連続性・P/N順</td></tr>
   <tr><td><code>tmds_channel.py --extract</code>、<code>tmds_channel.py</code></td><td>実配線の抽出、区間の差動インピーダンス・長さ・スキュー</td></tr>
   <tr><td><code>tmds_sparam.py</code>、<code>make_report_figs.py</code>、<code>make_report_page.py</code></td><td>Sパラメータ推定、図、このページ</td></tr>
  </tbody></table></div>
 <p>使用環境：KiCad 10.0.6、Python 3.12（numpy 2.5.3、scipy 1.18.1、matplotlib 3.11.2）、openEMS 0.37.0（専用のPython 3.13環境）。</p>
 <h3>訂正記録</h3>
 <ul>
  <li>2026-10-24（再提出）：監査指摘A・Bを是正。ESDを銅配線の分岐に変更、499Ω枝を短縮して解析に含めた。チャネル推定は枝・ESD容量の範囲・Core側の感度を含む形に更新。以前の「合格（推定）」の表現は取り下げた。</li>
  <li>2026-10-24：結合区間の差動インピーダンスを107Ω→103〜104Ωに訂正（間隔0.13mmの補間）。区間の並びを信号経路順に修正。</li>
 </ul>
</section>

</main>
<footer><div class="wrap">Tab5 × Tang Primer 20K キャリア基板 ／ HDMIシミュレーション評価（是正後）／ 2026-10-24</div></footer>
</body>
</html>
"""
subs = dict(zmin=zmin, w11=worst11, w21=worst21, cont=cont_ok, GH=GH, AUD=AUD, HDOC=HDOC,
            bmin=min(min(summ[k]["branch_C"]) for k in PAIRS), bmax=max(max(summ[k]["branch_C"]) for k in PAIRS),
            d1n=summ["D1"]["branch_C"][1])
# placeholders written as %(name).Nf / %(name)s: substitute explicitly (the text contains literal percent signs)
import re
def sub_ph(m):
    name, fmt = m.group(1), m.group(2)
    return ("%" + fmt) % subs[name]
page = re.sub(r"%\((\w+)\)([-.\d]*[sf])", sub_ph, page)
page = page.replace("%%", "%")
open(os.path.join(SITE, "hdmi-simulation-r2.html"), "w", encoding="utf-8").write(page)
print("wrote site/hdmi-simulation-r2.html")
