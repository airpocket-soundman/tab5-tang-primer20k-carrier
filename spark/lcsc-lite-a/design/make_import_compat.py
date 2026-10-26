"""Build an isolated importer compatibility copy with explicit numbered nets.

KiCad10 uses named-only net references; EasyEDA3.2.149's importer silently
loses them and the tracks. Never modify or rename the authoritative source.
"""
from pathlib import Path
import sys,json,hashlib,shutil,zipfile
H=Path(__file__).resolve().parent;K=H/'kicad';C=H/'import-compat'
sys.path.insert(0,str(K/'gen'));import sexp
C.mkdir(exist_ok=True)
source=K/'tab5-fpga-carrier.kicad_pcb';tree=sexp.parse(source.read_text(encoding='utf8'))
names=set()
def collect(n):
 if not isinstance(n,list) or not n:return
 if n[0]=='net' and len(n)==2:names.add(str(n[1]))
 for c in n:collect(c)
collect(tree);ids={n:i+1 for i,n in enumerate(sorted(names))};ids['']=0
def rewrite(n,parent=None):
 if not isinstance(n,list) or not n:return n
 if n[0]=='net' and len(n)==2:
  name=str(n[1]);return ['net',str(ids[name]),sexp.Str(name)] if parent=='pad' else ['net',str(ids[name])]
 out=[rewrite(c,n[0]) for c in n]
 if n[0]=='zone':
  net=sexp.first(n,'net')
  if net is not None and len(net)==2:out.append(['net_name',sexp.Str(str(net[1]))])
 if n[0]=='version':return ['version','20241229']
 return out
converted=rewrite(tree)
index=next(i for i,c in enumerate(converted) if isinstance(c,list) and c and c[0]=='footprint')
for name,i in reversed(sorted(ids.items(),key=lambda item:item[1])):converted.insert(index,['net',str(i),sexp.Str(name)])
(C/source.name).write_text(sexp.dump(converted)+'\n',encoding='utf8')
for name in ('tab5-fpga-carrier.kicad_pro','tab5-fpga-carrier.kicad_sch','fp-lib-table','sym-lib-table'):shutil.copyfile(K/name,C/name)
shutil.copytree(K/'lib',C/'lib',dirs_exist_ok=True)
with zipfile.ZipFile(H/'spark-kicad-compat-import.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in C.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(C))
(H/'import-compat-report.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'compat_sha256':hashlib.sha256((C/source.name).read_bytes()).hexdigest(),'named_nets':len(names),'geometry_change':False,'purpose':'Importer compatibility only, not original creation in EasyEDA; eligibility unresolved'},indent=2)+'\n')
print('Numbered-net compatibility copy:',len(names),'nets')
