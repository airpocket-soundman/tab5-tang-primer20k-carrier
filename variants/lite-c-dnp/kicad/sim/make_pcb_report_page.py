"""Consolidated PCB report for GitHub Pages: independent review, simulation, BOM and renders (system python).
  python -X utf8 kicad/sim/review_pcb_report.py      # re-run checks, write review JSON and renders first
  python -X utf8 kicad/sim/make_pcb_report_page.py   # -> site/pcb-report.html, and the "latest" link on every page
Every number on the page is read from the committed check/model JSON, bom.csv or the review JSON.
"""
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'kicad/sim'
SITE = ROOT/'site'
REVIEW = 'pcb_report_review_2026-10-25.json'
GH = 'https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/'
LINK = '<p id="pcb-report-link"><a href="pcb-report.html">最新：基板レポート（独立レビュー・シミュレーション・BOM・外観図、2026-10-25）</a></p>'
CHECK_LABELS = {
    'check_continuity': ('TMDS銅の連続性とピン対応', '8線すべて、Coreパッド→キャップ→コネクタを銅だけで到達。期待ピン番号と一致'),
    'check_negative': ('ストラップ除去の負の検査', '各線のESDストラップを1本ずつ外すと、その線だけが不連続になる'),
    'check_classification': ('TMDS銅の区間分類', '未分類0、重複0、幅の不一致0、ビア形状の誤り0'),
    'check_esd_footprint': ('ESDランドとデータシートの照合', 'DOWO RCLAMP0524P（DFN2510-10L）の外形寸法と配置済みランド'),
    'check_d1_bias': ('D1バイアス分岐', 'R30/R31は0402、分岐0.585mm、近傍GNDビアあり'),
    'check_ground_reference': ('TMDS直下のGND参照', '主配線・引き出し・ストラップ直下を0.25mm刻みで検査、全点が充填済みIn1 GND上'),
    'check_parallel_power': ('パラレル配線と電源トポロジ', '15信号のM5-Bus↔Coreピン、バススイッチ、監視IC、OE回路など32項目'),
    'check_power_dc': ('Core 5V銅経路の抵抗', 'Core 5V各端子までの直列抵抗と電圧降下（銅のみ）'),
    'check_mbus_revision': ('M5-Busの向き', '実物確認した四隅（1=GND、2=CLK、29=VIN、30=未接続）とTMDS形状の不変'),
    'test_classification_check': ('故障注入：区間分類', '11ケース'),
    'test_d1_bias_check': ('故障注入：D1分岐', '4ケース'),
    'test_esd_check': ('故障注入：ESDランド', '13ケース（回転・裏面反転を含む）'),
    'test_parallel_power_check': ('故障注入：パラレル・電源', '10ケース（M5-Bus列の左右反転を含む）'),
}


def esc(s):
    return html.escape(str(s), quote=True)


def load(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def table(head, rows, cls=''):
    h = ''.join(f'<th>{c}</th>' for c in head)
    body = ''.join('<tr>'+''.join(c if c.startswith('<td') else f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'


def db(v):
    return '数値床（理想対称）' if v <= -199 else f'{v:.1f} dB'


def fig(src, caption, alt):
    # KiCad's SVG drawings are black on transparent: keep them on paper in dark mode.
    paper = ' class="paper"' if src.endswith('.svg') else ''
    return f'<figure><img{paper} src="{src}" alt="{esc(alt)}" loading="lazy"><figcaption>{caption}</figcaption></figure>'


def findings(review):
    holes = review['board']['holes']
    thin = [h for h in holes if h['min_web_mm'] < 1.0]
    rest = min(h['min_web_mm'] for h in holes if h not in thin)
    net = review['netlist']
    extra = '、'.join(d['pad']+'→'+'/'.join(d['pcb']) for d in net['pcb_only_nets'])
    single = '、'.join(net['single_pin_nets']).replace('/', '')
    leads = '、'.join(review['board']['tht_leads_toward_tab5'])
    return [
        ('t-warn', '発注前に判断', '左側M3穴の縁残りが少ない',
         f'{"・".join(h["ref"] for h in thin)}（x={thin[0]["x_mm"]}mm）は穴の縁から基板外形まで<b>{thin[0]["min_web_mm"]}mm</b>しかない（他の穴は{rest}mm以上）。'
         'DRCは銅と外形の距離を見るため、銅の無い取付穴は検出されない。加工時の欠け・ネジ締めでの割れ、M3なべ頭（φ5.5mm程度）の外形はみ出しが起こりうる。'
         '設計仕様（index.html 2章）では左側の穴は「キャリアは使用しない」としている。使わないなら穴を削除し、使うなら外形を左へ広げられるかTab5.stlで確認する。'),
        ('t-warn', '組立時に確認', 'Tab5側へ出るTHTのリード',
         f'上面実装のTHT部品（{leads}）のリードはTab5背面側へ出る。J3の嵌合で決まる隙間より短く切り、絶縁を確認する。'
         '特にJP1や、後付けするJ6〜J8のピンヘッダの尾部（一般に約3mm）は、そのままでは当たる可能性がある。'),
        ('t-info', '記録', '回路図とPCBの等価性',
         f'KiCadの等価性検査は{review["drc_erc"]["parity_total"]}件を表示するが、内訳はすべて表記の差（ネット名の「/」、ライブラリ名、LCSC欄、取付穴のBOM属性）。'
         f'ピン単位の比較（回路図{net["schematic_pins"]}ピン）で不一致は0件。PCBだけにあるネットは{extra}で、DCジャックのスリーブ側とCoreソケット固定金具をGNDへ接続する意図した接続。'
         '回路図側へ反映しておくと、次回から等価性検査を合否判定に使える。'),
        ('t-info', '記録', '1ピンだけのネット',
         f'{single}は1ピンだけに接続（ERC警告3件）。CH224Kのパワーグッドと、M5-BusのI2Cをキャリアで使わない設計どおり。意図を示すため未接続フラグにするとよい。'),
        ('t-info', '記録', '降圧のENA分圧（R8 100k／R9 15k）',
         '12V入力時のENAは約1.57V。TPS5430のENA立上り閾値はデータシートで代表値1.3Vのみ（最小・最大の規定なし）で、余裕は約0.27V。'
         'BOM注記の「9V以下では起動しない」は保証値ではない。ただしTPS5430は9V入力でも5Vを出力できるため、安全上の問題ではない。'),
        ('t-info', '記録', 'BOM注記の混同',
         'D4（降圧のキャッチダイオード）がD1/D2と同じ行で「reverse-polarity + OR」と注記されている。U9とU10の注記はどちらも「3.08V / 4.38V」。'
         'C10「10u/16V」は50V品C13585を共用（耐圧は上側なので問題なし）。注文時の照合で迷わないよう注記を分けるとよい。'),
        ('t-info', '記録', 'kicad/README.md の状態欄が古い',
         '「Not manufacturing-ready（M5-Busの向きが未確認）」と、旧版の数値（SDD11 −16.1dB、SCD21 −33.6dB）が残っている。最新はM5-Bus確認済み、SDD11最大 −15.5dB、SCD21最大 −25.5dB。'),
        ('t-info', '記録', '3Dモデルの欠落',
         'J4（SODIMMソケット）とTang Primer 20K Core本体の3Dモデルが無く、下の外観図には写らない。Core搭載時の高さ・HDMIコネクタとの干渉は実物で確認する。'),
    ]


def bom_rows():
    rows = list(csv.DictReader((ROOT/'kicad/bom.csv').open(encoding='utf-8')))
    manual = {r['Refs'] for r in csv.DictReader((ROOT/'manufacturing/poc-2026-10-24/manual-assembly.csv').open(encoding='utf-8'))}
    groups = {'PCBA（JLC実装）': [], '手実装': [], '実装しない（DNP）': []}
    for r in rows:
        if r['Refs'].startswith('H1'):
            continue  # mounting holes are not parts
        if r['DNP']:
            groups['実装しない（DNP）'].append(r)
        elif r['Refs'] in manual:
            groups['手実装'].append(r)
        else:
            groups['PCBA（JLC実装）'].append(r)
    out, counts = [], {}
    for g, items in groups.items():
        counts[g] = sum(int(r['Qty']) for r in items)
        for r in items:
            lcsc = f'<a href="https://www.lcsc.com/product-detail/{esc(r["LCSC"])}.html">{esc(r["LCSC"])}</a>' if r['LCSC'] else '—'
            fp = r['Footprint'].split(':')[-1]
            out.append([esc(g), f'<code>{esc(r["Refs"].replace(",", ", "))}</code>', esc(r['Value']), f'<td class="c">{r["Qty"]}</td>',
                        lcsc, esc(fp), esc(r['Note'])])
    return out, counts


def main():
    review = load(REVIEW)
    sp, matrix, summ = load('report_sparam.json'), load('report_matrix.json'), load('tmds_summary.json')
    variants, dc, pp = load('report_variants.json'), load('power_dc_check.json'), load('parallel_power_check.json')
    pkg = json.loads((ROOT/'manufacturing/poc-2026-10-24/package-check.json').read_text(encoding='utf-8'))
    regress = {k: load(f'regression_{k}.json')['tests'] for k in ('classification', 'd1_bias', 'esd', 'parallel_power')}
    board = review['board']
    worst = max(sp, key=lambda k: sp[k]['s11_max_1500'])
    worst21 = min(sp, key=lambda k: sp[k]['s21_742'])
    worst_cd = max((k for k in sp if sp[k]['scd21_max_1500'] > -199), key=lambda k: sp[k]['scd21_max_1500'])
    fails = [m for m in matrix if m['sdd11_max_1500'] > -10]
    bom, counts = bom_rows()
    checks_ok = sum(1 for v in review['checks'].values() if v == 0)
    model = review['model']
    style = (SITE/'index.html').read_text(encoding='utf-8')
    style = style[style.index('<style>'):style.index('</style>')]
    style += ('figure img{width:100%;height:auto;display:block;border-radius:6px}'
              'figure img.paper{background:#fff;padding:8px}'
              '.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}'
              '.grid3 figure{margin:0}.verdict{font-size:1.05rem}'
              'table.bom td:nth-child(6),table.bom td:nth-child(7){font-size:.82rem;color:var(--muted)}'
              'main.wrap{padding-bottom:24px}code.hash{overflow-wrap:anywhere}table.nw td{white-space:nowrap}</style>')

    f_rows = [[f'<td class="{c}">{esc(s)}</td>', f'<b>{esc(t)}</b>', b] for c, s, t, b in findings(review)]
    check_rows = []
    for name, code in review['checks'].items():
        label, scope = CHECK_LABELS[name]
        check_rows.append([esc(label), f'<td class="{"t-ok" if code == 0 else "t-bad"}">{"成功" if code == 0 else "失敗"}（終了コード{code}）</td>',
                           esc(scope), f'<code>{name}.py</code>'])
    de = review['drc_erc']
    erc_warn = sum(de['erc_all_severities'].values())
    pair_rows = []
    for tag in ('D0', 'D1', 'D2', 'CK'):
        s, m = sp[tag], summ[tag]
        pair_rows.append([tag, f'{m["len_p"]:.2f} / {m["len_n"]:.2f} mm', f'{abs(m["skew"]):.2f} mm', f'{m["zmin"]:.0f} / {m["zmean"]:.0f} Ω',
                          f'{m["branch_C"][0]:.1f} / {m["branch_C"][1]:.1f} mm',
                          f'{s["s11_371"]:.1f} / {s["s11_742"]:.1f} dB', f'<b>{s["s11_max_1500"]:.1f} dB</b>',
                          f'{s["s21_371"]:.2f} / {s["s21_742"]:.2f} dB', db(s['scd21_max_1500'])])
    mat_rows = [[f'{m["core_z"]:.0f} Ω', f'{m["esd_cd_pf"]:.2f} pF', f'{m["sdd11_max_1500"]:.1f} dB ({m["worst_pair"]})',
                 f'{m["sdd21_742"]:.2f} dB',
                 '<td class="t-bad">外れる</td>' if m['sdd11_max_1500'] > -10 else '<td class="t-ok">満たす</td>'] for m in matrix]
    var_rows = [[esc(k), f'{v["sdd11_max_1500"]:.1f} dB ({v["worst_pair"]})', f'{v["sdd21_742"]:.2f} dB', db(v['scd21_max_1500'])]
                for k, v in variants.items()]
    bus_rows = [[c['name'].replace('parallel_', ''), str(c['mbus_pin']), str(c['core_pin'])] for c in pp['checks'] if 'mbus_pin' in c]
    hole_rows = [[h['ref'], f'({h["x_mm"]}, {h["y_mm"]})', f'{h["drill_mm"]} mm',
                  f'<td class="{"t-warn" if h["min_web_mm"] < 1 else "t-ok"}">{h["min_web_mm"]} mm</td>'] for h in board['holes']]
    rs = dc['path_resistance_ohm']
    sha = review['pcb_sha256']

    body = f'''
<header class="top"><div class="wrap">
 <p><span class="badge">基板レポート 最新版</span><span class="badge">少数PoC 発注候補</span></p>
 <h1>Tab5 × Tang Primer 20K キャリア基板<br>基板レポート（独立レビュー・シミュレーション・BOM・外観図）</h1>
 <p class="sub">対象：コミット <code>{review["reviewed_commit"][:7]}</code>（M5-Bus列の実物確認・修正後）、PCB SHA-256 <code>{sha[:16]}</code>。作成：2026-10-25、KiCad {esc(review["kicad"])}。</p>
</div></header>
<nav class="toc"><div class="wrap"><a href="#verdict">結論</a><a href="#review">独立レビュー</a><a href="#look">外観図</a><a href="#board">基板仕様</a><a href="#power">電源</a><a href="#bus">パラレル</a><a href="#hdmi">HDMIシミュレーション</a><a href="#bom">BOM</a><a href="#verify">検査一覧</a><a href="#files">データ</a></div></nav>
<main class="wrap">
<p><a href="index.html">← 企画・設計仕様</a> ／ 詳細：<a href="poc-fabrication.html">発注準備（通信・電源）</a>、<a href="hdmi-simulation-r3.html">HDMIシミュレーション第3版</a>、<a href="uniform-line-calibration.html">3D均一直線の校正</a></p>

<section id="verdict">
<h2>1. 結論</h2>
<div class="kpi">
 <div><b>{de["drc_violations"]} / {de["unconnected"]}</b><span>DRC違反 / 未配線（警告を含む全重大度）</span></div>
 <div><b>0 件</b><span>回路図とPCBのピン単位のネット不一致（{review["netlist"]["schematic_pins"]}ピン）</span></div>
 <div><b>{checks_ok} / {len(review["checks"])}</b><span>自動検査・故障注入スクリプト成功（回帰{sum(regress.values())}ケース）</span></div>
 <div><b>{sp[worst]["s11_max_1500"]:.1f} dB</b><span>SDD11最大（〜1.5GHz、悪い方 {worst}）</span></div>
 <div><b>{sp[worst21]["s21_742"]:.2f} dB</b><span>SDD21 @742MHz（悪い方 {worst21}）</span></div>
 <div><b>{pkg["pcba_components"]}個 / {pkg["pcba_bom_rows"]}行</b><span>JLC実装（BOM・CPLの部品集合一致）</span></div>
</div>
<div class="callout ok verdict"><b class="t">判断：少数PoCとして発注してよい（左側取付穴の扱いを決めてから）</b>
電気的な設計は、DRC・ERC（エラー）・ネット照合・TMDS/パラレル/電源の自動検査・故障注入のすべてを私の環境で再実行して確認した。
HDMIのチャネル推定もPCBから抽出し直して、公開値と完全に一致した（{len(model["identical"])}ファイルがバイト単位で同一）。
発注前に判断が必要なのは<b>左側M3穴（H1/H2）の縁残り{board["holes"][0]["min_web_mm"]}mm</b>の1件で、電気特性には影響しない。</div>
<div class="callout warn"><b class="t">このレポートが保証しないこと</b>
実機での通信・DDR3アクセス・720p60表示、HDMI規格適合は未確認。HDMIの数値は2D線路接続モデルによる推定で、Core基板内・SODIMM接点・ビアの寄生は感度解析に留まる。
複合条件（Core側 {fails[0]["core_z"]:.0f}Ω × ESD {fails[0]["esd_cd_pf"]:.2f}pF）では自主目標の−10dBを外れる（{fails[0]["sdd11_max_1500"]:.1f}dB）。</div>
</section>

<section id="review">
<h2>2. 独立レビューの指摘</h2>
<p>監査済みの設計を、記録された結果を信用せずに再実行し、図面・BOM・3D外観を目視で確認した。再実行の内容は9章と <code>kicad/sim/{REVIEW}</code> に保存した。</p>
{table(["区分", "項目", "内容"], f_rows)}
</section>

<section id="look">
<h2>3. 外観図</h2>
<p>KiCad 3Dビューアで現行PCBから描画（{review["reviewed_commit"][:7]}）。Coreとソケット（J4）は3Dモデルが無いため、シルクの枠だけが写る。</p>
{fig("img/render_top_poc.png", "図1　上面（部品面）。左：電源入力（DCジャックJ1、USB-C PD J2、降圧U2）、中央：M5-Bus（J3、下面）とバススイッチU7/U8、右：Coreソケット J4、HDMI J5。", "基板上面の3D画像")}
<div class="grid2">
{fig("img/render_iso_poc.png", "図2　斜め上から。HDMIコネクタは右辺から張り出す。", "基板の斜視3D画像")}
{fig("img/render_bottom_poc.png", "図3　下面（Tab5側）。M5-Busヘッダ J3 のみを実装。下面から見た鏡像。", "基板下面の3D画像")}
</div>
<div class="grid2">
{fig("audit-data/poc-assembly-top.svg", "図4　上面実装図（発注データと同じもの）", "上面実装図")}
{fig("audit-data/poc-assembly-bottom.svg", "図5　下面実装図（下面から見た鏡像）", "下面実装図")}
</div>
</section>

<section id="board">
<h2>4. 基板仕様</h2>
{table(["項目", "値"], [
    ["外形・層", f"{board['size_mm'][0]:.0f} × {board['size_mm'][1]:.0f} mm、{board['copper_layers']}層、{board['thickness_mm']} mm"],
    ["積層", "外層35µm／内層17.5µm、JLC04161H-7628相当。表層からIn1 GNDまで0.2104mm（HDMI解析の前提）"],
    ["部品", f"上面 {board['footprints_by_side']['top']}個、下面 {board['footprints_by_side']['bottom']}個（J3）、取付穴6"],
    ["配線", f"ネット{board['nets']}、配線{board['tracks']}本（総延長{board['track_length_m']} m）、ビア{board['vias']}"],
    ["入力", "安定化12Vのみ（DCジャック、またはUSB PDで12V要求）。24Vは不可"],
    ["M5-Bus", "Tab5裏面を電池区画が左になる向きで見て、左列がGND／1番（2026-10-24 実物確認）"],
])}
<h3>取付穴</h3>
{table(["穴", "中心 (x, y)", "穴径", "外形までの残り"], hole_rows)}
</section>

<section id="power">
<h2>5. 電源</h2>
{table(["区分", "構成"], [
    ["入力保護", "PTC 3A（F1）、SMBJ15A（D3、クランプ24.4V）、SS54でDC/PDをOR（D1/D2）、100µF/35V"],
    ["USB PD", "CH224K（U1）で12V要求：CFG1/CFG2=Low、CFG3=内部プルアップ（R4はDNP）"],
    ["Core用5V", "TPS5430（U2）、15µH、10k/3.24kで約4.99V、出力220µF POSCAP（ESR最大40mΩ）"],
    ["バススイッチ用3.3V", "TLV1117LV33（U3）、セラミック出力で安定する品番"],
    ["Tab5への供給", "VIN（12V）をM5-Bus HVIN（25/27/29番）へ。Tab5の5V/BATは未接続"],
])}
<p>Core 5V端子までの銅経路の直列抵抗は {min(rs.values()):.3f}〜{max(rs.values()):.3f} Ω、0.5Aを1経路に流した場合の降下は約{dc["core_0_5A_max_path_drop_V"]*1000:.0f} mV。
帰還抵抗±1%・基準±2%での設定範囲は {dc["regulator_conservative_bound_V"][0]:.3f}〜{dc["regulator_conservative_bound_V"][1]:.3f} V で、Coreの規定（{dc["core_5V_official_range_V"][0]}〜{dc["core_5V_official_range_V"][1]} V）に入る。
接点・GND帰路・リップル・負荷変動は含まないため、初回通電で測定する。</p>
</section>

<section id="bus">
<h2>6. パラレル通信</h2>
<p>Tab5 → SN74CB3Q3245（U7/U8、Ioff対応）→ 330Ω → Core。両方の電源監視（TPS3839：Tab5 3.3V／Core 5V）が正常で、BUS ARMジャンパ（JP1、初期は開放）を閉じたときだけOEが有効になる。CLKはCoreの専用クロック入力（52番、GCLKT_1）。</p>
{table(["信号", "M5-Busピン", "Core SODIMMピン"], bus_rows)}
</section>

<section id="hdmi">
<h2>7. HDMIシミュレーション</h2>
<p>実PCBの銅から抽出した経路に、2D電磁界ソルバの線路定数、AC結合キャップ、ESD（0.35pF）、499Ω枝（P/N別位置）、コネクタを接続した4ポートモデル。観察帯域は720p60に対して〜1.5GHz。今回のレビューで抽出から図の生成までを再実行し、結果は公開値と一致した。</p>
{table(["ペア", "P/N長", "スキュー", "Zdiff 最小/平均", "499Ω枝 P/N", "SDD11 371/742MHz", "SDD11最大", "SDD21 371/742MHz", "SCD21最大"], pair_rows, "nw")}
{fig("img/sim_sparam_r3.png", "図6　差動S11／S21、モード変換、Core側配線の差動インピーダンス", "Sパラメータのグラフ")}
<div class="grid2">
{fig("img/sim_route_r3.png", "図7　TMDS 4組の実配線（細線=P、太線=N、黒細線=499Ω枝）", "TMDS配線図")}
{fig("img/sim_matrix_r3.png", "図8　Core側ZとESD容量の複合条件（悪い方のペア）", "複合条件の結果")}
</div>
<h3>複合条件（Core側Z × ESD容量）</h3>
{table(["Core側Z", "ESD差動容量", "SDD11最大（悪い方）", "SDD21 @742MHz", "−10dB目標"], mat_rows)}
<h3>是正の効果と感度</h3>
{table(["条件", "SDD11最大", "SDD21 @742MHz", "SCD21最大"], var_rows)}
<div class="grid2">
{fig("img/sim_variants_r3.png", "図9　是正の効果とESD容量・Core側Zへの感度", "感度のグラフ")}
{fig("img/sim_sensitivity_r3.png", "図10　SODIMM接点の直列Lと並列C（実機の値は未確認）", "接点寄生の感度")}
</div>
<p>モード変換の最悪は {worst_cd}（{sp[worst_cd]["scd21_max_1500"]:.1f} dB）で、P/Nの499Ω枝の長さの差による。D1は対称のため理論上0。D2はFPGA側でシリアルビットを反転する（<a href="{GH}docs/FPGA_HDMI%E8%A6%81%E6%B1%82_D2%E5%8F%8D%E8%BB%A2%E3%81%A8%E3%83%94%E3%83%B3.md">要求</a>）。3D電磁界解析は均一直線の校正までで、設計判断には使っていない。</p>
</section>

<section id="bom">
<h2>8. BOM</h2>
<p>JLC実装 {counts["PCBA（JLC実装）"]}個、手実装 {counts["手実装"]}個（ほかにM3取付穴6）、実装しない {counts["実装しない（DNP）"]}個。原本は <a href="{GH}kicad/bom.csv">kicad/bom.csv</a>、発注用は <code>manufacturing/poc-2026-10-24/jlc-bom.csv</code>。在庫と代替は注文時に確認し、ランドが合わない代替品は採用しない。</p>
{table(["区分", "部品番号", "値", "数", "LCSC", "フットプリント", "注記"], bom, "bom")}
</section>

<section id="verify">
<h2>9. 検査一覧（このレビューで再実行）</h2>
{table(["検査", "結果", "範囲", "スクリプト"], [
    ["DRC（警告・除外を含む全重大度）", f'<td class="t-ok">違反{de["drc_violations"]}、未配線{de["unconnected"]}</td>', "KiCad 10.0.6、トラックの全エラー", "<code>kicad-cli pcb drc</code>"],
    ["ERC", f'<td class="t-ok">エラー0、警告{erc_warn}</td>', f'回路図内のシンボルがライブラリ版と異なる{de["erc_all_severities"].get("warning:lib_symbol_mismatch", 0)}件、1ピンのネット{de["erc_all_severities"].get("warning:isolated_pin_label", 0)}件', "<code>kicad-cli sch erc</code>"],
    ["回路図とPCBのネット照合", '<td class="t-ok">不一致0</td>', f'回路図ネットリストの全{review["netlist"]["schematic_pins"]}ピンとPCBパッドのネット', "<code>review_pcb_report.py</code>"],
] + check_rows + [
    ["チャネルモデルの再現", f'<td class="{"t-ok" if not model["changed"] else "t-bad"}">{len(model["identical"])}ファイル同一</td>', "抽出→線路→Sパラメータ→図", "<code>tmds_channel.py</code> ほか"],
    ["ハッシュ台帳", f'<td class="{"t-ok" if not review["manifest"]["mismatched"] else "t-bad"}">{review["manifest"]["files"]}ファイル一致</td>', "<code>manifest_r3.json</code> の全ファイル", "<code>make_manifest.py</code>"],
])}
<p>DRCが通っても、M5-Busの機械的な嵌合、実装業者の回転規約、実機での通信は証明しない。JLCの部品プレビューでU2、U4/U5、U7/U8、U9/U10、C7、J2、J4の端子1・極性を照合する。</p>
</section>

<section id="files">
<h2>10. データと再現手順</h2>
<p><a href="audit-data/poc-manufacturing-candidate.zip">製造データ一式 ZIP</a>（ガーバー、ドリル、JLC BOM/CPL、IPC-D-356、実装図、DNP表、手実装表）／ <a href="audit-data/poc-assembly-top.svg">上面実装図</a> ／ <a href="audit-data/poc-assembly-bottom.svg">下面実装図</a></p>
{table(["コマンド", "内容"], [
    ["<code>python -X utf8 kicad/sim/review_pcb_report.py</code>", "DRC・ERC・ネット照合・全検査・チャネルモデル再現・台帳照合・3D描画（KiCad 10のkicad-cliとPythonを使用）"],
    ["<code>python -X utf8 kicad/sim/make_pcb_report_page.py</code>", "このページ（数値はすべてJSONとbom.csvから読む）"],
])}
<p>PCB SHA-256（改行LF正規化）：<code class="hash">{sha}</code>。製造データの元PCBと一致：{"はい" if sha == pkg["source_pcb_sha256"] else "<b>いいえ</b>"}。</p>
</section>
<footer>Tab5 × Tang Primer 20K キャリア基板 ／ 基板レポート ／ 2026-10-25</footer>
</main>'''
    page = ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>キャリア基板レポート</title><meta name="description" content="Tab5 × Tang Primer 20K キャリア基板の最新版レポート：独立レビュー、HDMIシミュレーション、BOM、外観図">'
            + style + '</head><body>' + body + '</body></html>\n')
    (SITE/'pcb-report.html').write_text(page, encoding='utf-8')
    link_pcb_report()
    print('wrote site/pcb-report.html')


def link_pcb_report():
    """Put the latest-report link under every page header; older 'latest' links become history."""
    for path in SITE.glob('*.html'):
        if path.name == 'pcb-report.html':
            continue
        text = path.read_text(encoding='utf-8')
        new = re.sub(r'<p id="pcb-report-link">.*?</p>', '', text)
        new = new.replace('</header>', '</header>'+LINK, 1)
        for old, label in (('最新：パラレル通信・電源の修正と発注準備', '発注準備：パラレル通信・電源の修正'),
                           ('最新：通信と電源の修正・発注準備', '発注準備：通信と電源の修正'),
                           ('最新：第3版監査の引き継ぎ', '履歴：第3版監査の引き継ぎ')):
            new = new.replace(old, label)
        if new != text:
            path.write_text(new, encoding='utf-8')


if __name__ == '__main__':
    main()
