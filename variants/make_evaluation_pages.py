"""Build three evaluation pages from final evidence; refresh BoM separately last."""
from pathlib import Path
import hashlib
import html
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'variants/simulation'
BASE='https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier/blob/codex/lite-variants/'
STYLE='''body{font:16px/1.75 system-ui,"Meiryo",sans-serif;color:#203040;background:#f4f7fa;margin:0}main{max-width:1150px;margin:auto;padding:25px}section{background:white;padding:22px;margin:20px 0;border:1px solid #d6dfe7;border-radius:10px}a{color:#155bbc}table{border-collapse:collapse;font-size:14px;width:100%}td,th{border:1px solid #ccd3da;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#edf2f7}img{max-width:100%;height:auto}small,code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.warn{border-left:5px solid #bb820c}.pass{color:#18713c}.fail{color:#b33730}.uncertain{color:#88610c}h1{line-height:1.4}#bom .bom-table th:nth-child(5),#bom .bom-table td:nth-child(5){white-space:nowrap;min-width:95px}'''

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def esc(x):return html.escape(str(x))
def evidence(p,label):return f'<a href="{BASE}{p.relative_to(ROOT).as_posix()}">{esc(label)}</a>'
def picture(p,caption):
    if not p.exists():return ''
    out=ROOT/'site/img/evaluation'/p.relative_to(SIM)
    out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
    return f'<figure><img loading="lazy" src="{out.relative_to(ROOT/"site").as_posix()}" alt="{esc(caption)}"><figcaption>{esc(caption)}</figcaption></figure>'
def tests(record):
    result='<div style="overflow-x:auto"><table><tr><th>検査</th><th>判定</th><th>条件・数値</th></tr>'
    for t in record.get('tests',[]):
        status=t.get('status','uncertain')
        details={k:v for k,v in t.items() if k not in ('name','status')}
        result+=f'<tr><td>{esc(t.get("name",""))}</td><td class="{esc(status)}">{esc(status)}</td><td>{esc(json.dumps(details,ensure_ascii=False))}</td></tr>'
    return result+'</table></div>'

def main():
    parallel=read(SIM/'parallel/final-summary.json')
    power=read(SIM/'power/final-summary.json')
    mechanical=read(SIM/'mechanical/clearance.json')
    assert not mechanical['proposal_only_not_actual_CAD']
    for label,name in [('a','lite-a-dual'),('b','lite-b-barrel'),('c','lite-c-dnp')]:
        folder=ROOT/'variants'/name
        pcb=folder/'kicad/tab5-fpga-carrier.kicad_pcb'
        digest=hashlib.sha256(pcb.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        audit=read(ROOT/'variants/validation'/f'{name}-independent-audit.json')
        assert audit['ok'] and audit['pcb_sha256']==digest
        p=parallel['variants'][name];w=power['variants'][name];m=mechanical['variants'][name]
        assert m['pass_clearance'],name+' mechanical clearance unresolved'
        heading={'a':'HDMI実装・USB PD＋バレル、99×78mm','b':'HDMI実装・バレルのみ、99×78mm','c':'HDMI／PDは回路を残して未実装、125×78mm'}[label]
        text=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>案{label.upper()} 評価結果・BoM</title><style>{STYLE}</style></head><body><main>
<p><a href="lite-variants.html">← 廉価版3案</a> ／ <a href="pcb-report.html">基板レポート</a></p><h1>案{label.upper()}：評価結果・BoM</h1><p>{heading}。2026年10月25日更新。</p><p><a href="#bom">BoM・PCBA実装区分へ移動</a></p>
<section class="warn"><h2>目的に対する判定</h2><p>初期1MHz・弱い駆動／SLOW設定・規定12V電源を使うPoCの製作候補です。基板製作に進むための条件付き評価であり、Tab5との実通信、DDR3、GPUの実機動作が完了したという判定ではありません。</p>
<p>最低成功条件は8bitパラレル通信とCore上DDR3の利用、そのための安定した電源です。HDMIは最低成功条件から外します。40MHz転送や最終アクセラレータ性能は今回確認していません。</p>
<p>独立した実回路図・PCB・製造データ照合：{len(audit['checks'])}項目合格。DRC違反0・未接続0。元の高価格版は保持しています。</p></section>
<section><h2>今回の修正と再評価</h2><p>パラレル15本の直列抵抗を33Ωから{p.get('series_ohm_model','選定値')}Ωへ変更し、反射と整定時間を再評価しました。A/BのHDMI下部品は低背化し、HPDはNPN反転バッファと100nFフィルタ・Core手前10kΩ、独立対GNDの保護へ変更しました。CではHDMI専用部品はDNPを維持します。</p>
<p>J4はPCBA、J6/J7/J8はPCBA対象外です。Core本体はユーザー支給。最終の部品・実装区分は下のBoMで確認できます。</p></section>
<section><h2>パラレル通信・電源断保護</h2><p>実PCBから15信号を抽出し、伝送線路・バススイッチ・仮定したTab5/Core内部配線を含めて過渡解析しました。実在の接続試験RTLも27MHzシステムクロックで位相を振って評価しています。</p>
<p>初期運用は1MHz、DATAのsetup/hold各250ns以上、方向切替の待ち500ns以上、FPGAはLVCMOS33・最弱4mA・SLOW、Tab5も弱い駆動を使います。未校正の強い高速駆動では電圧逸脱を生じるため、全GPIO設定に対する合格とはしていません。</p>{tests(p)}
{picture(SIM/'parallel'/f'{name}-transient.png','送受信波形。強い駆動の感度結果とPoC設定を区別。')}
{picture(SIM/'parallel'/'rtl-phase-matrix.png','実RTLの通信速度・位相感度。初期運用は1MHz。')}
<p>{evidence(SIM/'parallel/final-summary.json','数値・条件・未確定事項')} ／ {evidence(SIM/'parallel/source-parameters.json','部品公式情報と仮定')}</p></section>
<section><h2>電源系</h2><p>TPS5430のメーカー公開モデルを実行し、単純基準回路で11ms完走しました。実案全回路のメーカー全モデルは0.518msで数値停止したため成功扱いせず、実案の条件一覧は平均化モデルで評価しています。基準回路の比較はRMS差0.974mV・最大差6.059mVで、個体差を含む全面的な校正ではありません。LDOはメーカーの典型波形に合わせた近似で、個体差を保証するモデルではありません。通常10mA以下の条件と、追加の50mA急変で失敗する条件を分けています。C11の有効容量6.6µF・遅い制御の感度では約3.151Vが下限で、±5%目標に対する余裕は約16mVです。C7の低ESR条件も250ms評価しましたが、解析した位相余裕6.58°は小さく、実機の波形確認が必要です。</p>{tests(w)}
{picture(SIM/'power/results'/f'{name}-power.png','規定入力・負荷変動時のCore5Vと局所3.3V。')}
{picture(SIM/'power/results'/f'{name}-power-sequence.png','起動・電源断・低電圧時の波形。通常動作の合格と異常時の限界を区別。')}
{picture(SIM/'power/results'/'calibration-buck.png','メーカーのスイッチングモデルと平均化モデルの同条件照合。')}
<p>規定12V±5%、室内PoC・周囲0〜50℃のモデル条件、Core通常0.5A、局所3.3Vの通常負荷10mA以下、外部3.3V負荷なしが条件です。K50のPGはCore入力4.5V以上を保証しません。電源が安定して500ms待ってからARMし、初品では温度も測定します。意図した電源断前にクロックを停止してARMを解除し、電圧低下後はFPGA／DDR3を再初期化します。逆接の長時間保持・急激な電源喪失に対する絶対定格保証はありません。</p>
<p>{evidence(SIM/'power/final-summary.json','電源解析の全条件・結果')}</p></section>
<section><h2>Core下面・高い部品との干渉</h2><p>灰色の壊れたような3D表示を実体として扱わず、公式Core STEPの部品形状と実PCBの部品外形を照合しました。差し込み位置−0.5〜4.5mm、Core下面高さ2.3mm以上、XYずれ±0.25mm、はんだ高さ0.05mmを仮定した保守的な外接箱の比較で、必要隙間0.3mmを確認しました。ソケットの実装高さ・公差をメーカーが保証した範囲ではなく、実装プレビュー／初品で確認する条件が残ります。</p>
{picture(SIM/'mechanical'/f'{name}-clearance.png','公式Core下面とキャリア部品の範囲、仮定範囲内の最小隙間。')}
<p>{evidence(SIM/'mechanical/clearance.json','干渉検査の全明細')} ／ {evidence(SIM/'mechanical/core_components.json','公式Core STEPからの抽出')}</p></section>'''
        if label!='c':
            eye=read(SIM/'hdmi/results'/name/'eye_results.json')
            data=eye.get('results',[])
            if not data:
                data=next((v for k,v in eye.items() if isinstance(v,list) and v and isinstance(v[0],dict) and 'signed_center_min_V' in v[0]),[])
            summary=[]
            for mode in ('480p','720p'):
                rows=[r for r in data if r.get('mode')==mode]
                assert rows,mode
                summary.append(f'<li>{mode}：中心差動レベル最小{min(r["signed_center_min_V"] for r in rows)*1000:.1f}mV、100mV以上の開口幅最小{min(r["width_over_100mV_UI"] for r in rows):.3f}UI。</li>')
            text+='''<section><h2>HDMI・2D／3D解析</h2><p>公式CoreのP/N別配線長、実キャリア配線、AC結合、510Ω、受信終端と仮定したソケット寄生を含めて時間波形を確認しました。自主目標は中心±100mV以上・幅0.5UI以上・クロック相対ずれ0.2UI以下です。</p><ul>'''+''.join(summary)+'''</ul><p>最初は640×480、短いケーブルと限定モニタで試します。720pは追加感度確認、1080p60は対象外。HPDはactive-lowへ変更しているためソフト側で反転し、10ms以上の安定判定が必要です。Coreとキャリアの3.3Vが別々に低下する感度では、フィルタ直結の注入を見つけたため10kΩを追加しました。注入電流を制限しますが、未公開のGPIO許容注入値への適合保証はしていません。</p><p>3Dを誤差だけを理由に破棄せず、直線基準のメッシュ感度を確認しました。基準3Dは約95.89Ω、細分化前後の差は約0.67%ですが、2D約103.42Ωとの差は約7.3%残ります。キャリアのインピーダンス±10%の感度をアイ解析に含め、一律に校正済みとはしていません。分岐3Dはエネルギー収束が不十分なため校正補正には使っていません。完全なCore・ケーブル・受信機・GPIO IBIS、ジッタ、規格試験を再現したものではありません。</p>'''
            text+=picture(SIM/'hdmi/results'/name/'480p-weak_slow_low_Rs-eye.png','480pの弱い送信条件を含むアイ波形。')
            text+=f'<p>{evidence(SIM/"hdmi/results"/name/"eye_results.json","HDMI解析結果")} ／ {evidence(SIM/"hdmi/hpd/summary.json","HPD DC／電源断過渡")} ／ {evidence(SIM/"hdmi/hpd/offrail_sensitivity.json","Core電源だけが低下する感度")}</p></section>'
        else:
            text+='<section><h2>HDMI・PD未実装の扱い</h2><p>専用回路・パターンを残し、PCBAから除外します。今回のPoCはバレル12Vとパラレル通信で進めます。HDMIやPDの後付けには専用部品一式と再確認が必要で、端子だけの追加で動作する扱いにはしません。</p></section>'
        if label=='a':
            text=text.replace('J4はPCBA、J6/J7/J8はPCBA対象外です。','J4とJ5 HDMIはPCBA、J6/J7/J8はPCBA対象外です。')
            text+=f'<section><h2>秋月ボタン・HDMI実装の更新</h2><p>SW1/SW2は秋月115969 TS-06104用にランド・配置・局所配線を変更しました。手実装は計2個。旧Panasonic品を購入しないでください。DRC違反0・未配線0、ERCエラー0（既存の警告165件は残存）、Core干渉の再確認は合格。電源・通信の配線と他部品のパッドの同一性を比較し、従来解析を継承しました。変更後の全基板の再シミュレーションや実測を意味しません。</p><p>J5 HDMIは19信号端子と4本の固定タブを含めPCBA必須。追加実装費は再見積が必要です。SW3はDigiKey調達、J1の秋月候補は無加工互換未確定です。</p><p>{evidence(SIM/"button-revision-review.json","ボタン変更の独立照合・解析継承根拠")} ／ {evidence(ROOT/"variants/lite-a-dual/reference/TS-06104.pdf","メーカー寸法図（8ページ）")}</p></section>'
        text+=f'''<section class="warn"><h2>Core DDR3と関連プロジェクトへの引き継ぎ</h2><p>Core上のDDR3と電源回路は公式のまま使います。キャリアの5V・IOとNC端子に加わる負荷は評価していますが、Core全体のDDR3信号品質とメモリコントローラの完全なシミュレーションではありません。</p><p>Linux側の物理通信ドライバ、GPU側のDDR3／最終ボードトップは未実装です。基板製作後、電源確認→1MHz CRC往復→公式DDR3試験→メモリREAD／WRITE→GPU・アクセラレータの順で実証します。Linuxの透過的なメインRAM増設を達成したものではありません。</p><p>{evidence(SIM/'requirements-review.json','関連リポジトリの参照版と要求照合')} ／ {evidence(SIM/'hdmi/ddr_nc_loading.json','DDR関連NC端子の局所負荷感度')}</p></section>
<!-- BOM START --><!-- BOM END -->
<section><h2>評価した版</h2><p><small>PCB SHA-256（改行LF正規化）：{digest}</small></p><p>{evidence(ROOT/'variants/validation'/f'{name}-independent-audit.json','独立照合結果')}</p></section></main></body></html>'''
        (ROOT/'site'/f'lite-{label}-evaluation.html').write_text(text,encoding='utf-8')
    sys.path.insert(0,str(ROOT/'variants'))
    import make_evaluation_bom
    make_evaluation_bom.main()

if __name__=='__main__':main()
