"""Builds site/hdmi-simulation.html from the simulation outputs and links it from site/index.html (idempotent).

python -X utf8 kicad/sim/make_report_page.py   (after make_report_figs.py)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "..", "site")
idx = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
style = idx[idx.index("<style>"):idx.index("</style>") + 8]
rs = json.load(open(os.path.join(HERE, "report_sparam.json")))
sp = json.load(open(os.path.join(HERE, "tmds_sparam.json")))
rows = "".join(
    '<tr><td>%s</td><td class="c">%.1f / %.1f / %.1f</td><td class="c">0.00</td><td class="c">%.1f / %.1f dB</td><td class="c">%.1f dB</td><td class="c">%.2f / %.2f dB</td></tr>\n'
    % (k, sp[k]["len_mm"]["core"], sp[k]["len_mm"]["C"], sp[k]["len_mm"]["K"], rs[k]["s11_825"], rs[k]["s11_1650"], rs[k]["s11_max"],
       rs[k]["s21_825"], rs[k]["s21_1650"]) for k in rs)
GH = "https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/"
AUD = "docs/%E3%82%B7%E3%83%9F%E3%83%A5%E3%83%AC%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E6%96%B9%E9%87%9D%E3%81%A8%E7%9B%A3%E6%9F%BB%E8%A8%98%E9%8C%B2.md"
HDOC = "docs/HDMI_%E4%BF%A1%E5%8F%B7%E5%93%81%E8%B3%AA_%E8%AA%BF%E6%9F%BB%E3%81%A8%E6%96%B9%E9%87%9D.md"
IMG = 'style="width:100%;height:auto;display:block;border-radius:6px"'

page = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HDMI信号品質 シミュレーション評価レポート</title>
<meta name="description" content="Tab5 × Tang Primer 20K キャリア基板のHDMI（TMDS）配線のシミュレーション評価。方針、手法、結果、限界。">
""" + style + """
</head>
<body>
<header class="top"><div class="wrap">
 <p><span class="badge">シミュレーション評価レポート</span><span class="badge">推定値（3D解析は較正中）</span></p>
 <h1>HDMI信号品質 シミュレーション評価</h1>
 <p class="sub">キャリア基板 v2.0（コミット 7a0a3c5）の TMDS 4 組を、実際の配線データから評価。更新：2026-10-24　／　<a href="index.html">← 企画・設計仕様に戻る</a></p>
</div></header>
<nav class="toc"><div class="wrap">
 <a href="#summary">結論</a><a href="#scope">範囲</a><a href="#method">手法</a><a href="#valid">検証</a><a href="#result">配線結果</a><a href="#channel">チャネル推定</a><a href="#sens">感度解析</a><a href="#em3d">3D解析</a><a href="#limits">限界</a><a href="#repro">再現・記録</a>
</div></nav>
<main class="wrap">

<section id="summary">
 <h2>結論</h2>
 <div class="kpi">
  <div><b>0.00 mm</b><span>ペア内スキュー（4組すべて。目標 5mm 未満）</span></div>
  <div><b>約104 Ω</b><span>結合区間の差動インピーダンス（目標 100Ω ±15%）</span></div>
  <div><b>≤ −14.4 dB</b><span>SDD11（〜1.65GHz、最悪の CK）</span></div>
  <div><b>−0.9 dB 以内</b><span>SDD21 @1.65GHz（挿入損失）</span></div>
 </div>
 <div class="callout ok"><b class="t">設計上の判断</b>最初の配線（P/Nを個別に配線）は不合格（差動インピーダンス約160Ω、スキュー最大13mm）でした。P/Nを1本の太い線として引いて2本に分けるペア配線をルータに実装し、<b>4組すべてが設計目標内</b>に入りました（推定値）。</div>
 <div class="callout warn"><b class="t">この結果の位置づけ</b>準静的モデルとチャネルのカスケード計算による<b>推定</b>です。実形状の3D電磁界解析（openEMS）は導入済みですが、<b>較正が済んでいないため結論には使っていません</b>（7章）。最終判断は試作基板の実測（TDR・アイ）で行います。</div>
</section>

<section id="scope">
 <h2>1. 評価の範囲と合否基準</h2>
 <p>信号の全経路は「FPGA → Core基板内配線 → SODIMM接点 → <b>キャリア基板</b> → HDMIコネクタ →（ケーブル → シンク）」です。範囲は次のとおり決めました。</p>
 <div class="tw"><table>
  <thead><tr><th>区間</th><th>扱い</th><th>理由</th></tr></thead>
  <tbody>
   <tr><td>キャリア基板</td><td><b>実形状から解析</b>（主対象）</td><td>自分たちの設計物</td></tr>
   <tr><td>Core基板内</td><td>理想100Ω線路（長さ38.4mm）</td><td>配線データは非公開。公式の配線長表のみ入手可。TX1/2/3/5は1510 mil ±5 mil、<b>TX4だけN側が1.9mm短い</b>ため不使用</td></tr>
   <tr><td>SODIMM接点</td><td><b>集中定数の感度解析</b></td><td>公式に電気特性データなし（6章）</td></tr>
   <tr><td>HDMIコネクタ</td><td>100Ω・11mmの理想線路</td><td>実形状モデルなし</td></tr>
   <tr><td>ケーブル・シンク</td><td>対象外</td><td>HDMIの測定はコネクタ端子で行う規定</td></tr>
  </tbody></table></div>
 <p>公式 Tang Primer 20K Dock の回路図（HDMIの構成：100nF AC結合、499Ω、RCLAMP0524P、SRV05-4）は採用しましたが、<b>公式の基板配線データは非公開</b>のため、配線品質の直接比較はできません。</p>
 <h3>合否基準</h3>
 <div class="tw"><table>
  <thead><tr><th>項目</th><th>基準</th><th>根拠</th></tr></thead>
  <tbody>
   <tr><td>差動インピーダンス</td><td>100Ω ±15%（85〜115Ω）</td><td>HDMI 1.4 のTMDS線路の一般的な要求</td></tr>
   <tr><td>ペア内スキュー</td><td>5mm未満（約30ps）</td><td>HDMI設計ガイドの一般値</td></tr>
   <tr><td>SDD11（反射）</td><td>−10dB以下（〜1.65GHz）</td><td>自主目標（規格値ではない）</td></tr>
   <tr><td>SDD21（挿入損失）</td><td>1dB程度以内</td><td>自主目標</td></tr>
   <tr><td>対象速度</td><td>720p60（0.74Gbps/レーン）〜1080p60（1.49Gbps/レーン）</td><td>初版の想定</td></tr>
  </tbody></table></div>
</section>

<section id="method">
 <h2>2. 手法とツール</h2>
 <div class="tw"><table>
  <thead><tr><th>層</th><th>手法</th><th>実装</th><th>状態</th></tr></thead>
  <tbody>
   <tr><td>(a) 解析式</td><td>IPC-2141／Hammerstad式</td><td>手計算</td><td>検証の基準値</td></tr>
   <tr><td>(b) 2D準静的</td><td>有限差分でラプラス方程式を解き、容量行列から Z0／偶奇モード／εeff</td><td><code>kicad/sim/microstrip2d.py</code>（自作）</td><td class="t-ok">主力</td></tr>
   <tr><td>(c) チャネル推定</td><td>配線を0.1mm刻みの区間に分け、局所の差動インピーダンスでABCD行列をカスケード。損失は tanδ 0.02 と表皮効果</td><td><code>kicad/sim/tmds_channel.py</code>, <code>tmds_sparam.py</code></td><td class="t-ok">主力</td></tr>
   <tr><td>(d) 3D電磁界</td><td>FDTD（openEMS 0.37.0）</td><td><code>kicad/sim/openems_*.py</code></td><td class="t-warn">較正中（7章）</td></tr>
  </tbody></table></div>
 <h3>スタックアップ（想定）</h3>
 <p>JLCPCB 4層 JLC04161H-7628（1.6mm）：L1 銅35µm／プリプレグ 0.2104mm（εr 4.4）／L2／コア 1.065mm／L3／プリプレグ 0.2104mm／L4。ソルダマスクは無視（差動インピーダンスを1〜3Ω下げる方向）。<b>発注時の積層指定が一致することの確認が必要</b>です。</p>
 <h3>モデルの前提・簡略化</h3>
 <ul>
  <li>差動モードのみ（コモン⇔差動のモード変換は評価しない）。</li>
  <li>F.Cuの区間だけ2Dで解く。In2.Cu・B.Cuの区間とビアは100Ωの線路として扱う（ビアの寄生は未考慮）。</li>
  <li>AC結合キャップは ESL 1.4nH（差動）、ESDは差動0.15pF。</li>
  <li>499Ωバイアス抵抗の枝配線は信号経路から除外（直流のみで、高周波では開放に近い）。</li>
 </ul>
</section>

<section id="valid">
 <h2>3. 2Dソルバの検証</h2>
 <div class="tw"><table>
  <thead><tr><th>ケース</th><th class="c">2Dソルバ</th><th class="c">解析式</th><th>参考</th></tr></thead>
  <tbody>
   <tr><td>単線 w=0.35mm</td><td class="c">51.7Ω</td><td class="c">IPC式 約50.0Ω</td><td>JLCPCB公表 50Ω用（0.35mm前後）と一致</td></tr>
   <tr><td>単線 w=0.20mm</td><td class="c">66.2Ω</td><td class="c">IPC式 67.2Ω</td><td>—</td></tr>
   <tr><td>差動 w=0.20／間隔0.13mm</td><td class="c">104Ω</td><td class="c">IPC-2141差動式 約98.7Ω</td><td>式は概算（±10%程度）</td></tr>
  </tbody></table></div>
 <p>単線は±3%で一致し、差動の差（5%）は式自体の精度の範囲です。<b>差動値は約±8%の不確かさ</b>を見込んでいます。</p>
 <figure><img src="img/sim_zdiff.png" alt="差動インピーダンスと線幅・間隔" """ + IMG + """>
  <figcaption>図1　差動インピーダンスと線幅・ペア内間隔（2Dソルバ）。採用した線幅0.2mm・間隔0.13mmは100Ω付近。従来の最小幅0.127mmでは、結合させても120Ω超になる。</figcaption></figure>
</section>

<section id="result">
 <h2>4. 配線の結果（ペア配線の導入前後）</h2>
 <p>最初の配線は、P/Nを別々に引いていたため並走せず（結合区間5〜7%）、差動インピーダンスが約160Ω、ペア内スキューが最大13mmでした。ルータに<b>ペア配線</b>（P/Nを1本の太い線として引いて2本に分割）を実装しました。</p>
 <figure><img src="img/sim_compare.png" alt="導入前後の比較" """ + IMG + """>
  <figcaption>図2　配線方式による改善。</figcaption></figure>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">P/N長 (mm)</th><th class="c">スキュー</th><th class="c">結合区間 Zdiff</th><th class="c">F.Cu上の結合割合</th></tr></thead>
  <tbody>
   <tr><td>D0（TX2）</td><td class="c">53.2 / 53.2</td><td class="c">0.00 mm</td><td class="c">約104Ω</td><td class="c">89%</td></tr>
   <tr><td>D1（TX3）</td><td class="c">35.2 / 35.2</td><td class="c">0.00 mm</td><td class="c">約104Ω</td><td class="c">83%</td></tr>
   <tr><td>D2（TX5、P/N入替）</td><td class="c">35.3 / 35.3</td><td class="c">0.00 mm</td><td class="c">約104Ω</td><td class="c">83%</td></tr>
   <tr><td>CK（TX1）</td><td class="c">53.9 / 53.9</td><td class="c">0.00 mm</td><td class="c">約104Ω</td><td class="c">77%</td></tr>
  </tbody></table></div>
 <figure><img src="img/sim_route.png" alt="TMDS実配線" """ + IMG + """>
  <figcaption>図3　TMDS 4組の実配線。Core側は入れ子の縦レーン、キャップ→ESD→コネクタは直線レーン。D2・D1・D0・CKの順で、ペアが交差しない。</figcaption></figure>
 <figure><img src="img/render_top.png" alt="基板3Dレンダリング" """ + IMG + """>
  <figcaption>図4　基板全体（右辺の上寄りがHDMI）。DRC違反0件、未接続0件。</figcaption></figure>
</section>

<section id="channel">
 <h2>5. チャネル推定（Sパラメータ）</h2>
 <p>Core基板内（理想100Ω・38.4mm）、キャリア基板の実配線、AC結合キャップ、ESD、コネクタ（100Ω・11mm）をカスケードしました（差動モード、基準100Ω）。</p>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">キャリア長 Core側/C/K (mm)</th><th class="c">ペア内スキュー (mm)</th><th class="c">SDD11 0.825/1.65GHz</th><th class="c">SDD11 最大(〜3.3GHz)</th><th class="c">SDD21 0.825/1.65GHz</th></tr></thead>
  <tbody>
""" + rows + """  </tbody></table></div>
 <figure><img src="img/sim_sparam.png" alt="Sパラメータ推定" """ + IMG + """>
  <figcaption>図5　差動S11／S21の推定と、Core側配線の差動インピーダンスの分布。区間の先頭（Core側）の約2.4mmはパッド直後の細い単線スタブ（約150Ω）、その後が結合区間（約104Ω）。</figcaption></figure>
 <p>反射は全帯域で−12.8dB以下、挿入損失は1.65GHzで−0.9dB以内でした。最悪はCKの1.65GHz付近（−14.4dB）で、Core側スタブとキャップのインダクタンスの影響です。</p>
</section>

<section id="sens">
 <h2>6. 感度解析：コネクタ接点の反射への余裕</h2>
 <p>SODIMM接点の寄生（直列L、並列C）は公式にデータが無いため、値を振って余裕を確認しました。<b>接点を理想とした場合</b>の最悪SDD11は−14.4dBです。</p>
 <figure><img src="img/sim_sensitivity.png" alt="感度解析" """ + IMG + """>
  <figcaption>図6　SODIMM接点の直列L（差動）と並列C（差動）に対する、4組のうち悪い方の反射（左）と挿入損失（右）。</figcaption></figure>
 <ul>
  <li>反射−10dBを保てる並列Cは、直列Lが0のとき約<b>0.4pF</b>まで、3nHのとき約0.65pFまで。</li>
  <li>並列Cが約1pFを超えると、挿入損失が1.65GHzで1.5dBを超える。</li>
  <li>実機のソケット接点の寄生値は<b>確認できていない</b>。</li>
 </ul>
 <div class="callout warn"><b class="t">この感度解析の意味</b>接点の寄生が上の範囲を超えると、反射の目標を満たさなくなる可能性があります。公式Dockは同じCore・同じソケットで動作しているので、同等の構成であれば大きな問題は起きにくいと考えますが、<b>キャリア側のESD・キャップの付加容量が公式より多い可能性</b>があります。試作でのTDR測定で確認します。</div>
</section>

<section id="em3d">
 <h2>7. 3D電磁界解析（openEMS）の状況</h2>
 <p>実形状の評価のため、openEMS 0.37.0（公式配布のWindows版）を導入しました。専用の環境に置き、プロジェクトには含めていません。ただし<b>較正が済んでいないため、結論には使っていません</b>。</p>
 <div class="tw"><table>
  <thead><tr><th>ケース</th><th class="c">openEMS</th><th class="c">2D／解析式</th><th class="c">差</th></tr></thead>
  <tbody>
   <tr><td>単線 w=0.35mm、メッシュ0.1mm</td><td class="c">47.7Ω</td><td class="c">51.7／50.0Ω</td><td class="c">−8%</td></tr>
   <tr><td>単線 w=0.35mm、メッシュ0.05mm</td><td class="c">47.9Ω</td><td class="c">同上</td><td class="c">−8%（収束済み）</td></tr>
   <tr><td>差動 w=0.2／間隔0.13mm、メッシュ0.1mm</td><td class="c">75.3Ω</td><td class="c">104／98.7Ω</td><td class="c t-bad">−22〜24%</td></tr>
  </tbody></table></div>
 <p>3Dの値は、メッシュを細かくしても変わらず、2Dと解析式のどちらとも一致しません。<b>3D側の設定（ポート定義、境界条件、基準面、抽出式）に系統的な誤りがある可能性</b>があります。解決の手順は、①公式チュートリアルの既知例で再現確認、②導波管ポートへの変更、③境界のPML化、④抽出方法の見直しです。</p>
</section>

<section id="limits">
 <h2>8. 限界と次の作業</h2>
 <div class="tw"><table>
  <thead><tr><th>未確認事項</th><th>対応</th></tr></thead>
  <tbody>
   <tr><td>3D電磁界解析の較正</td><td>7章の手順で解決後、ビア・ESD・コネクタ接続部を評価</td></tr>
   <tr><td>SODIMM接点とCore基板内の実特性</td><td>感度解析で許容範囲を提示。試作でTDR測定</td></tr>
   <tr><td>ビア・内層区間（100Ω近似）、モード変換</td><td>3D解析で確認</td></tr>
   <tr><td>積層構成が発注と一致するか</td><td>発注時にJLC04161H-7628を指定し、層厚を確認</td></tr>
   <tr><td>最終判断</td><td><b>試作基板でのTDRとアイパターン測定</b></td></tr>
  </tbody></table></div>
</section>

<section id="repro">
 <h2>9. 再現手順と記録</h2>
 <ul>
  <li>方針・前提・判断の記録（監査用）：<a href="%(GH)s%(AUD)s">docs/シミュレーション方針と監査記録.md</a></li>
  <li>調査と設計判断の経緯：<a href="%(GH)s%(HDOC)s">docs/HDMI_信号品質_調査と方針.md</a></li>
  <li>ソース：<a href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/tree/main/kicad/sim">kicad/sim/</a></li>
 </ul>
 <div class="tw"><table>
  <thead><tr><th>コマンド</th><th>内容</th></tr></thead>
  <tbody>
   <tr><td><code>kicad python tmds_channel.py --extract</code></td><td>基板から配線を抽出</td></tr>
   <tr><td><code>python tmds_channel.py</code></td><td>区間の差動インピーダンス・長さ・スキュー</td></tr>
   <tr><td><code>python tmds_sparam.py</code></td><td>Sパラメータ推定</td></tr>
   <tr><td><code>python make_report_figs.py</code></td><td>このページの図</td></tr>
  </tbody></table></div>
 <p>使用環境：KiCad 10.0.6、Python 3.12（numpy 2.5.3、scipy 1.18.1、matplotlib 3.11.2）、openEMS 0.37.0（専用のPython 3.13環境）。</p>
 <h3>訂正記録</h3>
 <ul>
  <li>2026-10-24：結合区間の差動インピーダンスを107Ω→104Ωに訂正（2Dの解の格子に実際の間隔0.13mmを追加）。チャネル推定の区間の並びを信号経路順に修正。合否判断は変わらない。</li>
 </ul>
</section>

</main>
<footer><div class="wrap">Tab5 × Tang Primer 20K キャリア基板 ／ HDMIシミュレーション評価 ／ 2026-10-24</div></footer>
</body>
</html>
""".replace("%(GH)s", GH).replace("%(AUD)s", AUD).replace("%(HDOC)s", HDOC)
open(os.path.join(SITE, "hdmi-simulation.html"), "w", encoding="utf-8").write(page)

s = idx
if "hdmi-simulation.html" not in s:
    s = s.replace('<a href="#todo">未解決事項</a>', '<a href="hdmi-simulation.html">HDMIシミュレーション</a><a href="#todo">未解決事項</a>', 1)
    a = " <h3>HDMI信号品質のシミュレーション</h3>"
    assert a in s
    s = s.replace(a, a + '\n <div class="callout ok"><b class="t">詳細レポート</b><a href="hdmi-simulation.html"><b>HDMIシミュレーション評価レポート</b></a>に、範囲・手法・検証・結果・感度解析・限界を表とグラフでまとめました。</div>', 1)
s = s.replace("更新：2026-10-22", "更新：2026-10-24", 1)
open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(s)
print("pages written")

# keep the review patches applied after regeneration
try:
    import apply_review_updates as _a
    _a.page_hdmi()
    _a.page_index()
except Exception as e:  # noqa: BLE001
    print("review updates not applied:", e)

# Preserve the links to the independent audit when regenerating this report.
from make_audit_pages import link_reports
link_reports()
