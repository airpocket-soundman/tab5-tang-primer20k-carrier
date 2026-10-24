"""Publish the R3 checker-fix addendum from the committed regression JSON."""
import html
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
records=[json.loads((HERE/name).read_text()) for name in ('regression_esd.json','regression_classification.json')]
if not all(r['ok'] and r['tests']==len(r['cases']) for r in records):
    raise SystemExit('Regression evidence is incomplete or failed')
rows=[]
for title,record in zip(('ESDランド','配線・分類・ビア'),records):
    for case in record['cases']:
        rows.append('<tr><td>'+title+'</td><td>'+html.escape(case['case'])+'</td><td>'+('正常として受理' if case['expected_ok'] else '不正として拒否')+'</td><td>'+str(case['exit_code'])+'</td></tr>')
count=sum(r['tests'] for r in records)
text='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>第3版監査の検査修正 | Tab5 carrier</title>
<style>body{font:16px/1.7 system-ui,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#18252c;background:#f5f7f6}table{border-collapse:collapse;width:100%;background:white}th,td{padding:.45rem;border:1px solid #ccd3d3;text-align:left}code{overflow-wrap:anywhere}a{color:#075a80}.table{overflow:auto}</style>
<header><a href="index.html">キャリア仕様</a> / <a href="hdmi-simulation-r3.html">第3版チャネルレポート</a></header>
<h1>第3版監査の検査修正</h1><p>2026-10-24。対象基準版：91dc3b4。回路・PCB・描画／転送性能は変更していません。</p>
<p>R3-01（配置済みランド）、R3-02（配線幅・区間分類）、R3-03（D2説明）へ対応しました。検査修正は、実機のHDMI動作や3D較正の合格を意味しません。</p>
<ul><li>基板に埋め込まれたU4/U5のパッドを、回転・裏面配置も含めてライブラリと比較。部品・番号・寸法・位置・層・マスク／ペーストの変更を検出します。</li>
<li>中心線だけでなく幅を比較し、全長を区間へ分割して未分類・二重分類・stale区間を検出。ビアは径0.6mm・ドリル0.3mm・F.Cu～B.Cuの確認済みポリシーと照合します。ビアの電磁界寄生は未モデル化です。</li>
<li>D2=赤、D1=緑、D0=青へ訂正し、符号語全反転、制御期間、物理P/N入替を含むRTL試験要求を登録。送信RTL・実機表示は未検証です。</li></ul>
<p>正常入力と故障注入の回帰試験：<strong>COUNTケース成功</strong>。正常ケースは終了0、不正ケースは検査結果JSONで理由を示し終了1。回転・裏面の試験はランド形状の試験であり、その配置で銅配線が接続することを意味しません。</p>
<div class="table"><table><thead><tr><th>対象</th><th>ケース</th><th>期待・確認結果</th><th>終了コード</th></tr></thead><tbody>ROWS</tbody></table></div>
<h2>残る制限</h2><p>メーカー推奨ランドが無いため、製造先との実装条件確認は残ります。D1N11.5mm枝と、複合条件で自主目標を外れることは第3版と同じです。3D較正とMeOSのPARLIO・電源断・ピン所有権は未完了です。</p>
<p><a href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/docs/HDMI_R3_検査修正_2026-10-24.md">変更・検証・再現手順</a> / <a href="https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/main/kicad/sim/manifest_r3.json">成果物ハッシュ</a></p>
</html>'''.replace('COUNT',str(count)).replace('ROWS',''.join(rows))
(ROOT/'site/hdmi-audit-checks.html').write_text(text,encoding='utf-8')
print('Published checker addendum:',count,'regressions')
