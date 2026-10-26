"""Importer-only copy: express all power nets with explicit ordinary labels.

Avoids importer power-symbol inference; authoritative KiCad ERC source is unchanged.
"""
from pathlib import Path
import sys,uuid,json
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'kicad/gen'))
import sexp
S=sexp.Str
t=sexp.parse((H/'kicad/tab5-fpga-carrier.kicad_sch').read_text(encoding='utf8'));out=[];count=0
for n in t:
 if not isinstance(n,list) or not n or n[0]!='symbol':out.append(n);continue
 props={p[1]:p[2] for p in sexp.find(n,'property')}
 if not props.get('Reference','').startswith('#'):out.append(n);continue
 if props['Reference'].startswith('#PWR'):
  pos=sexp.first(n,'at');net=props['Value']
  out.append(['label',S(net),['at',pos[1],pos[2],'0'],['effects',['font',['size','1.27','1.27']],['justify','left','bottom']],['uuid',S(str(uuid.uuid4()))]])
 count+=1
uuid_map={}
def gather(n):
 if not isinstance(n,list):return
 if n and n[0]=='uuid':uuid_map[str(n[1])]=str(uuid.uuid4())
 for c in n:gather(c)
gather(out)
def reidentify(n):
 if not isinstance(n,list):return
 if n and n[0]=='uuid':n[1]=S(uuid_map[str(n[1])])
 if n and n[0]=='path' and len(n)>1 and str(n[1]).startswith('/'):
  for old,new in uuid_map.items():
   if str(n[1])=='/'+old:n[1]=S('/'+new);break
 for c in n:reidentify(c)
reidentify(out)
(H/'import-compat/spark-label-power.kicad_sch').write_text(sexp.dump(out)+'\n',encoding='utf8')
print('Replaced power symbols / removed electrical flags:',count)
