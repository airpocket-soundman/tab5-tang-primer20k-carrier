"""Full64commandcore regression using build-only aligned RX candidate, no devices."""
import argparse,sys,shutil,hashlib,json
from pathlib import Path
import run_npu_ddr_core_8oc as base
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path);p.add_argument('--production-param',type=int,choices=[0,1]);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();snap=out/'source_snapshot';snap.mkdir(parents=True,exist_ok=True);files=['npu/rtl/npu_ddr_core_8oc.v','npu/rtl/npu_ddr_sys.v','npu/rtl/npu_ddr_arbiter.v','npu/rtl/npu_ddr_tile_loader_8oc.v','npu/rtl/conv_tile_engine_8oc.v','mem/rtl/memv1_bridge.v','mem/rtl/mem_adapter.v','mem/rtl/memv1_crc32b.v'];before={}
 for name in files:
  s=ROOT/name;before[name]=hashlib.sha256(s.read_bytes()).hexdigest();d=snap/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,d)
 if a.production_param is None:
  assert a.candidate,'Needcandidateorproduction-param';candidate=a.candidate.read_text().replace('module npu_ddr_sys_aligned #','module npu_ddr_sys #',1);(snap/'npu/rtl/npu_ddr_sys.v').write_text(candidate,newline='\n')
 else:base.NATIVE=base.NATIVE.replace('.RECAL_HOLD(8))','.RECAL_HOLD(8),.REQUEST_DATA_PIPELINE('+str(a.production_param)+'))')
 base.ROOT=snap;sys.argv=['run_npu_ddr_core_8oc.py','--iverilog',a.iverilog,'--vvp',a.vvp,'--output',str(out/'proof')];base.main();assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in before.items());(out/'production-unchanged.json').write_text(json.dumps(before,indent=2)+'\n')
if __name__=='__main__':main()
