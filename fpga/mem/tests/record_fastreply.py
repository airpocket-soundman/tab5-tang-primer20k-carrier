"""Record a locally built fast MEMV1 candidate; never copies vendor RTL/bitstreams."""
import argparse,gzip,hashlib,html,json,re
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
root=Path(__file__).resolve().parents[2];build=root/'build/memv1-fast';pnr=build/'out/mem_bist/impl/pnr'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cells(row):return [html.unescape(re.sub('<[^>]*>','',x)).strip() for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',row,re.S)]
s=(pnr/'mem_bist_tr_content.html').read_text(encoding='utf-8')
rows=[cells(x) for x in re.findall(r'<tr>(.*?)</tr>',s,re.S)]
summary={r[0]:r[1] for r in rows if len(r)==2}
assert summary['Numbers of Setup Violated Endpoints']=='0',summary
assert summary['Numbers of Hold Violated Endpoints']=='0',summary
reports={}
for m in re.finditer(r'<h4>Report Command:(.*?)</h4>',s,re.S):
 end=s.find('<h',m.end());body=s[m.end():end if end>=0 else len(s)]
 table=[cells(x) for x in re.findall(r'<tr>(.*?)</tr>',body,re.S)]
 paths=[r for r in table if len(r)>=3 and r[0].isdigit()]
 if paths and ('report_timing' in m[1]):
  command=html.unescape(m[1]);reports.setdefault(command,{'reported_paths':len(paths),'min_slack_ns':min(float(r[1]) for r in paths),'distinct_reported_starts':len({r[2] for r in paths}),'first_path':paths[0]})
for family in ('fast_header','fast_kind','fast_beats','fast_crc32','fast_prefix'):
 found=[v for k,v in reports.items() if '{core/link/'+family+'*}' in k]
 assert found and found[0]['reported_paths']>0,(family,'missing timing coverage')
 assert found[0]['min_slack_ns']>=0,(family,found)
validations={}
for name in ('memv1-fastreply-offline-2026-11-05.json','memv1-fastreply-regression-2026-11-05.json'):
 file=root/'validation'/name;data=json.loads(file.read_text(encoding='utf-8'))
 for source,expected in data['sources'].items():assert sha(root/source)==expected,('stale RTL result',name,source)
 validations[name]={'sha256':sha(file),'results':data['results']}
fs=pnr/'mem_bist.fs';fs_text=fs.read_text(encoding='utf-8')
prepared=json.loads((build/'prepared.json').read_text(encoding='utf-8'))
for name,expected in prepared['files'].items():assert sha(build/'rtl'/f'{name}.v')==expected,('modified build input',name)
sources={str(p.relative_to(root)):sha(p) for p in (root/'mem/rtl').glob('mem*v*.v')}
for name in ('memv1_sys','mem_v1_core'):
 assert sha(root/f'mem/rtl/{name}.v')==sha(build/f'rtl/{name}.v'),('stale PNR source',name)
sdc=(build/'mem_v1.sdc').read_text(encoding='utf-8')
cdc_pins=re.findall(r'set_false_path -to \[get_pins \{(core/link/[^}]+_0_s0/D)\}\]',sdc)
assert len(cdc_pins)==6 and len(set(cdc_pins))==6,cdc_pins
console=(build/'build-console.log').read_text(encoding='utf-8')
assert not re.search(r'ERROR|matched.no.objects|TA200[34]',console,re.I),'Tool errors or missing constraint objects'
output=Path(args.output);artifacts=output.with_suffix('');artifacts.mkdir(parents=True,exist_ok=True)
for name in ('mem_bist.rpt.txt','mem_bist_tr_content.html'):
 (artifacts/(name+'.gz')).write_bytes(gzip.compress((pnr/name).read_bytes(),mtime=0))
resource_text=(pnr/'mem_bist.rpt.txt').read_text(encoding='utf-8')
resources={name:{'used':int(a),'available':int(b)} for name,a,b in re.findall(r'^  (Logic|Register|BSRAM|rPLL|LW)\s*\|\s*(\d+)/(\d+)',resource_text,re.M)}
record={'scope':'offline RTL and diagnostic image PNR; no physical qualification; vendor RTL and FS excluded','usercode':re.search(r'//UserCode: (0x[0-9A-Fa-f]+)',fs_text)[1],'fs_sha256':sha(fs),'local_fs_path':str(fs.resolve()),'timing_summary':summary,'resources':resources,'timing_reports':reports,'rtl_sources':sources,'cdc_firststage_exception_pins':cdc_pins,'cdc_pin_match_evidence':'Six exact non-wildcard firststage D pins; Gowin accepted all six with no missing-object/TA errors. Stage1 remains normally timed.','validations':validations,'sdc_sha256':sha(build/'mem_v1.sdc'),'sdc_lf_sha256':hashlib.sha256((build/'mem_v1.sdc').read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest(),'sdc_template_sha256':sha(root/'mem/tests/prepare_memv1.py'),'prepared':prepared,'limitations':['Host sample in passing RTL tests is raw rising edge; not physical P4 NEG/POS qualification','Legacy DDR SYS/memory/user exclusions retained as explicit clock pairs','No complete external IO flight-time/input-output timing sign-off','TX5MHz request sampling and +25ns host-sample offset fail; see limitations JSON']}
output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('recorded',output,'USERCODE',record['usercode'],'SHA256',record['fs_sha256'])
