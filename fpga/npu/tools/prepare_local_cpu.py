"""Use PicoRV32's official register-file hook without modifying pinned vendor bytes."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[3]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=ROOT/'fpga/npu/vendor/picorv32/picorv32.v';manifest=json.loads((source.parent/'UPSTREAM.json').read_text());raw=source.read_bytes();actual=hashlib.sha256(raw).hexdigest();assert actual==manifest['files_sha256']['picorv32.v'],'Pinned official PicoRV32 changed'
 out=b'`define PICORV32_REGS npu_local_rv32_regs\n'+raw+b'\n`undef PICORV32_REGS\n';a.output.parent.mkdir(parents=True,exist_ok=True)
 if a.output.exists()and a.output.read_bytes()!=out:raise ValueError('Fresh output required; existing generated source differs')
 a.output.write_bytes(out);a.output.with_suffix('.provenance.json').write_text(json.dumps({'repository':manifest['repository'],'commit':manifest['commit'],'license':'ISC','original_sha256':actual,'generated_sha256':hashlib.sha256(out).hexdigest(),'change':'Only official PICORV32_REGS hook macro, external distributed-RAM register file; upstream text unmodified','external_module':'npu_local_rv32_regs'},indent=2)+'\n',encoding='utf-8');print(a.output)
if __name__=='__main__':main()
