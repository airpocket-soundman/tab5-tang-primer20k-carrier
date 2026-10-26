"""Render the saved audit records for GitHub Pages (requires markdown-it-py).

python -X utf8 kicad/sim/make_audit_pages.py
"""
from pathlib import Path
from html import escape
from urllib.parse import quote
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]
SITE=ROOT/'site'
GH='https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/'
RECORDS=[
    ('シミュレーション再監査_6450c42_開発引継ぎ.md','hdmi-audit.html','シミュレーション再監査・開発引き継ぎ'),
    ('PoCシミュレーション_妥当性レビュー_2026-10-24.md','hdmi-audit-initial.html','PoCシミュレーション 初回レビュー記録'),
]
LINK='<a href="hdmi-audit.html">独立監査・開発引き継ぎ</a>'
NOTICE='''<div class="callout warn" id="audit-link"><b class="t">独立監査の結果</b>
<a href="hdmi-audit.html">6450c42の再監査・開発引き継ぎ</a>を公開しました。
保存数値は再現できましたが、監査対象版にはESDの導通想定と長い抵抗枝の問題が残ります。
「26か所の不連続」は解析用リストの問題で、PCBの26か所の断線を意味しません。
開発側ではTMDS連続配線・ESDシャント接続・499Ω抵抗の近接配置へ修正中です。修正版の是正完了は未判定です。</div>'''


def link_reports():
    for name in ['hdmi-simulation.html','index.html']:
        p=SITE/name
        if not p.exists():continue
        text=p.read_text(encoding='utf-8')
        if LINK not in text:
            text=text.replace('</div></nav>',LINK+'\n</div></nav>',1)
        if 'id="audit-link"' not in text:
            if name=='hdmi-simulation.html':
                text=text.replace('<section id="summary">','<section id="summary">\n'+NOTICE,1)
            else:
                text=text.replace('<h3>HDMI信号品質のシミュレーション</h3>',
                                  '<h3>HDMI信号品質のシミュレーション</h3>\n'+NOTICE,1)
        p.write_text(text,encoding='utf-8')


def main():
    from markdown_it import MarkdownIt
    index=(SITE/'index.html').read_text(encoding='utf-8')
    style=index[index.index('<style>'):index.index('</style>')+8]
    extra='''<style>
    article{padding:24px 0}article h2{margin-top:38px}article h3{margin-top:26px}
    article p,article li,td{overflow-wrap:anywhere}pre{overflow:auto;background:var(--code);padding:16px;border-radius:8px}
    pre code{padding:0}blockquote{border-left:4px solid var(--line);padding:4px 16px;margin:16px 0}
    .audit-toc{display:flex;gap:8px 18px;flex-wrap:wrap}.audit-toc a{font-size:.9rem}
    @media(max-width:600px){h1{font-size:1.4rem}.wrap{padding:0 12px}}
    </style>'''
    md=MarkdownIt('commonmark',{'html':False}).enable('table')
    for source,target,title in RECORDS:
        raw=(ROOT/'docs'/source).read_text(encoding='utf-8')
        body=md.render(raw)
        body=re.sub(r'^<h1>.*?</h1>\s*','',body,count=1)
        body=re.sub(r'(<table>.*?</table>)',r'<div class="tw">\1</div>',body,flags=re.S)
        toc=[]
        def heading(m):
            anchor='audit-section-'+str(len(toc)+1)
            toc.append((anchor,re.sub('<[^>]+>','',m[1])))
            return '<h2 id="'+anchor+'">'+m[1]+'</h2>'
        body=re.sub(r'<h2>(.*?)</h2>',heading,body)
        nav=''.join('<a href="#'+a+'">'+t+'</a>' for a,t in toc)
        source_url=GH+quote('docs/'+source,safe='/')
        evidence=''
        if target=='hdmi-audit.html':
            evidence='''<div class="card"><b>監査の根拠</b><ul>
            <li><a href="audit-data/audit_6450c42_2026-10-24.json">コミット済み入力からの数値再現・169条件の検証結果（JSON）</a></li>
            <li><a href="audit-data/audit_drc_6450c42_2026-10-24.json">DRC結果（JSON）</a></li>
            <li><a href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/kicad/sim/audit_committed_simulation.py">監査の再実行スクリプト</a></li>
            </ul></div>'''
        html=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
        <meta name="description" content="6450c42時点のHDMIシミュレーション監査。数値の再現性、モデルの限界、PoC試作条件と開発引き継ぎ。">
        {style}{extra}</head><body>
        <header class="top"><div class="wrap"><p><span class="badge">2026-10-24 監査記録</span><span class="badge">6450c42時点・修正版の判定ではありません</span></p>
        <h1>{escape(title)}</h1><p class="sub">数値の再現性と製作判断を分けて記録しています。</p></div></header>
        <nav class="toc"><div class="wrap"><a href="index.html">企画・設計仕様</a><a href="hdmi-simulation.html">シミュレーションレポート</a><a href="hdmi-audit.html">再監査</a><a href="hdmi-audit-initial.html">初回レビュー</a></div></nav>
        <main class="wrap"><div class="callout"><b class="t">修正の進捗（ユーザー報告）</b>
        TMDS線の連続配線、ESDの短いシャント接続、499Ω抵抗の信号線近傍への配置へ修正中です。この方針は妥当です。
        ESDの接続枝とGND経路を短くし、抵抗はAC結合コンデンサのHDMI側に接続、P/Nを対称にします。
        以下は修正前コミットへの監査記録です。修正版の実配線・再計算を確認するまで、是正済みとは判定しません。</div>
        <div class="card audit-toc">{nav}</div>{evidence}<article>{body}</article>
        <footer><a href="{source_url}">この記録のMarkdown原文</a> · <a href="hdmi-simulation.html">シミュレーションレポートへ戻る</a></footer></main></body></html>'''
        (SITE/target).write_text(html,encoding='utf-8')
    data=SITE/'audit-data';data.mkdir(exist_ok=True)
    for name in ['audit_6450c42_2026-10-24.json','audit_drc_6450c42_2026-10-24.json']:
        json.loads((ROOT/'kicad/sim'/name).read_text(encoding='utf-8'))
        shutil.copyfile(ROOT/'kicad/sim'/name,data/name)
    link_reports()
    print('Generated audit pages and linked simulation report/index.')


if __name__=='__main__':
    main()
