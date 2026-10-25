"""Publish a reproducible overview only when all independent audits pass."""
from pathlib import Path
import hashlib
import html
import json

ROOT=Path(__file__).resolve().parents[1]
V=ROOT/'variants'
BASE='https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/codex/lite-variants/'
configs=[('A','lite-a-dual','1・2・6・7','HDMI実装／USB PD＋バレル','99×78'),('B','lite-b-barrel','1・2・5・6・7','HDMI実装／バレルのみ','99×78'),('C','lite-c-dnp','1・2・3・5・7','HDMI・PDは回路を残してDNP／バレル使用','125×78')]
old=json.loads((ROOT/'cost-study/2026-10-25/cost-model.json').read_text(encoding='utf-8'))
bias_saving=.08+2*3.09-40*.0022
basic=old['basic_R7_saving']+old['basic_LDO_saving']
l1=old['L1_extended_alternative_saving']
size=old['small_board_saving_range']
prices={
 'A':[151.98-basic-bias_saving-l1-size[1],151.98-basic-bias_saving-l1-size[0]],
 'B':[151.98-basic-bias_saving-l1-old['barrel_only']['total_saving']-size[1],151.98-basic-bias_saving-l1-old['barrel_only']['total_saving']-size[0]],
 'C':[151.98-basic-l1-old['barrel_only']['total_saving']-old['hdmi']['total_saving']]*2}
rows=[]
for label,name,methods,functions,dimensions in configs:
 audit=json.loads((V/'validation'/f'{name}-independent-audit.json').read_text(encoding='utf-8'))
 assert audit['ok'],name
 pcb=V/name/'kicad/tab5-fpga-carrier.kicad_pcb'
 assert hashlib.sha256(pcb.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==audit['pcb_sha256'],name+' changed after audit'
 package=next((V/name/'manufacturing').glob('*/package-check.json'))
 m=json.loads(package.read_text(encoding='utf-8'))
 lo,hi=prices[label]
 cost=f'${lo:.2f}＋S' if lo==hi else f'${lo:.2f}〜{hi:.2f}＋S'
 rows.append(dict(label=label,name=name,methods=methods,functions=functions,dimensions=dimensions,
                  pcba=m['pcba_components'],bom_rows=m['pcba_bom_rows'],audit_checks=len(audit['checks']),
                  package=package.parent.relative_to(ROOT).as_posix(),price=cost,
                  pcb_sha256=audit['pcb_sha256']))
summary=dict(date='2026-10-25',status='design and routing checked; manufacturing-review candidates; not physically tested',
 baseline_preserved=True,original_release='d93af0b',currency='USD',quantity=5,cost_is_estimate_not_vendor_quote=True,
 socket_S='mandatory procurement/loading/PCBA/fixture cost, unquoted',Basic_510_unit_price_assumption=.0022,
 board_savings_range=size,rows=rows)
(V/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
md=['# 廉価版3案：設計・配線・検証結果','',
 '2026-10-25。3案の回路図、配線済みPCB、BOM/CPL、Gerberを別フォルダに作成した。現行125×78mm版は変更していない。全案でKiCad DRC違反0・未接続0、必須通信・電源検査と親側の独立照合を通過した。実機通信・DDR3・表示を動作確認した結果ではない。','',
 '| 案 | 方法＋ソケット変更 | 基板mm | 機能・実装 | PCBA部品/品目 | 製造候補 |','|---|---|---|---|---|---|']
for r in rows:
 md.append(f"| [{r['label']}]({r['name']}/README.md) | {r['methods']} | {r['dimensions']} | {r['functions']} | {r['pcba']}/{r['bom_rows']} | [発注用ファイル]({r['package'].removeprefix('variants/')}/) |")
md+=['','## 使うファイル','',
 '各製造候補フォルダの `gerbers.zip`、`jlc-bom.csv`、`jlc-cpl.csv` を同じ版で組み合わせる。組立図、手実装一覧、DNP一覧、ハッシュ検査結果も同梱している。J4は受けソケットとしてPCBAに含む。Core基板本体はユーザー支給。J1バレル、M5-Bus、ジャンパ等は手実装を含むため、手実装一覧を省略しない。','',
 '[共通設計仕様](DESIGN_SPEC.md)。各案のREADMEに生成・再検査方法と詳細結果を記録。Bは検証済みAの小型配置・配線を共通化してPD専用部を除去した派生版。Cは旧125mm基板の局所更新で元の信号線を保持した。','',
 '## 独立確認','',
 '作業エージェントの自己評価に加え、親側で実回路図からXMLを出力し、PCBの端子接続・部品値・フットプリント・実装設定を照合した。M5-Busの確認済み左右、全204端子と新ソケット図面の位置、必須部品の実装、BOMとCPLの一致、指定品番、座標原点、PCB版と製造データのハッシュを検査した。DRCも親側で実行した。KiCad既定の無効検査種別は元版から増やしていない。','']
for r in rows:md.append(f"- {r['label']}：[独立監査 {r['audit_checks']}項目](validation/{r['name']}-independent-audit.json)、[親側DRC](validation/{r['name']}-drc.json)。")
md+=['','HDMIはA/Bの実PCBから再抽出し、510Ωを使って4ポートモデルを再計算した。主配線の連続性・全区間分類・既定の分岐ビアの整合も確認した。499Ω→510Ω単一抵抗はBasic化しつつ追加8部品と配線干渉を避けるための変更。伝達変化約0.01dB・受信DC変化約5.9mVで、変更感度は小さい。ただしCore・新ソケット・ESDの不確かさは残る。','',
 '## 発注時・実機で残る確認','',
 '- 新ソケットC22471982の在庫割当、予備数、治具費、PCBA実装可否と端子向きのプレビュー。5.2mm高さの筐体干渉は実物未確認。','- 4層積層は解析条件JLC04161H-7628（F.Cu→GND 0.2104mm）との一致を確認する。Gerberのみで積層が指定されるわけではない。','- 12Vセンタープラス電源を使う。外部3.3V給電は禁止、室内PoC・周囲50℃以下・通常LDO負荷10mA以下の条件。','- FPGAとTab5のGPIO設定を確認してARMし、低速パラレル通信→Core DDR3試験へ進む。実物での実行は未確認。HDMIは640×480から720p60へ、短いケーブルと限定モニタで試す。1080p60を目標にしない。','',
 '## 5枚の費用参考','',
 '元見積$151.98を基にした再計算で、業者の正式再見積ではない。送料・税・Core本体・手実装部品・アダプタを含まない。Sは必須ソケットの調達・PCBA・治具等の追加費で、未確定。A/Bの幅は主にPCB特価の適用有無による。510Ω単価は$0.0022の予算仮定。CではHDMI未実装と抵抗Basic化を重複して引かず、小型化割引も引かない。','']
for r in rows:md.append(f"- {r['label']}：**{r['price']}**／5枚。")
md += ['','## HDMIの追加感度確認','',
 '新Aの実配線・510ΩでCore85/100/115Ω×ESD差動0.2/0.35/0.5pFを解析すると、9条件中1条件で自主反射目標−10dBを外れた。Core85Ω・ESD0.5pFのD2で約−9.17dB。さらに新ソケットのL/Cを仮置きした感度例では悪化する条件がある。[27条件の結果](validation/lite-a-dual-channel/uncertainty.json)。ソケットのL/Cは未校正の仮定で、全実物条件を包絡せず、不良率を表さない。HDMIの普遍的な動作保証とはしない。']
(V/'README.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
cards=[]
for r in rows:
 path=BASE+r['package']+'/'
 cards.append(f'''<article><h2>案{r['label']} <small>{r['dimensions']} mm</small></h2><p>方法 {r['methods']}＋ソケット変更</p><p>{r['functions']}</p><p><b>PCBA {r['pcba']}部品・{r['bom_rows']}品目</b></p><p>5枚参考 {r['price']}</p><figure><img src="img/lite-{r['label'].lower()}-assembly.png" alt="案{r['label']}の上面組立図"><figcaption>上面組立図。×印は未実装。</figcaption></figure><p><a href="{path}gerbers.zip">Gerber ZIP</a> ／ <a href="{path}jlc-bom.csv">BOM</a> ／ <a href="{path}jlc-cpl.csv">部品位置</a></p><p><a href="{BASE}variants/{r['name']}/README.md">設計・検証記録</a></p></article>''')
page='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>廉価版3案の設計・検証結果</title><style>
body{margin:0;background:#f5f7fa;color:#202933;font:16px/1.75 system-ui,"Meiryo",sans-serif}main{max-width:1100px;margin:auto;padding:30px 20px}h1{line-height:1.4}h2{font-size:1.4rem}small{font-size:1rem;color:#596777}a{color:#155bbc}article,.panel{padding:22px;background:white;border:1px solid #d8e0e8;border-radius:12px;margin:20px 0}figure{margin:16px 0}img{width:100%;height:auto;background:white}figcaption{font-size:.85rem;color:#596777}.ok{border-left:5px solid #218047}.warn{border-left:5px solid #bf850c}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.cards article{margin:0}.cards article:last-child{grid-column:1/-1}.cards article:last-child figure{max-width:800px}li{margin:8px 0}@media(max-width:760px){.cards{display:block}.cards article{margin:20px 0}}
</style></head><body><main><p><a href="pcb-report.html">← 現行版の基板レポート</a> ／ <a href="index.html">設計仕様トップ</a></p><h1>廉価版3案の設計・検証結果</h1><p>2026年10月25日。現行版を保持した別設計。</p><div class="panel ok"><b>3案とも配線済み。DRC違反0・未接続0。</b><p>必須通信・電源の検査に加え、親側で回路図とPCB、ソケット全204端子、実装設定、BOMと部品位置、製造データの版一致を独立確認しました。実機動作を確認した結果ではありません。</p></div><div class="cards">'''+''.join(cards)+'''</div><section class="panel"><h2>必須機能を保持</h2><p>Tab5との8bitパラレル通信、Coreへの独立5V、バスの電源断保護と両電源監視を保持。Core上DDR3を使うLinux／GPU用途の共通キャリアです。ソケットは全案PCBAに含め、Core本体はユーザー支給。バレル・M5-Bus等の手実装一覧も確認してください。</p><p>Aは自動配線とGND局所補修、BはAの検証済み小型配置を共通化してPD専用部を除去、Cは現行125mm版の局所変更で完成させました。</p></section><section class="panel warn"><h2>発注・実機で確認すること</h2><ul><li>新ソケットの在庫・治具・PCBA可否と向きのプレビュー。5.2mm高さの筐体干渉は実物未確認。</li><li>解析した4層積層との一致、12V電源、手実装範囲を確認。</li><li>外部3.3V給電は禁止。室内PoC、周囲50℃以下、通常LDO負荷10mA以下の条件。</li><li>低速パラレル通信とCore DDR3を実機で試す。HDMIは640×480から720p60へ進め、1080p60は目標外。</li></ul><p>HDMIの新510Ω負荷は差分解析上の影響が小さいものの、Core／ソケット／ESDの仮定には不確かさが残ります。HDMI規格適合や全機器動作保証ではありません。</p></section><section class="panel"><h2>費用と記録</h2><p>金額は5枚の比較計算で、正式再見積ではありません。Sは必須ソケットの調達・実装・治具等の未確定費。送料・税・Core本体・手実装部品は別です。幅は主にPCB特価の適用有無によります。</p><p><a href="'''+BASE+'''variants/DESIGN_SPEC.md">共通設計仕様</a> ／ <a href="'''+BASE+'''variants/README.md">結果と独立監査一覧</a></p></section></main></body></html>'''
page=page.replace('HDMIの新510Ω負荷は差分解析上の影響が小さいものの、Core／ソケット／ESDの仮定には不確かさが残ります。HDMI規格適合や全機器動作保証ではありません。', 'HDMIの510Ωへの変更感度は小さい一方、Core85Ω・ESD差動0.5pFの例では自主反射目標−10dBを外れます。新ソケットの未校正L/Cを置いた感度例でも悪化する条件があり、HDMI規格適合や全機器動作保証とはしません。詳細は共通設計仕様と27条件の解析結果に記録しています。')
(ROOT/'site/lite-variants.html').write_text(page,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=1))
