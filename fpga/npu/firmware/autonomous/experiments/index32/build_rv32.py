"""Build experimental RV32 image; never edits canonical firmware or pinned vendor."""
from pathlib import Path
import argparse,subprocess,sys,json,hashlib
from prepare import prepare,HERE,FW
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'build/rv32');a=p.parse_args();out=a.output.resolve();assert out.is_relative_to(HERE.resolve());out.mkdir(parents=True,exist_ok=True);graph=prepare();canonical=FW/'build.py';text=canonical.read_text(encoding='utf-8');text='import sys\nsys.path.insert(0,'+repr(str(FW))+')\n'+text;root_line='ROOT=Path(__file__).resolve().parent';assert text.count(root_line)==1 and text.count("v/'rtdetr_graph.cpp'")==1
 text=text.replace(root_line,'ROOT=Path('+repr(str(FW))+')').replace("v/'rtdetr_graph.cpp'",'Path('+repr(str(graph))+')')
 text=text.replace("'-nostartfiles'","'-I'+str(Path("+repr(str(HERE))+")),'-nostartfiles'",1)
 text=text.replace('files=[*src,','files=[Path('+repr(str(HERE/'index32_contract.hpp'))+'),Path('+repr(str(HERE/'prepare.py'))+'),*src,',1)
 effective=out/'build-effective.py';effective.write_text(text,encoding='utf-8');r=subprocess.run([sys.executable,str(effective),'--output',str(out)],capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8');print(r.stdout+r.stderr,flush=True)
 (out/'build-provenance.json').write_text(json.dumps({'canonical_builder_sha256':hashlib.sha256(canonical.read_bytes()).hexdigest(),'effective_builder_sha256':hashlib.sha256(effective.read_bytes()).hexdigest(),'scope':'Same canonical flags/startup/firmware/backend/transport; only graph source and guard include path replaced','canonical_files_modified':False,'returncode':r.returncode},indent=2)+'\n',encoding='utf-8');raise SystemExit(r.returncode)
if __name__=='__main__':main()
