"""4E23 actual-source core regression plus >2 LINK_TIMEOUT healthy session gap."""
import argparse,sys,shutil,hashlib,json
from pathlib import Path
import run_npu_ddr_core_8oc as base
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/npu-ddr-idle-guard-core');p.add_argument('--iverilog',default='D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/iverilog.exe');p.add_argument('--vvp',default='D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/vvp.exe');a=p.parse_args();out=a.output.resolve();snap=out/'source_snapshot';snap.mkdir(parents=True,exist_ok=True)
 files=['npu/rtl/npu_ddr_core_8oc_idle_guard.v','npu/rtl/npu_ddr_sys_idle_guard.v','npu/rtl/npu_ddr_arbiter.v','npu/rtl/npu_ddr_tile_loader_8oc.v','npu/rtl/conv_tile_engine_8oc.v','mem/rtl/memv1_bridge.v','mem/rtl/mem_adapter.v','mem/rtl/memv1_crc32b.v'];before={}
 for name in files:
  source=ROOT/name;before[name]=hashlib.sha256(source.read_bytes()).hexdigest();dest=snap/name.replace('_idle_guard','');dest.parent.mkdir(parents=True,exist_ok=True)
  text=source.read_text().replace('npu_ddr_core_8oc_idle_guard','npu_ddr_core_8oc').replace('npu_ddr_sys_idle_guard','npu_ddr_sys');dest.write_text(text,newline='\n')
 base.NATIVE=base.NATIVE.replace('.RECAL_HOLD(8))','.RECAL_HOLD(8),.REQUEST_DATA_PIPELINE(1),.LINK_TIMEOUT(700000))')
 marker=' $display("PASS NPU DDR core'
 extra=''' repeat(1400100) @(posedge clk);
 if(dut.conv_error||dut.conv_quarantined||dut.arbiter_fault)$fatal(1,"healthy idle poisoned loader/session");
 command(8'h76,0,0,0);if(got_value!==16'hccdd)$fatal(1,"idle session token low lost");
 command(8'h77,0,0,0);if(got_value!==16'haabb)$fatal(1,"idle session token high lost");
 small_write(32'h22000,19);small_read(32'h22000,19,0);
'''
 assert marker in base.MAIN;base.MAIN=base.MAIN.replace(marker,extra+marker)
 base.ROOT=snap;sys.argv=['run_npu_ddr_core_8oc.py','--iverilog',a.iverilog,'--vvp',a.vvp,'--output',str(out/'proof')];base.main()
 assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==v for n,v in before.items())
 (out/'actual-source-hashes.json').write_text(json.dumps(before,indent=2)+'\n')
if __name__=='__main__':main()
