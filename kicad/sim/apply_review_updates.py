"""One-shot: reflect the independent review findings (2026-10-24) in the pages and records. Idempotent (marker based)."""
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def rd(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def wr(p, s):
    open(os.path.join(ROOT, p), "w", encoding="utf-8").write(s)


def sub(s, a, b, count=1):
    assert a in s, a[:70]
    return s.replace(a, b, count)


ISSUES_HTML = """<section id="issues">
 <h2>設計レビューで判明した是正事項（試作前に必須）</h2>
 <p>別セッションによる独立レビュー（2026-10-24）と、その指摘の確認（データシート・実配線の再計算）の結果、<b>次の2点は設計の欠陥</b>であり、このページの「推定」結果の前提を損ないます。試作に進む前に是正します。</p>
 <div class="tw"><table>
  <thead><tr><th class="c">#</th><th>事項</th><th>確認した内容</th><th>対応</th></tr></thead>
  <tbody>
   <tr><td class="c t-bad">1</td><td><b>TMDS用ESD（RCLAMP0524P）の端子導通の想定が誤り</b></td><td>設計は、10ピン品の「入力（1/2/4/5）と出力（10/9/7/6）が部品内部でつながる（素通し）」と仮定して配線した。採用部品 C293965 は<b>DOWO製（DFN2510-10L）</b>で、データシート（Rev.G1.00）は「I/Oは1・2・4・5、GNDは3・8」と記載し、6/7/9/10の内部導通を保証していない。回路図とDRCは内部導通を前提にするため、この誤りを検出しない。</td><td>信号線はPCB上で連続した銅配線にし、ESDは分岐（シャント）として接続する。または内部導通が仕様で保証された部品に変更する。変更後に再配線・再解析。</td></tr>
   <tr><td class="c t-bad">2</td><td><b>499Ωバイアス抵抗の枝配線が長い</b></td><td>実配線を追跡すると、枝の長さは<b>21〜53mm</b>（CKNは53.5mm、P側29.2mmで非対称）。これまで「直流のみで影響しない」として解析から除外していたが、差動998Ωの並列負荷だけでSDD21が約−0.43dB・SDD11が約−26dB悪化し、53mmの枝は0.8GHz付近で1/4波長に相当する。</td><td>抵抗を信号線の分岐点の近く（数mm以下）に置き直し、P/Nを対称にする。枝は解析に含める。</td></tr>
  </tbody></table></div>
 <h3>その他の見直し</h3>
 <ul>
  <li><b>対象速度は720p60（0.74Gbps/レーン）に限定。</b>通常の1080p60（1.49Gbps/レーン）は、GW2Aの公開データシート（DS102 Table 3-17）の8:1/10:1シリアライザ上限1200Mbpsを超えるため、初版の保証条件に含めない。</li>
  <li><b>ペア内・ペア間スキューの基準を訂正。</b>TI SLLA414A §2.3は、ペア内0.15×Tbit、ペア間0.20×Tcharacterを示す（720p60で約200ps／約2.7ns）。5mmは自主的な保守的目標で、規格値ではない。「ペア間規定なし」は誤り。</li>
  <li><b>ESD容量の仮定を訂正。</b>差動0.15pFは根拠が弱い。DOWO資料は、I/O−GND 0.4pF（最大0.5pF）、I/O−I/O 0.2pF（最大0.3pF）。差動0.2〜0.5pFを仮定の感度範囲として使う。</li>
  <li><b>差動インピーダンスの数値。</b>間隔0.13mmの直接解は約103〜104Ω（以前の107Ωは0.15mmの値で代用していた）。2Dソルバと概算式の一致をもって保証誤差とは言わない。</li>
  <li><b>Coreの影響をゼロとは言わない。</b>Core側を85〜115Ωに振ると、720p帯でSDD11は−12〜−16dB程度まで悪化する（レビューの試算）。長さ一致だけでは100Ωの証明にならない。</li>
  <li><b>公式の基板配線データは「非公開」ではなく「未取得・公開確認できず」</b>と表現する。</li>
  <li><b>3D解析（openEMS）は未較正のため採用しない</b>（7章）。</li>
 </ul>
 <div class="callout warn"><b class="t">この結果の位置づけ（訂正）</b>ペア配線による<b>配線方式の改善</b>（スキュー0.00mm、結合区間約104Ω）は、実配線から確認できています。一方、<b>チャネル全体のS パラメータは上記2点を含まない推定</b>であり、「合格」とは言えません。是正後に再抽出して確認します。目標は<b>短いケーブル・限定したモニタでの720p60のPoC動作</b>で、動作保証・全機器互換・HDMI規格適合を意味しません。</div>
</section>

"""


def page_hdmi():
    p = "site/hdmi-simulation.html"
    s = rd(p)
    if 'id="issues"' in s:
        return
    s = sub(s, '<span class="badge">推定値（3D解析は較正中）</span>', '<span class="badge">推定値（3D解析は較正中）</span><span class="badge" style="background:var(--badbg);color:var(--bad);border-color:var(--bad)">試作前に是正が必要な事項あり</span>')
    s = sub(s, '<a href="#summary">結論</a>', '<a href="#summary">結論</a><a href="#issues">是正事項</a>')
    s = sub(s, '<div class="callout ok"><b class="t">設計上の判断</b>最初の配線（P/Nを個別に配線）は不合格（差動インピーダンス約160Ω、スキュー最大13mm）でした。P/Nを1本の太い線として引いて2本に分けるペア配線をルータに実装し、<b>4組すべてが設計目標内</b>に入りました（推定値）。</div>',
            '<div class="callout ok"><b class="t">改善できたこと</b>最初の配線（P/Nを個別に配線）は不合格（差動インピーダンス約160Ω、スキュー最大13mm）でした。P/Nを1本の太い線として引いて2本に分けるペア配線をルータに実装し、<b>配線方式としては4組すべてが目標内</b>に入りました（実配線から確認）。</div>\n <div class="callout bad"><b class="t">ただし「合格」ではありません</b>独立レビューで、<b>ESD部品の端子導通の想定が誤っていた</b>こと、<b>499Ω抵抗の枝が長い</b>ことが判明しました。下の「是正事項」のとおり、試作前に是正します。以下のSパラメータは、これらを含まない推定です。</div>')
    s = sub(s, '<section id="scope">', ISSUES_HTML + '<section id="scope">')
    s = sub(s, '<tr><td>ペア内スキュー</td><td>5mm未満（約30ps）</td><td>HDMI設計ガイドの一般値</td></tr>',
            '<tr><td>ペア内スキュー</td><td>5mm未満（約30ps）。参考：720p60のペア内0.15×Tbit≒200ps</td><td>5mmは自主的な保守目標。TI SLLA414A §2.3：ペア内0.15×Tbit、ペア間0.20×Tcharacter</td></tr>')
    s = sub(s, '<tr><td>対象速度</td><td>720p60（0.74Gbps/レーン）〜1080p60（1.49Gbps/レーン）</td><td>初版の想定</td></tr>',
            '<tr><td>対象速度</td><td><b>720p60（0.74Gbps/レーン）</b>。1080p60（1.49Gbps/レーン）は保証対象外</td><td>GW2Aのシリアライザ上限1200Mbps（DS102 Table 3-17）を超える</td></tr>')
    s = sub(s, '<b>公式の基板配線データは非公開</b>のため', '<b>公式の基板配線データは未取得（公開を確認できず）</b>のため')
    s = sub(s, '<td>AC結合キャップは ESL 1.4nH（差動）、ESDは差動0.15pF。</td>', '<td>AC結合キャップは ESL 1.4nH（差動）、ESDは差動0.15pF。</td>') if False else s
    s = sub(s, '<li>AC結合キャップは ESL 1.4nH（差動）、ESDは差動0.15pF。</li>', '<li>AC結合キャップは ESL 1.4nH（差動）、ESDは差動0.15pF（<b>仮定。DOWO資料はI/O−GND 0.4〜0.5pF</b>。是正事項）。ESDは信号線の途中に素通しで入る形でモデル化（<b>誤り。是正事項1</b>）。</li>')
    s = sub(s, '<li>499Ωバイアス抵抗の枝配線は信号経路から除外（直流のみで、高周波では開放に近い）。</li>', '<li>499Ωバイアス抵抗の枝配線は信号経路から除外（<b>誤り。枝が21〜53mmあり、並列負荷としても無視できない。是正事項2</b>）。</li>')
    s = sub(s, '<td class="c">104Ω</td><td class="c">IPC-2141差動式 約98.7Ω</td><td>式は概算（±10%程度）</td>', '<td class="c">104Ω（直接解は約103Ω）</td><td class="c">IPC-2141差動式 約98.7Ω</td><td>式は概算（±10%程度）。以前の107Ωは0.15mmの値で代用していた</td>')
    s = sub(s, '<h2>5. チャネル推定（Sパラメータ）</h2>', '<h2>5. チャネル推定（Sパラメータ）— 是正前の推定</h2>\n <div class="callout warn"><b class="t">注意</b>この節の値は、ESDの素通しと499Ω枝の除外を前提にした<b>是正前の推定</b>です。是正後に再計算します。</div>')
    s = sub(s, '<tr><td>最終判断</td><td><b>試作基板でのTDRとアイパターン測定</b></td></tr>', '<tr><td>是正事項1・2（ESD端子導通、499Ω枝）</td><td><b>試作前に是正し、再配線・再抽出・再解析</b></td></tr>\n   <tr><td>最終判断</td><td>PoCでは<b>短いケーブル・限定モニタでの720p60の表示確認</b>（30分程度）。TDR・アイ測定は不調時の切り分けと次版の改善用</td></tr>')
    s = sub(s, '<ul>\n  <li>2026-10-24：結合区間の差動インピーダンスを107Ω→104Ωに訂正', '<ul>\n  <li>2026-10-24：独立レビューの指摘を反映。ESDの端子導通の想定誤り、499Ω枝の長さ、対象速度（720p60に限定）、スキュー基準の根拠、ESD容量の仮定を訂正・追記（是正事項の章）。</li>\n  <li>2026-10-24：結合区間の差動インピーダンスを107Ω→104Ωに訂正')
    wr(p, s)


def page_index():
    p = "site/index.html"
    s = rd(p)
    if "試作前に是正が必要" in s:
        return
    s = sub(s, '<tr><td>HDMI TMDS</td><td><b>ペア内スキュー0.00mm（4組すべて）</b>、結合区間の差動インピーダンスは約104Ω（2Dソルバ）。Core基板内の配線（約38mm）は理想線路として扱った推定</td><td class="c t-ok">目標内（推定）</td></tr>',
            '<tr><td>HDMI TMDS</td><td><b>ペア内スキュー0.00mm（4組すべて）</b>、結合区間の差動インピーダンスは約104Ω（2Dソルバ）。ただし<b>ESD部品の端子導通の想定が誤り、499Ω抵抗の枝が21〜53mmと長い</b>ことが判明（<a href="hdmi-simulation.html#issues">是正事項</a>）</td><td class="c t-bad">試作前に是正</td></tr>')
    s = sub(s, '<div class="callout ok"><b class="t">詳細レポート</b>', '<div class="callout bad"><b class="t">是正事項（試作前に必須）</b>TMDS用ESD（RCLAMP0524P）は、採用部品（DOWO製）の仕様上、入力と出力が内部でつながる保証がありません。また、499Ωバイアス抵抗の枝配線が長く、高周波では無視できません。目標は<b>720p60のPoC</b>（1080p60はGW2Aのシリアライザ上限を超えるため対象外）。詳細は<a href="hdmi-simulation.html#issues">レポート</a>。</div>\n <div class="callout ok"><b class="t">詳細レポート</b>')
    s = sub(s, '<li>RCLAMP0524P（USON-10）の実フットプリントと、499Ωの部品区分を確認する。</li>', '<li><b>【必須】TMDS用ESDの端子導通を是正する</b>（信号線は連続配線にしてESDを分岐接続、または内部導通が保証された部品に変更）。<b>499Ω抵抗の枝を数mm以下に短縮</b>する。是正後に再配線・再解析。</li>\n   <li>RCLAMP0524Pの実フットプリント（DOWO DFN2510-10L）と、499Ωの部品区分を確認する。</li>')
    s = sub(s, '<tr><th>想定解像度</th><td>720p60〜（測定）</td><td>720p60程度まで（測定）</td></tr>', '<tr><th>想定解像度</th><td><b>720p60を目標</b>（1080p60はGW2Aのシリアライザ上限により保証対象外）</td><td>720p60程度まで（測定）</td></tr>')
    wr(p, s)


def doc_audit():
    p = "docs/シミュレーション方針と監査記録.md"
    s = rd(p)
    if "## 9. 独立レビュー" in s:
        return
    s = sub(s, "### 5.2 最終配線（ペア配線ルータ導入後）— 合格（推定）", "### 5.2 最終配線（ペア配線ルータ導入後）— 配線方式の改善は確認。**ただし是正事項あり（§9）。「合格」とは言えない**")
    s = sub(s, "| ペア間スキュー | 規定なし（チャネル間デスキューは受信側）。参考として 17 mm 以内 | 初期検討（`docs/HDMI_信号品質_調査と方針.md` §6） |", "| ペア間スキュー | TI SLLA414A §2.3: 0.20×Tcharacter（720p60 で約 2.7 ns）。参考として 17 mm 以内 | 以前の「規定なし」は誤り（§9 で訂正） |")
    s = sub(s, "| 対象信号速度 | 720p60 = 0.74 Gbps/lane、1080p60 = 1.49 Gbps/lane（TMDS 10bit） | 初版は〜1080p |", "| 対象信号速度 | **720p60 = 0.74 Gbps/lane を目標**。1080p60 = 1.49 Gbps/lane は GW2A のシリアライザ上限（1200 Mbps、DS102 Table 3-17）を超えるため対象外 | §9 で訂正（以前は〜1080p） |")
    s = sub(s, "4. AC 結合キャップは ESL 1.4 nH（差動、2×0.7 nH）、ESD は差動 0.15 pF（0.3 pF/線の並列）。\n5. バイアス抵抗（499 Ω）の枝配線は信号経路から除外（DC のみで、高周波では開放に近い）。", "4. AC 結合キャップは ESL 1.4 nH（差動、2×0.7 nH）、ESD は差動 0.15 pF（0.3 pF/線の並列）。**ESD は入出力が内部でつながる素通しとしてモデル化したが、採用部品でその保証はない（§9 A）。容量も仮定（§9）。**\n5. バイアス抵抗（499 Ω）の枝配線は信号経路から除外した。**誤り：枝は 21〜53 mm あり、並列負荷としても無視できない（§9 B）。**")
    s = s.rstrip() + """

## 9. 独立レビュー（別セッション、2026-10-24）の指摘と確認結果

別セッションが、この記録と解析コードを独立にレビューした。指摘のうち、**次の 2 点を自分でも確認し、設計の欠陥と認めた**。

### A. TMDS 用 ESD の端子導通の想定が誤り（試作前に必須の是正）
- 設計（`kicad/gen/design.py`）は U4/U5 を LCSC C293965 とし、10 ピンの入力（1/2/4/5）と出力（10/9/7/6）が部品内部でつながる素通しとして配線した。
- 確認: C293965 は **DOWO 製 RCLAMP0524P（DFN2510-10L）**。データシート Rev.G1.00 p.2 に「I/O pins are pin 1,2,4,5, GND pins are pin 3,8」とある。6/7/9/10 の内部導通は保証されない。公式 Dock の回路図の記号を根拠に別メーカー部品の内部導通は仮定できない。
- DRC・回路図の照合は部品内部の導通を前提にするため、この誤りを検出しない。
- 対応: 信号線を PCB 上で連続した銅配線にし、ESD は分岐（シャント）で接続する。または内部導通が仕様で保証された部品へ変更。変更後に再配線・再抽出・再解析。

### B. 499 Ω バイアス抵抗の枝配線が長い
- 確認（実配線）: 枝の長さは D0P 21.0／D0N 23.3／D1P 20.9／D1N 31.7／D2P 29.8／D2N 32.3／CKP 29.2／**CKN 53.5 mm**。P/N で非対称。`stub_tracks.json` は CKN の枝を記録できていなかった（解析の記録漏れ）。
- 以前の「DC のみで高周波では開放に近い」は誤り。差動 998 Ω の並列負荷だけで SDD21 約 −0.43 dB、SDD11 約 −26 dB（レビューの試算）。53 mm の枝は約 0.8 GHz で 1/4 波長に相当する。
- 対応: 抵抗を信号線の分岐点の近く（数 mm 以下、可能なら 1〜2 mm）へ置き直し、P/N を対称にする。枝は解析に含める。

### C. その他の訂正・追記
| 項目 | 訂正 |
|---|---|
| ペア間スキュー | 「規定なし」は誤り。TI SLLA414A §2.3: ペア内 0.15×Tbit、ペア間 0.20×Tcharacter（720p60 で約 200 ps／約 2.7 ns）。5 mm は自主的な保守目標 |
| 対象速度 | 通常の 1080p60（1485 Mbps）は GW2A のシリアライザ上限 1200 Mbps を超える。**720p60 に限定**。1080p30 は同じ線路速度でもモニタ対応の別確認が必要 |
| ESD 容量 | 差動 0.15 pF は根拠が弱い。DOWO 資料は I/O−GND typ.0.4/max.0.5 pF、I/O−I/O typ.0.2/max.0.3 pF。差動 0.2〜0.5 pF を**仮定の感度範囲**として使う |
| 差動インピーダンス | 実間隔 0.13 mm の直接解は約 103〜104 Ω。107 Ω は 0.15 mm の値の代用だった（§6.4 で訂正済み） |
| Core の影響 | 長さ一致だけでは 100 Ω の証明にならない。Core 側を 85〜115 Ω に振ると、720p 帯で SDD11 が −12〜−16 dB 程度まで悪化する（レビューの試算） |
| 公式の基板データ | 「非公開」ではなく「未取得・公開確認できず」と表現する |
| チャネル推定の合否 | 内層・ビアの 100 Ω 置換、ESD の素通し、枝の除外を残した推定から「合格」と断定できない。**§5.2 の表現を訂正** |
| 区間の順序 | レビュー時点のコードは Core 側を単純に逆順にしており、電気的な経路順ではなかった。本記録の §6.4 のとおり、接続をたどって並べる方式に修正済み |
| 3D 解析 | 較正未了で採用しない判断は妥当。2D 値に合うまで調整することは検証ではない |

### D. 目標の再設定（PoC）
- 目標は量産品質ではなく、**短いケーブル・限定したモニタでの 720p60 の表示確認（30 分程度）**。動作保証・全機器互換・HDMI 規格適合は意味しない。
- Core 全体の 3D 解析、HDMI 認証、試作前の TDR・アイ測定は、今回の製作条件としては必須としない（不調時の切り分け・次版の改善用）。
- 製作前に残す確認: ESD の実部品・端子・フットプリント、P/N と D2 の反転方針（TMDS エンコード後・差動バッファ前の全シリアルビットを反転）、499 Ω 枝の短縮、積層指定（JLC04161H-7628）、電源・機構の確認。

> 本節の元になったレビュー文書は別セッションの作業物で、この記録のコミットには含めていない。数値の根拠となる再計算は、本記録の §6 および `kicad/sim/` のスクリプトで再現できる範囲に限る。
"""
    wr(p, s)


def doc_hdmi():
    p = "docs/HDMI_信号品質_調査と方針.md"
    s = rd(p)
    if "## 8. 是正が必要な事項" in s:
        return
    s = s.rstrip() + """

## 8. 是正が必要な事項（独立レビューによる、2026-10-24）

詳細と確認結果は `docs/シミュレーション方針と監査記録.md` §9。要点:

1. **TMDS 用 ESD の端子導通の想定が誤り**: §1 の表の「RCLAMP0524P ×2（4ch、10 ピン、素通し）」は、採用部品 C293965（DOWO 製、DFN2510-10L）では保証されない（I/O は 1/2/4/5、GND は 3/8）。信号線は連続配線にし、ESD は分岐接続にする必要がある。
2. **499 Ω 枝配線が長い（21〜53 mm）**: §7 の「バイアス抵抗は信号経路から外した」は評価から外してよい根拠にならない。抵抗を分岐点の近くに置き直す。
3. **対象速度は 720p60**: 1080p60 は GW2A のシリアライザ上限（1200 Mbps）を超える。
4. §3 の「ペア間スキュー：規定なし」は誤り（TI SLLA414A §2.3：ペア間 0.20×Tcharacter）。5 mm は自主目標。
5. §7 の結果表は、1・2 を含まない**是正前の推定**。是正後に再配線・再解析する。
"""
    wr(p, s)


def readme():
    p = "kicad/README.md"
    s = rd(p)
    if "Known issues" in s:
        return
    s = s.rstrip() + """

## Known issues (must be fixed before ordering)
* **TMDS ESD (U4/U5, LCSC C293965 = DOWO RCLAMP0524P, DFN2510-10L)**: the board assumes the IN pins (1/2/4/5) are internally connected to the OUT pins (10/9/7/6). The vendor datasheet only defines I/O = pins 1,2,4,5 and GND = 3,8, so this is **not guaranteed**. Route each TMDS line as continuous copper and connect the ESD as a shunt tap, or use a part with a guaranteed flow-through.
* **499 ohm bias resistors** hang on 21-53 mm branches (CKN 53.5 mm). Move them to the tap points (a few mm).
* Target is **720p60 only** (1080p60 exceeds the GW2A serializer limit of 1200 Mbps).
* The HDMI channel estimate (`docs/HDMI_信号品質_調査と方針.md`) does not include the two items above; re-run it after the fix.
"""
    wr(p, s)


if __name__ == "__main__":
    page_hdmi()
    page_index()
    doc_audit()
    doc_hdmi()
    readme()
    print("updated")
