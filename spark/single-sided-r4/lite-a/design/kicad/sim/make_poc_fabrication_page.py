"""Publish fabrication readiness and uniform-line calibration into GitHub Pages."""
from pathlib import Path
import re,shutil,zipfile
from markdown_it import MarkdownIt
ROOT=Path(__file__).resolve().parents[2]
LINK='<p id="poc-fabrication-link"><a href="poc-fabrication.html">発注準備：パラレル通信・電源の修正（M5-Bus向き確認・修正済み）</a></p>'
def main():
 index=(ROOT/'site/index.html').read_text(encoding='utf8');style=index[index.index('<style>'):index.index('</style>')+8]
 for source,name,title in [('PoC発注準備_パラレル通信と電源_2026-10-24.md','poc-fabrication.html','PoC発注準備と通信及び電源の検証'),('3D均一直線のポート校正_2026-10-24.md','uniform-line-calibration.html','3D均一直線のポート校正とメッシュ確認')]:
  text=(ROOT/'docs'/source).read_text(encoding='utf-8-sig').replace('(3D均一直線のポート校正_2026-10-24.md)','(uniform-line-calibration.html)')
  body=MarkdownIt('commonmark',{'html':False}).enable('table').render(text)
  body=re.sub(r'(<table>.*?</table>)',r'<div class="tw">\1</div>',body,flags=re.S)
  downloads='<p><a href="audit-data/poc-manufacturing-candidate.zip">少数PoC用 製造データ一式 ZIP</a> / <a href="audit-data/poc-assembly-top.svg">上面実装図</a> / <a href="audit-data/poc-assembly-bottom.svg">下面実装図</a> / <a href="audit-data/uniform-line-calibration.zip">3Dモデルと生波形</a></p>'
  (ROOT/'site'/name).write_text('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title>'+style+'</head><body><header class="top"><div class="wrap">2026-10-24 基板発注前の検証</div></header><main class="wrap"><nav><a href="index.html">設計仕様</a> / <a href="poc-fabrication.html">発注準備</a> / <a href="hdmi-simulation-r3.html">HDMI概算</a></nav>'+downloads+body+'</main></body></html>',encoding='utf8')
 for p in (ROOT/'site').glob('*.html'):
  if p.name in ('poc-fabrication.html','uniform-line-calibration.html'):continue
  s=p.read_text(encoding='utf8');s=re.sub(r'<p id="poc-fabrication-link">.*?</p>','',s)
  s=s.replace('</header>','</header>'+LINK,1).replace('最新：目的への独立評価・D1分岐の実修正','履歴：目的への独立評価・D1分岐の実修正')
  p.write_text(s,encoding='utf8')
 out=ROOT/'site/audit-data';out.mkdir(exist_ok=True)
 for name in ('top','bottom'):shutil.copy2(ROOT/f'manufacturing/poc-2026-10-24/assembly-{name}.svg',out/f'poc-assembly-{name}.svg')
 for source,target in [(ROOT/'manufacturing/poc-2026-10-24','poc-manufacturing-candidate.zip'),(ROOT/'docs/reference/openems/calibration-2026-10-24','uniform-line-calibration.zip')]:
  with zipfile.ZipFile(out/target,'w',zipfile.ZIP_DEFLATED) as z:
   for p in sorted(source.rglob('*')):
    if p.is_file():z.write(p,str(p.relative_to(source)).replace('\\','/'))
 print('published fabrication and calibration pages')
if __name__=='__main__':main()
