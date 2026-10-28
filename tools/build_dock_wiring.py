"""Generate the Dock wiring guide from the canonical Markdown pin table."""
from pathlib import Path
import base64
import html
import re

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'docs/Dockジャンパ試験_配線とFPGA構成_2026-10-28.md'
rows = []
for line in source.read_text(encoding='utf-8').splitlines():
    cells = [c.strip() for c in line.strip('|').split('|')]
    if len(cells) == 8 and re.fullmatch(r'D[0-7]|CLK|READY|DIR|AUX[0-3]', cells[0]):
        rows.append(cells)
assert len(rows) == 15

def text(x, y, value, size=18, fill='#19324a', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{html.escape(value)}</text>'

svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1600" role="img" aria-labelledby="title desc">',
       '<title id="title">Tab5とTang Primer 20K Dockのジャンパ配線図</title>',
       '<desc id="desc">上段はTab5裏面とDock公式写真の接続場所。下段は番号で照合する結線図。Dockのピン配列の物理的向きは未確認。</desc>',
       '<rect width="1200" height="1600" fill="#f4f7fb"/><g font-family="Yu Gothic,Meiryo,sans-serif">']
svg += [text(40, 45, 'Tab5 × Tang Primer 20K Dock', 30), text(40, 77, 'ジャンパ配線ガイド / LINK・GFX v0 / 実機未検証', 18)]
svg += ['<rect x="35" y="100" width="435" height="610" rx="24" fill="#e3e8ee" stroke="#8090a0"/>',
        text(60,135,'Tab5 裏面：電池区画を左へ',22),
        '<rect x="60" y="165" width="115" height="480" rx="14" fill="#c7ced7"/>',text(78,200,'電池区画',18),
        text(215,165,'M5-Bus（2列×15段）',16)]
pins = {int(r[2]): (r[0], r[1]) for r in rows}
for p in range(1,31):
    x = 275 if p%2 else 360
    y = 200 + ((p-1)//2)*31
    name = pins.get(p, ('GND','') if p in (1,3,5) else ('×',''))[0]
    color = '#64748b' if name=='GND' else '#b0b9c5' if name=='×' else '#8b5cf6' if name.startswith('AUX') else '#137a62'
    svg += [f'<circle cx="{x}" cy="{y}" r="11" fill="{color}"/>',text(x,y+4,str(p),11,'white','text-anchor="middle"'),
            text(x-18 if p%2 else x+18,y+5,name,13,'#19324a', 'text-anchor="end"' if p%2 else '')]
svg += [text(60,686,'×：本試験では接続しない',15)]
photo = base64.b64encode((ROOT/'docs/reference/tang-primer-20k/dock-up.png').read_bytes()).decode()
svg += [text(510,135,'Dock 部品面：USB端子を下へ',22),
        f'<image x="510" y="155" width="640" height="484" href="data:image/png;base64,{photo}"/>']
for label,x,width,color in [('J5',578,100,'#137a62'),('J12',828,90,'#2563eb'),('J14',952,90,'#d97706')]:
    svg += [f'<rect x="{x}" y="218" width="{width}" height="38" rx="4" fill="none" stroke="{color}" stroke-width="5"/>',
            text(x+width/2,208,label,20,color,'text-anchor="middle"')]
svg += [text(510,665,'写真：Sipeed公式Wiki / ヘッダの場所を示す',16),
        text(510,692,'旧版写真：各ヘッダ左下が1番（公式3709配置データ）',17,'#ad3c16'),
        text(40,754,'番号で照合する結線図',26),
        text(40,783,'下図の端点は読みやすく並べ替えています。Dockの物理ピン配列ではありません。',17)]
for i,r in enumerate(rows):
    name,gpio,mbus,dock,net,ball,bank,direction=r
    y=832+i*37
    color='#8b5cf6' if name.startswith('AUX') else '#2563eb' if name.startswith('D') and name!='DIR' else '#d97706'
    svg += [text(45,y+5,name,18,color),text(125,y+5,f'M5-Bus {mbus} / {gpio}',17),
            f'<path d="M 340 {y} H 440 m 50 0 H 650" stroke="{color}" stroke-width="3" fill="none"'+(' stroke-dasharray="7 5"' if name.startswith('AUX') else '')+'/>',
            f'<rect x="440" y="{y-9}" width="50" height="18" fill="white" stroke="{color}" stroke-width="2"/>',
            text(670,y+5,f'{dock}  {net}',17),text(990,y+5,'未接続で可' if name.startswith('AUX') else direction,15)]
svg += [text(345,1410,'各信号：220〜330ΩをTab5側近くへ / 線長15cm以下',18),
        '<path d="M 340 1450 H 650" stroke="#475569" stroke-width="6"/>',
        text(45,1456,'GND：M5-Bus 1 / 3 / 5',18),text(670,1446,'J12-3/4、J14-3/4、J5-3/4',18),
        text(670,1475,'3本以上、各ヘッダへ1本ずつ',17),
        text(40,1520,'電源レール同士は接続しない。本図の全ヘッダで1/2＝3.3V、3/4＝GND。',20,'#ad3c16'),
        text(40,1560,'AUXは今回不使用。GND併走。片側電源断の前に信号線を外す。',18),'</g></svg>']
(ROOT/'site/img/dock-jumper-wiring.svg').write_text('\n'.join(svg),encoding='utf-8', newline='\n')
# Electrical pin arrangement follows the schematic, not an unverified footprint.
dock_pins = {
    'J5': ['3.3V','3.3V','GND','GND','RGB_LCD_R0','RGB_LCD_R1','RGB_LCD_R2','RGB_LCD_R3','RGB_LCD_R4','RGB_LCD_G0','RGB_LCD_G1','RGB_LCD_G2'],
    'J12': ['3.3V','3.3V','GND','GND','DVP_D7','DVP_D6','DVP_D5','DVP_D4','DVP_D0','DVP_D3','DVP_D1','DVP_D2'],
    'J14': ['3.3V','3.3V','GND','GND','MIC_LED_CLK','MIC_LED_DAT','MIC_DAT1','MIC_DAT0','MIC_DAT2','MIC_DAT3','MIC_BCK','MIC_WS'],
}
assigned = {r[3]: r for r in rows}
ball_names={'J5':['3V3','3V3','GND','GND','L9','N8','N9','N7','N6','D11','A11','B11']}
detail = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1280" role="img" aria-labelledby="t d">',
          '<title id="t">Dockヘッダ全12ピンの回路図基準模式図</title>',
          '<desc id="d">J5、J12、J14。部品面・USB下。上段偶数、下段奇数で左から右へ増える。各端子に番号、ネット、用途、Tab5接続先を表示。</desc>',
          '<rect width="1200" height="1280" fill="#f4f7fb"/><g font-family="Yu Gothic,Meiryo,sans-serif">',
          text(35,48,'Dock ヘッダの番号と信号',30),
          text(35,83,'部品面・USB下：上段＝偶数、下段＝奇数。写真と同じ向き。',19),
          text(35,115,'J5の電源配置はユーザー確認シルク基準。1番は左下の四角。',18,'#ad3c16')]
for j,(header,nets) in enumerate(dock_pins.items()):
    top = 155+j*365
    detail += [text(35,top+25,header+' / '+{'J5':'RGB LCD','J12':'CAMERA / DVP','J14':'MIC ARRAY'}[header],25),
               text(35,top+55,'上：FPC・基板外周側 / 下：Core・USB側',17,'#ad3c16')]
    for p,net in enumerate(nets,1):
        x=35+((p-1)//2)*190
        y=top+75+(p%2)*120
        r=assigned.get(f'{header}-{p}')
        color='#be3030' if net=='3.3V' else '#475569' if net=='GND' else '#8b5cf6' if r and r[0].startswith('AUX') else '#137a62' if r else '#8995a5'
        detail += [f'<rect x="{x}" y="{y}" width="178" height="108" rx="9" fill="white" stroke="{color}" stroke-width="2"/>']
        if p==1:
            detail += [f'<rect x="{x+10}" y="{y+8}" width="30" height="30" fill="{color}"/>']
        else:
            detail += [f'<circle cx="{x+25}" cy="{y+23}" r="15" fill="{color}"/>']
        detail += [text(x+25,y+29,str(p),19,'white','text-anchor="middle"'),text(x+47,y+29,ball_names[header][p-1] if header in ball_names else net,14),
                   text(x+10,y+60,r[0] if r else '接続禁止' if net=='3.3V' else '共通GND' if net=='GND' else '本試験では未接続',17,color),
                   text(x+10,y+87,f'M5-Bus {r[2]} / {r[1]}' if r else '各ヘッダに1本以上' if net=='GND' else '電源レールは結ばない' if net=='3.3V' else '—',14)]
detail += [text(35,1270,'紫：AUX（今回未接続で可） / 緑：通信 / 灰：GND・未使用 / 赤：3.3V（接続禁止）',18),'</g></svg>']
(ROOT/'site/img/dock-header-pinout.svg').write_text('\n'.join(detail),encoding='utf-8', newline='\n')
# Photo orientation is corroborated by the official 3709 iBOM pin1 pads.
layout = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1110" role="img" aria-labelledby="pt pd">',
          '<title id="pt">旧版Dock写真上の1番ピン</title><desc id="pd">部品面、USB下。J5、J12、J14は左下が1番。上段偶数、下段奇数で左から右へ増える。公式3709配置データを根拠とし、3713や3714の実物確認とは区別する。</desc>',
          '<rect width="1200" height="1110" fill="#f4f7fb"/><g font-family="Yu Gothic,Meiryo,sans-serif">',
          text(30,42,'掲載写真の1番は、各ヘッダの左下',28),
          text(30,77,'部品面・USB端子を下。公式3709 iBOMのpin1座標と写真の信号シルクを照合。',18),
          f'<image x="180" y="100" width="840" height="635.25" href="data:image/png;base64,{photo}"/>']
for name,px in [('J5',59),('J12',244),('J14',337)]:
    x=180+px*1.75; y=100+66*1.75
    layout += [f'<rect x="{x-12}" y="{y-12}" width="24" height="24" fill="none" stroke="#ff482e" stroke-width="4"/>',
               f'<path d="M {x} {y-18} V 140" fill="none" stroke="#ff482e" stroke-width="3"/>',
               text(x,127,name+'-1',22,'#bd2417','text-anchor="middle"')]
layout += [text(40,780,'写真と同じ向きに展開した各ヘッダの番号',24)]
for j,name in enumerate(['J5','J12','J14']):
    x0=40+j*395
    layout += [text(x0,825,name,24),text(x0,852,'上：FPC・基板外周側',16)]
    for col in range(6):
        for row in range(2):
            n=col*2+(2 if row==0 else 1);x=x0+col*52;y=885+row*48
            layout += [f'<rect x="{x}" y="{y}" width="40" height="36" rx="{0 if n==1 else 8}" fill="{"#bd2417" if n==1 else "#19324a"}"/>',text(x+20,y+25,str(n),21,'white','text-anchor="middle"')]
    layout += [text(x0,1005,'下：Core・USB側',16)]
layout += [text(40,1050,'旧版写真のJ5：1/2＝3V3、3/4＝GND。3713系回路図のJ5は電源が逆。',20,'#ad3c16'),
           text(40,1085,'この番号方向は掲載写真・3709資料についての特定。手元の3713/3714は版と電源を照合。',18),'</g></svg>']
(ROOT/'site/img/dock-photo-pin1.svg').write_text('\n'.join(layout),encoding='utf-8',newline='\n')

table=''.join('<tr>'+''.join('<td>'+html.escape(c.replace('**',''))+'</td>' for c in r)+'</tr>' for r in rows)
page='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dockジャンパ配線ガイド | Tab5 × Tang Primer 20K</title><style>
body{margin:0;background:#f4f7fb;color:#19324a;font:16px/1.8 "Yu Gothic",Meiryo,sans-serif}main{max-width:1200px;margin:auto;padding:28px}h1{line-height:1.4}a{color:#1564bf}section{background:white;border-radius:16px;padding:24px;margin:24px 0}.warn{border-left:5px solid #d97706;background:#fff3df}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}td,th{padding:9px;border-bottom:1px solid #dce3ed;text-align:left}.scroll{overflow:auto}small{color:#526477}@media print{main{padding:0}section{break-inside:avoid}}</style>
<main><a href="index.html">← キャリア基板ドキュメント</a><h1>基板上の場所からたどる<br>Dockジャンパ配線ガイド</h1>
<p>Tab5のM5-Busと、Coreを装着した公式Tang Primer 20K Dockを接続します。LINK／GFX v0は信号11本＋共通GND。AUX0〜3は未接続で構いません。</p>
<section class="warn"><strong>配線案・実機未検証</strong><p>Dock写真はヘッダ位置の目印です。掲載写真の1番方向は旧版3709配置データで特定しました。現行版との電源割当の違いは下の「写真上の1番ピン」を参照してください。実物のシルクと回路図を照合し、Dock単体で電源・GNDを測定してから配線してください。このページはユーザー確認のJ5シルクに合わせ、J5の1/2を3.3V、3/4をGNDと表示しています。</p></section>
<section><a href="img/dock-jumper-wiring.svg" target="_blank">SVGを原寸で開く・保存する</a><img src="img/dock-jumper-wiring.svg" alt="Tab5裏面のM5-Bus配置、Dockの接続ヘッダ位置、15信号とGNDの結線図"></section>
<section id="photo-pin1"><h2>写真上の1番ピンを特定</h2><p>公式の旧版3709基板配置データでは、J5・J12・J14のpin1はそれぞれ左下です。掲載写真と同じ部品面・USB下の向きで、上段は2・4・6・8・10・12、下段は1・3・5・7・9・11と並びます。</p><a href="img/dock-photo-pin1.svg" target="_blank">番号付き写真SVGを開く</a><img src="img/dock-photo-pin1.svg" alt="部品面USB下の写真で、J5・J12・J14の左下を1番として表示。旧版3709の配置データに基づく。"><p class="warn">掲載の旧版写真はJ5も左端列が3V3、次がGNDです。一方、3713系回路図のJ5は1/2=GND、3/4=3.3V。以下の図・GND接続先はユーザーが確認したシルクに合わせています。版が異なる基板は電源配置を個別に照合してください。</p><p>根拠：<a href="https://dl.sipeed.com/shareURL/TANG/Primer_20K/03_Bit_number_map/Dock">Sipeed公式配置データ</a>のTang_Primer_20K_Dock_3709_ibom.html。pin1フラグ付き四角パッドが各ヘッダの左下。背面写真の信号順も照合しました。手元のJ5の信号・電源の並びはユーザーがシルクで確認済みです。基板の版と電圧実測は未確認です。</p></section>
<section id="dock-pinout"><h2>Dockヘッダのピン配置模式図</h2><p>J5・J12・J14の全12ピンを番号付きで示します。<strong>部品面・USB下で上段が偶数、下段が奇数</strong>。番号の横はDockの信号名（J5は実物シルクのFPGA ball名）、下は今回の用途とTab5の接続先です。1番ピンは四角で強調しています。</p><p class="warn">写真と同じ向きの模式図です。J5はユーザー確認シルク（上段：3V3/GND/N8/N7/D11/B11、下段：3V3/GND/L9/N9/N6/A11）を基準にしています。J12/J14は公式旧版配置資料に基づき、手元の実物確認は未完了です。</p><a href="img/dock-header-pinout.svg" target="_blank">ピン配置SVGを原寸で開く・保存する</a><img src="img/dock-header-pinout.svg" alt="J5・J12・J14それぞれの12ピン。番号、ネット名、今回の用途、M5-Bus接続先。写真と同じ向き。J5はユーザー確認シルク基準。"><details><summary>公式裏面写真と回路図の差異（配線前に確認）</summary><p>公式裏面写真ではRGB LCDのR0〜G2に対応するヘッダの電源端子が、端から3.3V、GNDの順に見えます。一方、保存済み回路図ではJ5の1/2がGND、3/4が3.3Vです。写真と回路図の版の対応は未確定です。旧版配置資料では写真上の1番は左下です。写真だけから番号を割り当てず、実物の版・導通・電圧を照合してください。</p><img style="max-width:720px" src="img/dock-back-reference.png" alt="Sipeed公式Dock裏面写真。各ヘッダのFPGA信号名と電源のシルクを確認する参考。部品面写真とは左右が反転。"><p>裏面写真は部品面と左右が反転します。資料名がDock_3714_Schematics.pdfでも、今回確認したPDF内の図枠はDock_3713、Rev 1.1、2023-09-12です。</p></details></section>
<section><h2>接続する順序</h2><ol><li>Dockの版（3713／3714）と各ヘッダの電源・GNDを測定。カメラ、RGB LCD、マイク、タッチを外します。</li><li>SW0をOFFにして、Tab5の対象GPIOが入力であることを確認。両ボードへ個別に給電し、共通GNDと信号を接続します。</li><li>各信号へ220〜330Ωを挿入。線長15cm以下、データ線2本ごとにGNDを併走します。電源レール同士は結びません。</li><li>LINK／GFXを書き込み、SW0 OFFのままKey_0でリセット。両側の電源とTab5の入力状態を再確認してSW0をON、ホスト側arm操作へ進みます。</li></ol><p>抵抗はIoff分離の代替ではありません。片側の電源を切る前に信号線を外してください。</p></section>
<section><h2>全信号の照合表</h2><div class="scroll"><table><thead><tr><th>信号</th><th>GPIO</th><th>M5-Bus</th><th>Dock</th><th>ネット</th><th>FPGA ball</th><th>Bank</th><th>向き</th></tr></thead><tbody>TABLE</tbody></table></div><p>GND：M5-Bus 1／3／5 → J12-3/4、J14-3/4、J5-3/4（3本以上、各ヘッダに1本）。</p><p>未接続：M5-Bus 12、25、27、28、29、30、およびDockの3.3V。AUXは今回不使用です。</p></section>
<section><h2>資料と確認範囲</h2><ul><li><a href="../docs/Dockジャンパ試験_配線とFPGA構成_2026-10-28.md">配線仕様の正本</a> / <a href="../docs/Dockジャンパ_GFXテスト手順.md">GFX試験手順</a></li><li><a href="https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html">Sipeed公式写真・製品資料</a>：Dock部品面のヘッダ位置を照合。写真は公式Wiki由来。</li><li>ピン対応：保存済みDock 3714回路図と配線正本。Tab5の向き：2026-10-24の実物確認記録。</li></ul><p>2026-10-28：既存仕様の図解化。GPIO・電源・コマンドの変更なし、全ホスト共通の配線。ホスト側への仕様同期は不要。詳細な参照版は<a href="../docs/Dock配線図_生成記録.md">生成記録</a>を参照。</p></section><small>生成：tools/build_dock_wiring.py / 写真の基板と手元の版は必ず照合してください。</small></main></html>'''.replace('TABLE',table)
page = page.replace('href="../docs/', 'href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/docs/')
(ROOT/'site/dock-jumper-wiring.html').write_text(page,encoding='utf-8', newline='\n')
print('Generated 15 signal rows, board locator SVG, HTML')
