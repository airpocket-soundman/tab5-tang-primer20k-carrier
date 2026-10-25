"""Publish the purpose-oriented review and practical D1 correction."""
from pathlib import Path
import re
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[2]
LINK = '<p id="poc-purpose-review-link"><a href="poc-purpose-review.html">履歴：目的への独立評価・D1分岐の実修正（0.585mm、共通用途の残件）</a></p>'


def link_review():
    for name in ['index.html','hdmi-simulation-r3.html','hdmi-audit-handover.html','hdmi-audit-checks.html']:
        path = ROOT/'site'/name
        text = path.read_text(encoding='utf-8')
        if 'id="poc-purpose-review-link"' not in text:
            text = text.replace('</header>','</header>\n'+LINK,1)
        path.write_text(text,encoding='utf-8')


def main():
    source = ROOT/'docs/PoC目的適合性_独立評価とD1修正_2026-10-24.md'
    index = (ROOT/'site/index.html').read_text(encoding='utf-8')
    style = index[index.index('<style>'):index.index('</style>')+8]
    body = MarkdownIt('commonmark',{'html':False}).enable('table').render(source.read_text(encoding='utf-8').replace('(PoC発注準備_パラレル通信と電源_2026-10-24.md)','(poc-fabrication.html)'))
    body = re.sub(r'(<table>.*?</table>)',r'<div class="tw">\1</div>',body,flags=re.S)
    page = '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PoC目的への独立評価・D1修正</title>'+style+'</head><body><header class="top"><div class="wrap"><p>2026-10-24・独立評価と設計修正</p></div></header><main class="wrap"><nav><a href="index.html">設計仕様</a> / <a href="hdmi-simulation-r3.html">更新シミュレーション</a> / <a href="hdmi-audit-handover.html">修正前851adf4の確認</a></nav>'+body+'</main></body></html>'
    (ROOT/'site/poc-purpose-review.html').write_text(page,encoding='utf-8')
    link_review()


if __name__ == '__main__':
    main()
