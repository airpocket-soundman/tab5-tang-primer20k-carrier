"""Isolated payload CRC experiment atop frozen index32; no canonical mutation."""
from pathlib import Path
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent
FW=HERE.parents[1]
INDEX=HERE.parent/'index32'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=HERE/'build/rv32';out.mkdir(parents=True,exist_ok=True)
 baseline=FW/'firmware.cpp';s=baseline.read_text(encoding='utf-8');start=s.index('bool crc32(');end=s.index('\nbool valid(',start)
 original=s[start:end]
 assert '0xedb88320u' in original and '(i&4095u)' in original
 s='#include "crc_table.hpp"\n'+s[:start]+'bool crc32(const void*data,std::size_t n,std::uint32_t&out){return crc_table::checked(data,n,out,[](){return cancelled();});}'+s[end:]
 generated=HERE/'build/firmware.cpp';generated.write_text(s,encoding='utf-8')
 # Reuse exact frozen index32 effective builder; do not rerun index32 prepare.
 old=INDEX/'build/rv32/build-effective.py';text=old.read_text(encoding='utf-8')
 assert text.count("ROOT/'firmware.cpp'")==1
 text=text.replace("ROOT/'firmware.cpp'",'Path('+repr(str(generated))+')')
 text=text.replace("'-nostartfiles'","'-I'+str(Path("+repr(str(HERE))+")),'-nostartfiles'",1)
 text=text.replace('files=[','files=[Path('+repr(str(HERE/'crc_table.hpp'))+'),',1)
 effective=out/'build-effective.py';effective.write_text(text,encoding='utf-8')
 before={str(p):sha(p) for p in [baseline,INDEX/'generated/rtdetr_graph.cpp',INDEX/'build/rv32/autonomous.elf',INDEX/'build/rv32/autonomous.bin']}
 p=subprocess.run([sys.executable,str(effective),'--output',str(out)],capture_output=True,text=True);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout+p.stderr)
 assert all(sha(Path(f))==h for f,h in before.items())
 (out/'provenance.json').write_text(json.dumps({'baseline_immutable':before,'only_change':'firmware payloadCRC function replaced with256entry table, same polynomial/cancellation interval/return semantics','generated_firmware_sha256':sha(generated),'header_sha256':sha(HERE/'crc_table.hpp'),'returncode':p.returncode},indent=2)+'\n',encoding='utf-8')
 raise SystemExit(p.returncode)
if __name__=='__main__':main()
