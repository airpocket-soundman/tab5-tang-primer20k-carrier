"""Render each evaluation's assembly scope from its actual manufacturing CSVs."""
from pathlib import Path
import csv
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/codex/lite-variants/'
START, END = '<!-- BOM START -->', '<!-- BOM END -->'

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def refs(rows, key):
    return {x.strip() for r in rows for x in r[key].split(',')}

def main():
    for label, name in [('a', 'lite-a-dual'), ('b', 'lite-b-barrel'), ('c', 'lite-c-dnp')]:
        folder = ROOT / 'variants' / name
        package = next((folder / 'manufacturing').glob('*/package-check.json')).parent
        pcba = read(package / 'jlc-bom.csv')
        manual = read(package / 'manual-assembly.csv')
        dnp = read(package / 'dnp.csv')
        sets = [refs(pcba, 'Designator'), refs(manual, 'Refs'), refs(dnp, 'Refs')]
        assert all(not sets[i] & sets[j] for i in range(3) for j in range(i))
        assert set.union(*sets) == refs(read(folder / 'kicad/bom.csv'), 'Refs')
        assert 'J4' in sets[0] and not {'J6', 'J7', 'J8'} & sets[0]
        assert {'J6', 'J7', 'J8'} <= sets[2]
        rows = []
        for source, key, status in [(pcba, 'Designator', 'PCBA実装'), (manual, 'Refs', '別途取り付け'), (dnp, 'Refs', '未実装（DNP）')]:
            for r in source:
                rr = r[key].split(',')
                action = status
                if all(x.startswith('H') for x in rr):
                    action = '取付穴（電子部品の実装なし）'
                elif set(rr) <= {'J6', 'J7', 'J8'}:
                    action = 'PCBA対象外・必要時にユーザー取り付け'
                value = r.get('Comment', r.get('Value', ''))
                rows.append([r[key], value, str(len(rr)), r['Footprint'], r.get('LCSC Part #', ''), action])
        body = ''.join('<tr>' + ''.join('<td>' + html.escape(x) + '</td>' for x in row) + '</tr>' for row in rows)
        links = ' ／ '.join(f'<a href="{BASE}{(package / f).relative_to(ROOT).as_posix()}">{text}</a>' for f, text in [('jlc-bom.csv', 'PCBA BoM'), ('manual-assembly.csv', '別途取り付け一覧'), ('dnp.csv', 'DNP一覧')])
        digest = hashlib.sha256((folder / 'kicad/tab5-fpga-carrier.kicad_pcb').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        procurement = ''
        purchase_file = folder / 'manual-parts-procurement.json'
        if purchase_file.exists():
            guide = json.loads(purchase_file.read_text(encoding='utf-8'))
            purchase_rows = ''.join('<tr>' + ''.join('<td>' + html.escape(str(r[k])) + '</td>' for k in ('refs','qty','part')) + '<td><a href="' + html.escape(r['url'], quote=True) + '">' + html.escape(r['supplier']) + '</a></td><td>' + html.escape(r['status'] + '。' + r['note']) + '</td></tr>' for r in guide['items'])
            procurement = '<h3>手実装品の購入先：秋月を優先</h3><p>J5 HDMIはPCBAに含めました。お客様がHDMIをはんだ付けする前提ではありません。19端子に加え4本のスルーホール固定タブも業者実装の指示に含めます。最終見積・実装プレビューで対応を確認してください。</p><p>ヘッダー・ジャンパー・任意ソケットは秋月で調達する候補です。スイッチは現基板との適合を優先し他店調達が残ります。J1は無加工互換未確定で、まだ購入確定品として扱いません。在庫は確認時点の表示で取り置きではありません。</p><div style="overflow-x:auto"><table><tr><th>対象</th><th>数量/枚</th><th>部品</th><th>購入先</th><th>適合・注意</th></tr>' + purchase_rows + '</table></div>'
        fragment = f'''{START}<section id="bom"><h2>BoMと実装範囲</h2>
<p>PCBAは{len(sets[0])}部品・{len(pcba)}品目。J4 SO-DIMMソケットはPCBA必須。Tang Primer 20K Core本体はユーザー支給で、PCBA発注BoMに含めません。</p>
<p>「別途取り付け」は手はんだ等が必要です。GPIO・PMODのJ6/J7/J8はPCBA対象外で、必要な場合のみユーザーが取り付けます。DNP部品は原則取り付けません。取付穴の行は購入する電子部品ではありません。</p>
<p>{links}</p><div style="overflow-x:auto"><table class="bom-table"><thead><tr><th>参照番号</th><th>部品・値</th><th>数量/枚</th><th>フットプリント</th><th>LCSC品番</th><th>実装区分</th></tr></thead><tbody>{body}</tbody></table></div>
<p><small>製造候補CSVから生成。基板SHA-256: {digest}。追加シミュレーションに伴う設計更新時はBoMも再生成します。</small></p>{procurement}</section>{END}'''
        page = ROOT / 'site' / f'lite-{label}-evaluation.html'
        if page.exists():
            text = page.read_text(encoding='utf-8')
            assert START in text and END in text
            text = text[:text.index(START)] + fragment + text[text.index(END) + len(END):]
        else:
            text = f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>案{label.upper()} 評価・BoM</title>
<style>body{{font:16px/1.7 system-ui;max-width:1200px;margin:auto;padding:24px;color:#202933}}a{{color:#155bbc}}table{{border-collapse:collapse;font-size:14px}}td,th{{border:1px solid #ccd3da;padding:8px;text-align:left}}th{{background:#edf2f7}}small{{overflow-wrap:anywhere}}</style>
<p><a href="lite-variants.html">← 3案の比較</a></p><h1>案{label.upper()} {name}：評価・BoM</h1>
<p>追加シミュレーションと修正の検証中です。以下は現時点の製造候補の実装区分で、最終発注可否の判定は更新予定です。</p>
{fragment}</html>'''
        page.write_text(text, encoding='utf-8')
        print(json.dumps(dict(variant=name, pcba=len(sets[0]), manual=len(sets[1]), dnp=len(sets[2])), ensure_ascii=False))

if __name__ == '__main__':
    main()
