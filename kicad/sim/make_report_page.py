"""Builds site/hdmi-simulation-r3.html from the simulation outputs (run after make_report_figs.py and make_manifest.py).

python -X utf8 kicad/sim/make_report_page.py
Every number in the tables comes from the JSON files written by the checks / the model (nothing is typed by hand except the text,
the audit baseline values marked as such and the 3D calibration table of the audit).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "..", "site")
idx = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
style = idx[idx.index("<style>"):idx.index("</style>") + 8]
J = lambda n: json.load(open(os.path.join(HERE, n), encoding="utf-8"))      # noqa: E731
summ, sp, var, mat = J("tmds_summary.json"), J("report_sparam.json"), J("report_variants.json"), J("report_matrix.json")
cont, neg, cls, esd, stub = J("continuity_report.json"), J("negative_report.json"), J("classification_report.json"), J("esd_footprint_check.json"), J("report_stub_effect.json")
full, base_sp, man = J("tmds_sparam.json"), J("baseline_r2_report_sparam.json"), J("manifest_r3.json")
drc = J("drc_r3.json")
PAIRS = ["D0", "D1", "D2", "CK"]
GH = "https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/"
IMG = 'style="width:100%;height:auto;display:block;border-radius:6px"'
BASE = man["baseline_commit"]
n_drc = len(drc.get("violations", [])) + len(drc.get("unconnected_items", [])) + len(drc.get("schematic_parity", []))


def tr(*cells, cls_=None):
    return "<tr>" + "".join("<td%s>%s</td>" % (' class="c"' if i else "", c) for i, c in enumerate(cells)) + "</tr>\n"


worst11 = max(sp[k]["s11_max_1500"] for k in PAIRS)
worst21 = min(sp[k]["s21_742"] for k in PAIRS)
worst_sc = max(sp[k]["scd21_max_1500"] for k in PAIRS)
zmin = min(summ[k]["zmin"] for k in PAIRS)
cont_ok = cont["ok"]
neg_ok = neg["ok"]
cls_ok = cls["ok"]
esd_ok = esd["ok"]
bmin = min(min(summ[k]["branch_C"]) for k in PAIRS)
bmax = max(max(summ[k]["branch_C"]) for k in PAIRS)

rows_len = "".join(tr(k, "%.2f / %.2f" % (summ[k]["len_p"], summ[k]["len_n"]), "%.2f mm" % abs(round(summ[k]["skew"], 2)),
                      "%.0f / %.0f" % (summ[k]["zmin"], summ[k]["zmean"]), "%.1f / %.1f mm" % tuple(summ[k]["branch_C"]),
                      "%.0f %%" % summ[k]["coupled"]) for k in PAIRS)
rows_sp = "".join(tr(k, "%.1f / %.1f dB" % (sp[k]["s11_371"], sp[k]["s11_742"]), "%.1f dB" % sp[k]["s11_max_1500"],
                     "%.2f / %.2f dB" % (sp[k]["s21_371"], sp[k]["s21_742"]), "%.2f dB" % sp[k]["s21_1500"],
                     "%.1f dB" % sp[k]["scd21_max_1500"]) for k in PAIRS)
rows_branch = "".join(tr(k, "%.1f / %.1f mm" % tuple(summ[k]["branch_C"]),
                         "%s / %s mm" % (full[k]["branch_tap_s_mm"].get("P", "-"), full[k]["branch_tap_s_mm"].get("N", "-")),
                         "%.1f dB → %.1f dB" % (full[k]["old_approx"]["s11_max_1500"], full[k]["s11_max_1500"]),
                         "%.1f dB → %.1f dB" % (full[k]["old_approx"]["scd21_max_1500"], full[k]["scd21_max_1500"])) for k in PAIRS)
rows_var = "".join(tr(k, "%.1f dB (%s)" % (v["sdd11_max_1500"], v["worst_pair"]), "%.2f dB" % v["sdd21_742"], "%.1f dB" % v["scd21_max_1500"]) for k, v in var.items())
rows_stub = "".join(tr(k, "%.2f → %.2f mm" % (stub["without_stubs"][k]["path_len_mm"], stub["with_stubs"][k]["path_len_mm"]),
                       "%.2f mm" % stub["with_stubs"][k]["in_pad_clipped_mm"],
                       "%.1f → %.1f dB" % (stub["without_stubs"][k]["s11_max_1500"], stub["with_stubs"][k]["s11_max_1500"]),
                       "%.2f → %.2f dB" % (stub["without_stubs"][k]["s21_742"], stub["with_stubs"][k]["s21_742"])) for k in PAIRS)
rows_mat = "".join(tr("%.0f Ω" % c["core_z"], "%.2f pF" % c["esd_cd_pf"], "%.1f dB (%s)" % (c["sdd11_max_1500"], c["worst_pair"]),
                      "%.2f dB" % c["sdd21_742"],
                      ("満たす" if c["sdd11_max_1500"] <= -10 else "<b>外れる</b>"),
                      "%.1f dB (%s)" % (c["sdd11_ideal_branch"], "満たす" if c["sdd11_ideal_branch"] <= -10 else "<b>外れる</b>")) for c in mat)
rows_base = "".join(tr(k, "%.1f dB → %.1f dB" % (base_sp[k]["s11_max_1500"], sp[k]["s11_max_1500"]),
                       "%.2f dB → %.2f dB" % (base_sp[k]["s21_742"], sp[k]["s21_742"])) for k in PAIRS)
rows_pins = "".join(tr(l, ", ".join(r["pins"]["core"]), ", ".join(r["pins"]["connector"]), "一致" if r["pins"]["ok"] else "<b>不一致</b>",
                       "連続" if (r["core"]["ok"] and r["carrier"]["ok"]) else "<b>不連続</b>", ("検出" if neg["cases"][l]["ok"] else "<b>未検出</b>")) for l, r in cont["lines"].items())
rows_cls = "".join(tr(n, v["pcb_segments"], v["pcb_vias"], v["main"], v["stub"], v["strap"], v["branch"]) for n, v in cls["nets"].items())
rows_man = "".join('<tr><td><code>%s</code></td><td><code>%s</code></td></tr>\n' % (k, (v["sha256"] or "(なし)")[:16]) for k, v in man["files"].items())
esd_rows = "".join('<tr><td>%s</td><td class="c">%s</td></tr>\n' % (c["name"], "OK" if c["ok"] else "<b>NG</b>") for c in esd["checks"])

page = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HDMI信号品質 シミュレーション評価レポート（第3版）</title>
<meta name="description" content="Tab5 × Tang Primer 20K キャリア基板のHDMI（TMDS）配線の評価。第2回監査（A1〜A5）への対応、4ポートモデルでの再解析、限界。">
""" + style + """
</head>
<body>
<header class="top"><div class="wrap">
 <p><span class="badge">シミュレーション評価レポート 第3版</span><span class="badge">第2回監査への対応後・再提出版</span><span class="badge">推定値（3D解析は較正未達）</span></p>
 <h1>HDMI信号品質 シミュレーション評価（第3版）</h1>
 <p class="sub">第2回監査（<code>7929491</code> 対象）のA1〜A5への対応。更新：2026-10-24　／　<a href="hdmi-simulation-r2.html">第2版（第2回監査の対象）</a>　<a href="hdmi-simulation.html">第1版</a>　<a href="index.html">← 企画・設計仕様に戻る</a></p>
</div></header>
<nav class="toc"><div class="wrap">
 <a href="#summary">結論</a><a href="#status">対応状況</a><a href="#a1">A1 ESD</a><a href="#a2">A2 経路分類</a><a href="#a3">A3 枝の位置</a><a href="#a4">A4 複合感度</a><a href="#a5">A5 検査・整合</a><a href="#result">配線結果</a><a href="#channel">チャネル推定</a><a href="#em3d">3D解析</a><a href="#limits">限界</a><a href="#repro">再現・記録</a>
</div></nav>
<main class="wrap">

<section id="summary">
 <h2>結論</h2>
 <div class="kpi">
  <div><b>DRC %(drc)d 件</b><span>違反・未配線の合計（113ネット配線済み）</span></div>
  <div><b>≤ %(w11).1f dB</b><span>SDD11 最大（〜1.5GHz、悪い方のペア）</span></div>
  <div><b>%(w21).2f dB</b><span>SDD21 @742MHz（悪い方のペア。499Ω負荷の約−0.4dBを含む）</span></div>
  <div><b>%(wsc).1f dB</b><span>SCD21 最大（〜1.5GHz）：P/N枝の非対称によるモード変換</span></div>
 </div>
 <div class="callout ok"><b class="t">監査指摘への対応</b>A1（ESD実部品の照合）：データシートの寸法とフットプリントを照合し、<b>GND端子のランド幅の不足を修正</b>して専用フットプリントを作成。A2（経路分類）：全TMDS銅（配線・ビア）を主経路／パッドエスケープ／ESDストラップ／枝に分類し、<b>未分類0</b>。<b>これまで解析経路から抜けていた引き出し線（各2.4mm）をモデルに追加</b>。A3：P/Nの枝を<b>別々の位置</b>に接続する4ポートモデルへ変更し、モード変換（SCD21）を評価。A4：Core側Z×ESD容量の複合条件を評価。A5：検査を終了コードで失敗するよう変更し、説明・ハッシュを同一版に揃えた。</div>
 <div class="callout warn"><b class="t">まだ残っていること（隠さずに記載）</b>①<b>複合条件でSDD11の自主目標（−10dB）を外れる条件がある</b>（%(failing)s）。②D1のN側の抵抗枝が%(d1n).1fmm（数mm以下の目標は未達。PoCで残す理由は A3）。③3D解析（openEMS）は較正未達で、設計根拠に使っていない。④ESDのメーカー推奨ランドパターンは入手できない。⑤実機での720p60動作は未確認。目標は<b>短いケーブル・限定モニタでの720p60のPoC</b>で、動作保証・HDMI規格適合を意味しません。</div>
</section>

<section id="status">
 <h2>1. 第2回監査の指示と対応状況</h2>
 <div class="tw"><table>
  <thead><tr><th class="c">#</th><th>指示</th><th>状態</th><th>要点・結果</th></tr></thead>
  <tbody>
   <tr><td class="c">A1</td><td>ESD実部品とフットプリントの照合</td><td class="t-ok">完了（残る制限あり）</td><td>寸法・端子の比較表を保存（<code>docs/ESD_フットプリント照合_RCLAMP0524P.md</code>）。<b>GNDランド幅0.30→0.42mmに修正</b>、専用フットプリント作成、BOM・回路・PCBへ反映。メーカー推奨ランドはデータシートに無い</td></tr>
   <tr><td class="c">A2</td><td>ソケット引き出し線・パッド遷移のモデル化、分類の網羅</td><td class="t-ok">完了</td><td>全トラック・ビアを分類し未分類0。引き出し線をモデルへ追加。パッド内の銅は除外し長さを記録</td></tr>
   <tr><td class="c">A3</td><td>P/N抵抗枝の異なる接続位置</td><td class="t-warn">完了（枝11.5mmは残す）</td><td>4ポートモデルでP/Nを別位置に接続。モード変換を評価。短い対称枝との比較を保存。D1Nの枝は残す理由を記録</td></tr>
   <tr><td class="c">A4</td><td>Core Z × ESD容量の複合感度</td><td class="t-warn">完了（目標を外れる条件あり）</td><td>3×3の結果表を公開。外れる条件と受け入れる不確かさを明記</td></tr>
   <tr><td class="c">A5</td><td>自動検査・説明の整合</td><td class="t-ok">完了</td><td>導通・ピン対応・負の検査・分類・ESD照合が終了コードで失敗する。READMEの数値、対象版、ハッシュ・再生成手順を揃えた</td></tr>
   <tr><td class="c">B1/B2</td><td>3D解析の較正（単線・差動）</td><td class="t-bad">未着手（未達のまま保留）</td><td>今回の作業では実施していない。3Dの数値は設計根拠に使っていない。第2回監査の記録（単線の較正未達）が最新</td></tr>
   <tr><td class="c">C</td><td>MeOS利用に関する未完了事項</td><td class="t-bad">未着手</td><td>8bit双方向PARLIO、電源断・逆給電、最終ネットリストのピン表、GPIO所有権はキャリア要求側の確定事項で、この作業では扱っていない。HDMI修正だけではMeOSでの利用可否は確定しない</td></tr>
  </tbody></table></div>
</section>

<section id="a1">
 <h2>2. A1　ESD実部品とフットプリントの照合</h2>
 <p>購入対象を <b>DOWO RCLAMP0524P（LCSC C293965、DFN2510-10L、データシート Rev.G1.00 2024/03/01）</b>に固定しました。設計初期のSemtech品を前提とした「素通し」の想定と、KiCad標準USON-10の流用は誤りの原因でした。比較表は <a href="%(GH)sdocs/ESD_%%E3%%83%%95%%E3%%83%%83%%E3%%83%%88%%E3%%83%%97%%E3%%83%%AA%%E3%%83%%B3%%E3%%83%%88%%E7%%85%%A7%%E5%%90%%88_RCLAMP0524P.md">docs/ESD_フットプリント照合_RCLAMP0524P.md</a> に保存しました。</p>
 <div class="tw"><table>
  <thead><tr><th>項目</th><th class="c">データシート（p.4）</th><th class="c">旧（USON-10流用）</th><th class="c">新（専用）</th></tr></thead>
  <tbody>
   <tr><td>本体 D×E／ピッチ</td><td class="c">2.50×1.00／0.50 mm</td><td class="c">同じ</td><td class="c">同じ</td></tr>
   <tr><td>信号端子 幅 b</td><td class="c">0.15〜0.25</td><td class="c">ランド0.30</td><td class="c">ランド0.28</td></tr>
   <tr><td>GND端子（3・8）幅 b1</td><td class="c">0.35〜0.45</td><td class="c"><b>ランド0.30（不足）</b></td><td class="c"><b>ランド0.42</b>（隣との間隔0.15mm）</td></tr>
   <tr><td>端子長 L</td><td class="c">0.33〜0.43</td><td class="c">ランド0.55</td><td class="c">ランド0.55（つま先0.16mm）</td></tr>
   <tr><td>端子機能</td><td class="c">I/O=1,2,4,5　GND=3,8　NC=6,7,9,10</td><td class="c">フロースルー前提のシンボル</td><td class="c">シンボルをIO／NCへ修正。NCは銅ストラップで信号線へ接続</td></tr>
  </tbody></table></div>
 <p>自動検査 <code>check_esd_footprint.py</code>（%(esdn)d項目）：<b>%(esdok)s</b>。ストラップ除去の負の検査、DRC、銅の連続性も再実行しました（A5）。<b>残る制限</b>：データシートに推奨ランドパターンが無いため、新ランドは外形図から導いた値です。注文時にJLCPCBの部品ライブラリのフットプリントと向き（端子1）を確認してください。</p>
</section>

<section id="a2">
 <h2>3. A2　経路の分類とパッド遷移のモデル化</h2>
 <p>ルータが出力する <code>tmds_roles.json</code> に、<b>stub（パッドエスケープの細線、Core側・コネクタ側）</b>と<b>strap（ESD銅ストラップ）</b>の役割を追加し、全TMDS銅を分類しました。<code>check_classification.py</code> が、基板の全トラック・ビアの各点が役割の線分に一致するかを検査します（未分類・役割だけで銅が無い場合は終了コード1）。結果：<b>%(clsn)s、未分類 %(unc)d、実体のない役割 %(stale)d</b>。</p>
 <div class="tw"><table>
  <thead><tr><th>ネット</th><th class="c">PCB線分</th><th class="c">ビア</th><th class="c">main</th><th class="c">stub</th><th class="c">strap</th><th class="c">枝</th></tr></thead>
  <tbody>
""" + rows_cls + """  </tbody></table></div>
 <p><b>これまでの解析で抜けていたもの</b>：Core側の幅0.127mm・長さ2.4mmの引き出し線8本は、主経路のroleに含まれず、解析が0.2mm配線から始まっていた（監査指摘）。今回これを経路に加え、<b>ソケット／コネクタのパッド銅の内側に入っている部分は除外</b>して長さを記録しました（パッドは幅の広い導体で、線路の区間ではないため。2.4mm全部を細線として足すことはしていません）。</p>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">解析経路長（引き出し線なし→あり）</th><th class="c">パッド内の除外長（Core側とコネクタ側、P+N合計）</th><th class="c">SDD11最大(〜1.5GHz)</th><th class="c">SDD21 @742MHz</th></tr></thead>
  <tbody>
""" + rows_stub + """  </tbody></table></div>
 <p>同一モデル（4ポート）で、引き出し線の有無だけを変えた比較です（パッド内の除外後で経路が約2.7mm長くなる。SDD11最大は0.2〜2.1dB変化（改善側）、SDD21は約0.02dB変化）。引き出し線は幅0.127mmで、パッド直後の部分の差動インピーダンスが高い（約150Ω）ため、除外・追加の影響は結合区間のインピーダンスとの組み合わせで決まります。<b>この結果だけで、パッド直後の構造が問題ないとは言えません</b>（3D解析で確認していません）。</p>
</section>

<section id="a3">
 <h2>4. A3　P/N抵抗枝の接続位置</h2>
 <p>これまで、P/Nの枝のアドミタンスを一つに合成し、P側の位置だけに挿入していました（D1では、N側の枝が実際は別の位置にあるのを再現できていませんでした）。今回、モデルを<b>P線・N線を別々に持つ4ポート</b>に変更しました。結合区間は2Dソルバの<b>偶モード・奇モード</b>のインピーダンスと実効誘電率で表し、P枝・N枝は<b>それぞれの実際の分岐位置（経路上の距離）</b>で、各線から対地へ接続します。差動（SDD11・SDD21）に加え、<b>差動→コモン変換（SCD21）</b>を計算します。</p>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">枝長 P/N</th><th class="c">分岐位置 P/N（キャップ側からの距離）</th><th class="c">SDD11最大：P位置のみの旧近似 → 実位置</th><th class="c">SCD21最大：旧近似 → 実位置</th></tr></thead>
  <tbody>
""" + rows_branch + """  </tbody></table></div>
 <ul>
  <li>D1のN側の枝は11.5mmで、ESDの入力パッド付近（キャップから7.2mm）で分岐しています。実位置を反映すると、D1のSDD11は旧近似より悪化し、<b>モード変換（SCD21）も −25dB 程度まで増えます</b>（他のペアは −33dB 以下）。</li>
  <li><b>短く対称な枝（3mm×2、キャップ位置）との比較</b>（8章の表）：D1のSDD11最大は改善しますが、SDD21は大きく変わらず、モード変換は理想上ほぼ0になります。枝を短くする効果は<b>反射とモード変換の改善</b>です。</li>
  <li><b>D1の枝（11.5mm）を残す理由</b>：今回の作業では、抵抗の再配置・再配線は<b>試行していません</b>（時間の都合）。基準条件（Core 100Ω・ESD 0.35pF）の反射は自主目標（−10dB）を満たしている（実位置で %(d1s11).1f dB）ので、PoCではこのまま製作し、試作の反射・モード変換の測定結果に基づいて、次版で抵抗を信号線の近くへ置き直します。ただし<b>モード変換（SCD21 %(d1sc).1f dB）が実機で許容できるかは未確認</b>で、複合条件の最悪側（A4）ではD1が目標を外れる主因です。</li>
  <li>枝の線路は幅0.127mm・単線約85Ω・誘電率3.0の近似で、隣接配線との結合や層の違いは考慮していません。</li>
 </ul>
</section>

<section id="a4">
 <h2>5. A4　複合条件の感度（Core側Z × ESD容量）</h2>
 <p>Core側の差動インピーダンス85／100／115Ω と、ESDの差動容量0.2／0.35／0.5pF を<b>組み合わせた</b>9条件です。根拠：Core Z は公式にデータが無く、100Ωを基準、±15%を仮定の範囲としました（HDMIの許容範囲）。ESD容量はDOWOのデータシート（I/O−GND 0.4〜0.5pF、I/O−I/O 0.2〜0.3pF）から、0.2〜0.5pFを仮定範囲、0.35pFを基準としました。ソケット寄生は別（7章の感度）。</p>
 <div class="tw"><table>
  <thead><tr><th>Core側 Z</th><th class="c">ESD 差動容量</th><th class="c">SDD11最大(〜1.5GHz)（悪い方のペア）</th><th class="c">SDD21 @742MHz（悪い方）</th><th class="c">−10dBの自主目標</th><th class="c">（比較案）枝を3mm×2の対称にした場合の最悪値</th></tr></thead>
  <tbody>
""" + rows_mat + """  </tbody></table></div>
 <figure><img src="img/sim_matrix_r3.png" alt="複合条件" """ + IMG + """>
  <figcaption>図1　Core側ZとESD容量の複合条件（悪い方のペア）。観察帯域は〜1.5GHz（720p60）。</figcaption></figure>
 <p><b>目標を外れる条件への扱い</b>：外れる条件は %(failing)s の<b>最悪側の組み合わせ</b>で、いずれも悪い方のペアはD1（N側の枝11.5mm・分岐位置が非対称）です。比較案（枝を短く対称にした場合）では %(failing_ideal)s。これは<b>出現確率・製造歩留まり・実機の表示可否ではありません</b>。対処：①PoCでは受け入れる不確かさとして記録し、試作で反射（TDRまたは公式Dockとの比較）を測る、②反射が悪ければ、ESD容量を下げる（別部品）、D1の枝を短縮する（A3）、低速（640×480）で動作確認する、を次版の対処とする。自主目標は規格値ではありません。</p>
</section>

<section id="a5">
 <h2>6. A5　自動検査と説明の整合</h2>
 <div class="tw"><table>
  <thead><tr><th>信号</th><th class="c">Coreパッド</th><th class="c">HDMIコネクタパッド</th><th class="c">ピン対応</th><th class="c">銅の連続性</th><th class="c">ストラップ除去の検査</th></tr></thead>
  <tbody>
""" + rows_pins + """  </tbody></table></div>
 <ul>
  <li><code>check_continuity.py</code>：銅だけでCoreパッド→キャップ→コネクタパッドに到達するか、<b>期待するピン番号に接続しているか</b>（P/Nの見た目の上下ではなく番号で判定）。不合格は終了コード1。D2はP/Nをピンで入れ替えて接続（意図した設計）：FPGAで<b>D2のシリアルビットを反転</b>する要求を <a href="%(GH)sdocs/FPGA_HDMI%%E8%%A6%%81%%E6%%B1%%82_D2%%E5%%8F%%8D%%E8%%BB%%A2%%E3%%81%%A8%%E3%%83%%94%%E3%%83%%B3.md">docs/FPGA_HDMI要求_D2反転とピン.md</a> に明記。</li>
  <li><code>check_negative.py</code>：各線のESDストラップを1本ずつ取り除いた基板で、<b>その線だけ</b>が不連続と判定されることを確認（結果：%(negok)s）。</li>
  <li><code>check_classification.py</code>、<code>check_esd_footprint.py</code>：上記のとおり。DRC：違反・未配線 %(drc)d 件（KiCad 10.0.6）。DRCは部品内部の導通や実ランド適合を保証しない。</li>
  <li><b>モデルの制限（継続して明記）</b>：全ての銅層を同じマイクロストリップ表で近似（In2.Cu・B.Cuは実際の帰路が異なる）。ビアの寄生は未考慮。枝の線路は近似。3D解析で確認していない。</li>
 </ul>
</section>

<section id="result">
 <h2>7. 配線の結果とチャネル推定</h2>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">P/N長 (mm)（引き出し線を含む）</th><th class="c">スキュー</th><th class="c">Zdiff 最小/平均 (Ω)</th><th class="c">499Ω枝 P/N</th><th class="c">F.Cu結合割合</th></tr></thead>
  <tbody>
""" + rows_len + """  </tbody></table></div>
 <p>長さは実PCBの銅線を接続順にたどり、パッド中心からの積算です（ルータの設計値ではなく、実配線の抽出値）。部品内部・ビアの垂直方向（約1.6mm相当）・Core側基板内（38.4mm）は含みません。</p>
 <figure><img src="img/sim_route_r3.png" alt="TMDS実配線" """ + IMG + """>
  <figcaption>図2　TMDS 4組の実配線（細線=P、太線=N、黒細線=499Ω枝）。</figcaption></figure>
 <figure><img src="img/render_top_r3.png" alt="基板3Dレンダリング" """ + IMG + """>
  <figcaption>図3　基板全体（右辺の上寄りがHDMI）。</figcaption></figure>
</section>

<section id="channel">
 <h2>8. チャネル推定（4ポートモデル）</h2>
 <p>Core基板内（理想100Ω・38.4mm）、キャリア配線（引き出し線・結合ペア・ESDストラップ）、AC結合キャップ、ESD（0.35pF）、499Ω枝（P/N別位置）、コネクタ（100Ω・11mm）。観察帯域は〜1.5GHz。</p>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">SDD11 371/742MHz</th><th class="c">SDD11 最大(〜1.5GHz)</th><th class="c">SDD21 371/742MHz</th><th class="c">SDD21 1.5GHz</th><th class="c">SCD21 最大</th></tr></thead>
  <tbody>
""" + rows_sp + """  </tbody></table></div>
 <figure><img src="img/sim_sparam_r3.png" alt="Sパラメータ推定" """ + IMG + """>
  <figcaption>図4　差動S11／S21、モード変換、Core側配線の差動インピーダンス。</figcaption></figure>
 <h3>第2版（第2回監査の対象）との比較</h3>
 <div class="tw"><table>
  <thead><tr><th>ペア</th><th class="c">SDD11最大(〜1.5GHz)　第2版 → 第3版</th><th class="c">SDD21 @742MHz　第2版 → 第3版</th></tr></thead>
  <tbody>
""" + rows_base + """  </tbody></table></div>
 <div class="callout warn"><b class="t">比較の読み方</b>第2版と第3版の差は、①引き出し線（各2.4mm、パッド内を除く）の追加、②結合区間の偶モード・奇モードによる表現、③P/Nの枝を別位置へ接続、④導体損失の計算式の変更（差動インピーダンスではなく各線のモードのインピーダンスで計算）、の合計です。個別の寄与は分離していません（①は3章、③は4章に分離した比較あり）。SDD21の差は小さい（約0.06〜0.09dB）一方、D1・D2のSDD11は2〜3dB悪化しました。</div>
 <h3>是正の効果と仮定値に対する感度（同一モデル）</h3>
 <div class="tw"><table>
  <thead><tr><th>条件（4組のうち悪い方）</th><th class="c">SDD11 最大(〜1.5GHz)</th><th class="c">SDD21 @742MHz</th><th class="c">SCD21 最大</th></tr></thead>
  <tbody>
""" + rows_var + """  </tbody></table></div>
 <figure><img src="img/sim_variants_r3.png" alt="是正の効果と感度" """ + IMG + """>
  <figcaption>図5　是正の効果とESD容量・Core側Zへの感度。</figcaption></figure>
 <h3>SODIMM接点の寄生（別の不確かさ）</h3>
 <figure><img src="img/sim_sensitivity_r3.png" alt="接点の感度解析" """ + IMG + """>
  <figcaption>図6　接点の直列L（差動）と並列C（差動）。実機の値は確認できていない。</figcaption></figure>
</section>

<section id="em3d">
 <h2>9. 3D電磁界解析（openEMS）の状況（B1/B2）</h2>
 <p><b>今回の作業では3D解析の較正を行っていません</b>（未着手のまま保留）。第2回監査の記録では、単線の較正が未達（lumped-port単線：30,000ステップで残留エネルギー約−20.6dB、指定−40dB未達。別のMSLポート基準：−50dBに収束したが2D基準59.85Ωに対し3Dは52.4〜53.1Ωで約11%の差）です。3Dの値はこのレポートの結論に使っていません。</p>
</section>

<section id="limits">
 <h2>10. 限界と残課題</h2>
 <div class="tw"><table>
  <thead><tr><th>事項</th><th>状況・対応</th></tr></thead>
  <tbody>
   <tr><td>D1のN側の枝（%(d1n).1fmm）、P/N非対称</td><td>PoCでは残す（A3）。試作でモード変換・反射を測り、次版で抵抗を信号線近くへ</td></tr>
   <tr><td>複合条件で−10dB目標を外れる最悪側</td><td>PoCで受け入れる不確かさとして記録（A4）。実機で反射を確認</td></tr>
   <tr><td>ESDの推奨ランド</td><td>データシートに無い。注文時にJLCPCBのフットプリント・向きを確認</td></tr>
   <tr><td>Core基板内・SODIMM接点</td><td>感度解析のみ。公式Dockとの比較測定が有効</td></tr>
   <tr><td>内層・ビア・多層の帰路</td><td>全層をマイクロストリップ表で近似（未確認）。3D解析の較正後に確認</td></tr>
   <tr><td>3D解析（B1/B2）、MeOS要求（C）</td><td>未着手（この作業の範囲外）</td></tr>
   <tr><td>製作後の成功条件（PoC）</td><td>短いケーブル・限定モニタで、640×480→720p60の固定パターンを30分程度表示。1080p60は保証対象外</td></tr>
  </tbody></table></div>
</section>

<section id="repro">
 <h2>11. 再現手順と記録</h2>
 <p>対象：ベースコミット <code>%(base)s</code>（第2版）に対する変更。回路・PCB・抽出入力・モデル・結果・図・本ページは、同じ変更に含まれます。ファイルのSHA-256（改行をLFに正規化）は下表（<code>kicad/sim/manifest_r3.json</code>）で、チェックアウト後に <code>make_manifest.py</code> で再計算して照合できます（コミット自身のSHAは、その中に含められないため記載しません）。</p>
 <div class="tw"><table>
  <thead><tr><th>コマンド（順番）</th><th>内容</th></tr></thead>
  <tbody>
   <tr><td><code>make_sch.py</code>、<code>make_pcb.py</code>、<code>finish_pcb.py NONE.0</code></td><td>回路図・配置配線（<code>tmds_roles.json</code>＝main/stub/strap/branchを出力）</td></tr>
   <tr><td><code>kicad-cli pcb drc ...</code>（--severity-error --all-track-errors）</td><td>DRC（結果：<code>drc_r3.json</code>）</td></tr>
   <tr><td><code>tmds_channel.py --extract</code>（KiCad python）、<code>check_continuity.py</code>、<code>check_negative.py</code>、<code>check_classification.py</code>、<code>check_esd_footprint.py</code></td><td>実配線の抽出と、各検査（失敗は終了コード1）</td></tr>
   <tr><td><code>tmds_channel.py</code>、<code>tmds_sparam.py</code>、<code>make_report_figs.py</code>、<code>make_manifest.py</code>、<code>make_report_page.py</code></td><td>解析・図・ハッシュ・このページ</td></tr>
  </tbody></table></div>
 <details><summary>ファイルのハッシュ（先頭16桁）</summary><div class="tw"><table><thead><tr><th>ファイル</th><th>SHA-256</th></tr></thead><tbody>
""" + rows_man + """ </tbody></table></div></details>
 <p>使用環境：KiCad 10.0.6、Python 3.12（numpy、scipy、matplotlib）。方針・前提・判断の記録：<a href="%(GH)sdocs/%%E3%%82%%B7%%E3%%83%%9F%%E3%%83%%A5%%E3%%83%%AC%%E3%%83%%BC%%E3%%82%%B7%%E3%%83%%A7%%E3%%83%%B3%%E6%%96%%B9%%E9%%87%%9D%%E3%%81%%A8%%E7%%9B%%A3%%E6%%9F%%BB%%E8%%A8%%98%%E9%%8C%%B2.md">docs/シミュレーション方針と監査記録.md</a>（§11に今回の対応）。</p>
 <h3>訂正記録</h3>
 <ul>
  <li>2026-10-24（第3版）：第2回監査のA1〜A5に対応。引き出し線の欠落、P/N枝の位置の近似、導体損失の計算式（差動インピーダンスで計算していた）を訂正。第2版は、引き出し線を経路に含めず、P/Nの枝を一つの位置にまとめていたため、D1・D2のSDD11を2〜3dB良く見積もっていた。導体損失の計算式も各線のモードのインピーダンスへ変更した（SDD21への影響は約0.06〜0.09dB）。</li>
 </ul>
</section>

</main>
<footer><div class="wrap">Tab5 × Tang Primer 20K キャリア基板 ／ HDMIシミュレーション評価（第3版）／ 2026-10-24</div></footer>
</body>
</html>
"""
d1 = full["D1"]
failing = "、".join("Core %.0fΩ × ESD %.2fpF（%.1fdB）" % (c["core_z"], c["esd_cd_pf"], c["sdd11_max_1500"]) for c in mat if c["sdd11_max_1500"] > -10) or "（なし）"
bad_ideal = [c for c in mat if c["sdd11_ideal_branch"] > -10]
failing_ideal = ("外れる条件は残る（" + "、".join("Core %.0fΩ × ESD %.2fpF（%.1fdB）" % (c["core_z"], c["esd_cd_pf"], c["sdd11_ideal_branch"]) for c in bad_ideal) + "）") if bad_ideal else "全9条件で −10dB を満たす"
subs = dict(drc=n_drc, w11=worst11, w21=worst21, wsc=worst_sc, d1n=summ["D1"]["branch_C"][1], GH=GH, base=BASE,
            esdn=len(esd["checks"]), esdok="全項目OK" if esd_ok else "不合格あり",
            clsn=", ".join("%s %d" % (k, v) for k, v in cls["counts"].items()), unc=len(cls["unclassified"]), stale=len(cls["stale_roles"]),
            failing=failing, failing_ideal=failing_ideal, negok="全8線で検出" if neg_ok else "未検出あり", d1s11=d1["s11_max_1500"], d1sc=d1["scd21_max_1500"])
import re


def sub_ph(m):
    return ("%" + m.group(2)) % subs[m.group(1)]


page = re.sub(r"%\((\w+)\)([-.\d]*[sfd])", sub_ph, page)
page = page.replace("%%", "%")
open(os.path.join(SITE, "hdmi-simulation-r3.html"), "w", encoding="utf-8").write(page)
print("wrote site/hdmi-simulation-r3.html")
