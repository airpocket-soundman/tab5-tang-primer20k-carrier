"""Publish the fixed-revision R3 handover verification; markdown-it-py to render."""
from pathlib import Path
from urllib.parse import quote
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]
SITE=ROOT/'site'
SOURCE='HDMI_R3_監査引継ぎ確認_2026-10-24.md'
LINK='<p id="audit-handover-link"><a href="hdmi-audit-handover.html">最新：第3版監査の引き継ぎ・再確認（851adf4、24件の回帰試験と数値再現）</a></p>'


def link_handover():
    for name in ['hdmi-simulation-r3.html','hdmi-audit-checks.html','index.html']:
        path=SITE/name
        if not path.exists():continue
        text=path.read_text(encoding='utf-8')
        if 'id="audit-handover-link"' in text:continue
        if '<main class="wrap">' in text:
            text=text.replace('<main class="wrap">','<main class="wrap">\n'+LINK,1)
        else:
            text=text.replace('</header>','</header>\n'+LINK,1)
        path.write_text(text,encoding='utf-8')


def main():
    from markdown_it import MarkdownIt
    index=(SITE/'index.html').read_text(encoding='utf-8')
    style=index[index.index('<style>'):index.index('</style>')+8]
    body=MarkdownIt('commonmark',{'html':False}).enable('table').render((ROOT/'docs'/SOURCE).read_text(encoding='utf-8'))
    body=re.sub(r'^<h1>.*?</h1>\s*','',body,count=1)
    body=re.sub(r'(<table>.*?</table>)',r'<div class="tw">\1</div>',body,flags=re.S)
    for href in ['HDMI_R3_検査修正_2026-10-24.md',quote('HDMI_R3_検査修正_2026-10-24.md')]:
        body=body.replace('href="'+href+'"','href="hdmi-audit-checks.html"')
    page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>HDMI第3版：監査引き継ぎと再確認</title>{style}
    <style>article h2{{margin-top:36px}}article p,article li,td{{overflow-wrap:anywhere}}pre{{overflow:auto;padding:16px;background:var(--code)}}pre code{{padding:0}}</style></head>
    <body><header class="top"><div class="wrap"><p><span class="badge">引き継ぎ再確認・2026-10-24</span><span class="badge">固定対象851adf4</span></p>
    <h1>HDMI第3版：監査引き継ぎと再確認</h1><p class="sub">追加検査指摘の確認と、PoCに残る不確かさを分けて記録します。</p></div></header>
    <nav class="toc"><div class="wrap"><a href="index.html">設計仕様</a><a href="hdmi-simulation-r3.html">第3版シミュレーション</a><a href="hdmi-audit-checks.html">検査修正</a><a href="hdmi-audit.html">旧版の監査</a></div></nav>
    <main class="wrap"><div class="callout ok"><b class="t">検査修正を再確認</b>24件の回帰試験、8線の導通と負の試験、DRC、55ファイルのハッシュ、4ポート数値・複合感度を再検証しました。</div>
    <div class="callout warn"><b class="t">基板全体の製作承認・実機合格ではありません</b>D1Nの11.5mm枝、仮定の複合条件での目標外、3D較正と実機・電源断・PARLIOの未完了は継続します。</div>
    <p><a href="audit-data/handover_851adf4_2026-10-24.json">今回の再実行データ（JSON）</a> · <a href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/docs/{quote(SOURCE)}">Markdown原文</a></p>
    <article>{body}</article><footer><a href="hdmi-simulation-r3.html">第3版シミュレーションレポートへ戻る</a></footer></main></body></html>'''
    (SITE/'hdmi-audit-handover.html').write_text(page,encoding='utf-8')
    (SITE/'audit-data').mkdir(exist_ok=True)
    name='handover_851adf4_2026-10-24.json'
    shutil.copyfile(ROOT/'kicad/sim'/name,SITE/'audit-data'/name)
    link_handover()
    print('Published handover verification page and report links.')


if __name__=='__main__':main()
