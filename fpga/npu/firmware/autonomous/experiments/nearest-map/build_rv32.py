from pathlib import Path
import subprocess,sys,json,hashlib
from prepare import prepare,HERE,FW,INDEX
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
graph=prepare();out=HERE/'build/rv32';out.mkdir(parents=True,exist_ok=True)
old=INDEX/'build/rv32/build-effective.py';text=old.read_text(encoding='utf-8');pattern='Path('+repr(str(INDEX/'generated/rtdetr_graph.cpp'))+')';assert text.count(pattern)==1;text=text.replace(pattern,'Path('+repr(str(graph))+')')
text=text.replace('files=[','files=[Path('+repr(str(HERE/'prepare.py'))+'),',1)
before={str(p):sha(p)for p in [FW/'firmware.cpp',INDEX/'generated/rtdetr_graph.cpp',INDEX/'build/rv32/autonomous.elf',INDEX/'build/rv32/autonomous.bin']}
e=out/'build-effective.py';e.write_text(text,encoding='utf-8');r=subprocess.run([sys.executable,str(e),'--output',str(out)],capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8');print(r.stdout+r.stderr)
assert all(sha(Path(p))==h for p,h in before.items());(out/'provenance.json').write_text(json.dumps({'baseline_immutable':before,'generated_graph_sha256':sha(graph),'only_change':'generic nearest axis map plus odometer; original index32 firmware, noCRCtablecombo','returncode':r.returncode},indent=2)+'\n',encoding='utf-8');raise SystemExit(r.returncode)
