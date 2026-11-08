"""Actual local RV32/cache + tagged DDR/8OC MAC, pin-level control, fake DDR PHY."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess
import run_npu_ddr_core_8oc as base
ROOT=Path(__file__).resolve().parents[3]
TOOLS=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin')
MAIN=r'''
 always @(posedge clk)if(dut.local_cpu.mmio_ready)begin
  if(dut.local_cpu.native_wstrb==0)$display("CSR read addr%h value%h gen%h",dut.local_cpu.native_addr,dut.local_cpu.native_rdata,dut.generation);
  else if(dut.local_cpu.native_addr[7:0]==12)$display("CSR ABORT PC%h",dut.local_cpu.cpu.reg_pc);
 end
 reg[7:0]program_bytes[0:@LAST@];integer off,take,t,n,timeout;reg[15:0]auto_status;
 task ctrl;input integer action,token,status;begin
  payload[0]=action;payload[1]=0;payload[2]=0;payload[3]=0;
  payload[4]=token;payload[5]=token>>8;payload[6]=token>>16;payload[7]=token>>24;
  command(8'h7e,8,0,status);
 end endtask
 task rd;input integer addr,len;begin
  payload[0]=addr;payload[1]=addr>>8;payload[2]=addr>>16;payload[3]=addr>>24;
  payload[4]=len;payload[5]=len>>8;payload[6]=0;payload[7]=0;command(8'h70,8,len,0);
 end endtask
 function signed[31:0]word;input integer o;begin word={r[8+o+3],r[8+o+2],r[8+o+1],r[8+o]};end endfunction
 task wait_end;begin
  timeout=0;auto_status=2;
  while(auto_status[1]&&timeout<1000)begin ctrl(0,0,0);auto_status=got_value;timeout=timeout+1;end
  if(auto_status[1])$fatal(1,"autonomous timeout state%h CPU%h cache%d",st,dut.local_cpu.cpu.reg_pc,dut.local_cpu.memory.state);
 end endtask
 initial begin
  for(i=0;i<524288;i=i+1)mem[i]=0;
  $readmemh("program.hex",program_bytes);
  #200;reset_n=1;arm=1;pll_lock=1;ip_user_reset=0;
  timeout=0;while(!dut.memory_ready&&timeout<100000)begin @(posedge clk);timeout=timeout+1;end
  if(!dut.memory_ready)$fatal(1,"memory calibration");
  command(8'h50,0,0,0);if(got_value!==16'h4e30)$fatal(1,"wrong capability");
  ctrl(1,32'h735129ab,9);
  payload[0]=8'hab;payload[1]=8'h29;payload[2]=8'h51;payload[3]=8'h73;command(8'h75,4,0,0);
  for(off=0;off<@SIZE@;off=off+take)begin
   take=@SIZE@-off;if(take>2032)take=2032;n=(take+15)&~15;
   payload[0]=off;payload[1]=off>>8;payload[2]=0;payload[3]=5;
   payload[4]=n;payload[5]=n>>8;payload[6]=0;payload[7]=0;
   for(t=0;t<n;t=t+1)payload[8+t]=t<take?program_bytes[off+t]:0;
   command(8'h71,8+n,0,0);
  end
  ctrl(3,32'h735129ab,0);ctrl(1,32'h735129aa,9);ctrl(1,32'h735129ab,0);
  if(!dut.local_running)$fatal(1,"START did not hold RUN lease");
  payload[0]=0;payload[1]=16;payload[2]=0;payload[3]=0;payload[4]=16;payload[5]=0;payload[6]=0;payload[7]=0;
  command(8'h70,8,0,4);
  for(t=0;t<16;t=t+1)payload[8+t]=8'h5a;command(8'h71,24,0,4);
  command(8'h78,0,0,4);command(8'h67,0,0,4);
  // Unknown monitor and malformed CONTROL reject without touching DDR.
  payload[0]=128;payload[1]=0;payload[2]=0;payload[3]=0;command(8'h7f,4,0,3);
  wait_end();if(!auto_status[2]||auto_status[6:3])$fatal(1,"firmware not complete status%h app%h conv=%d/%d MACstatus=%h CPUfault=%b CPUerr=%h cache=%h state=%d desc=%h",auto_status,dut.cpu_app_error,dut.conv_error,dut.conv_error_code,dut.local_cpu.status_word,dut.cpu_fault,dut.cpu_error_code,dut.local_cpu.memory.error_code,dut.local_cpu.state,dut.cpu_descriptor);
  rd(32'h07ff0000,208);if(word(48)!==4||word(64)!==14||word(80)!==6)$fatal(1,"bad committed mailbox");
  rd(32'h3000,256);
  for(co=0;co<2;co=co+1)for(ho=0;ho<2;ho=ho+1)for(wo=0;wo<2;wo=wo+1)begin
   actual=0;for(ci=0;ci<3;ci=ci+1)actual=actual+(ci*3+ho*2+wo-5)*(co+ci-2);
   if(word(co*128+ho*64+wo*4)!==actual)$fatal(1,"actual Tile integer mismatch");
  end
  rd(32'h6000,128);
  for(co=0;co<2;co=co+1)for(ho=0;ho<3;ho=ho+1)begin
   actual=0;for(ci=0;ci<5;ci=ci+1)actual=actual+(ci*3+ho-7)*(co+ci-3);
   if(word(co*64+ho*4)!==actual)$fatal(1,"actual Matrix integer mismatch");
  end
  command(8'h78,0,0,2);command(8'h79,0,0,2);
  payload[0]=2;payload[1]=0;payload[2]=0;payload[3]=0;command(8'h7f,4,0,0);if(got_value!==14)$fatal(1,"latched node monitor");
  // A finished run cannot restart without CLEAR, then an early abort cannot
  // publish the stale successful result from the preceding firmware run.
  ctrl(1,32'h735129ab,4);ctrl(3,32'h735129ab,0);ctrl(1,32'h735129ab,0);
  ctrl(2,32'h735129ab,0);wait_end();if(auto_status[2]||!auto_status[3]||!auto_status[6])$fatal(1,"abort published old result %h",auto_status);
  $display("PASS autonomous full core: real RV32/cache/8OC+CPU-sequenced-MatMul/CDC/DDR adapter;14 integer outputs, token/BUSY/abort/no-stale-complete guards; packets%0d",packets);$finish;
 end
endmodule
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--firmware',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);fw=a.firmware.read_bytes();(out/'program.hex').write_text(''.join(f'{b:02x}\n'for b in fw))
 native=base.NATIVE.replace('mem[0:262143]','mem[0:524287]').replace('npu_ddr_core_8oc','npu_ddr_core_autonomous')
 before='else if(a>=32\'h07ff0000&&a<32\'h08000000)mapped=32\'h30000+(a&65535);'
 after="else if(a>=32'h05000000&&a<32'h05020000)mapped=32'h40000+(a&131071);else if(a>=32'h07fd0000&&a<32'h07fe0000)mapped=32'h60000+(a&65535);else if(a>=32'h07ff0000&&a<32'h08000000)mapped=32'h70000+(a&65535);"
 assert before in native;native=native.replace(before,after)
 text=base.OLD_TB.split(' initial begin')[0].replace("wire[7:0]bus_data=host_oe?host_data:data_oe?data_o:8'bz;","wire[7:0]bus_data;assign bus_data=host_oe?host_data:8'bz;")
 text=text.replace(' npu_conv_link #(.TIMEOUT(700000)) dut(clk,reset_n,arm,bus_clk,dir,bus_data,data_o,data_oe,ready);',native).replace('n=8+words*4+2','n=8+words+2').replace('dut.state','dut.link.state')
 (out/'tb.v').write_text(text+MAIN.replace('@LAST@',str(len(fw)-1)).replace('@SIZE@',str(len(fw))))
 names=['npu_ddr_core_autonomous','npu_ddr_sys_autonomous','npu_local_run_control','npu_local_cpu_subsystem','npu_local_rv32_regs','npu_rv32_ddr_cache','npu_ddr_matmul_sequencer','conv_tile_engine_8oc','npu_ddr_tile_loader_8oc','npu_ddr_arbiter']
 sources=[ROOT/f'fpga/npu/rtl/{n}.v'for n in names]+[ROOT/'fpga/npu/vendor/picorv32/picorv32.v']+[ROOT/f'fpga/mem/rtl/{n}.v'for n in ['memv1_bridge','mem_adapter','memv1_crc32b']]
 env=dict(os.environ);env['PATH']=str(TOOLS)+os.pathsep+env['PATH'];logs=[];passed=False
 try:
  for cmd in [[str(TOOLS/'iverilog.exe'),'-g2012','-DPICORV32_REGS=npu_local_rv32_regs','-s','tb_conv_link','-o','test.vvp',*[str(x)for x in sources],'tb.v'],[str(TOOLS/'vvp.exe'),'test.vvp']]:
   r=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,timeout=300);logs.append(dict(command=cmd,exit_code=r.returncode,output=r.stdout+r.stderr));(out/'commands.json').write_text(json.dumps(logs,indent=2)+'\n');print(r.stdout+r.stderr,flush=True);assert r.returncode==0,logs[-1]
  passed=True
 finally:(out/'result.json').write_text(json.dumps(dict(passed=passed,hardware_access=False,scope='Actual RV32IMC, cache, real8OC MAC and CPU-sequenced MatMul, CDC/DDR adapter; only native DDR PHY is fake. Tiny program, not full model.',hardware_matrix_sequencer=False,firmware_sha256=hashlib.sha256(fw).hexdigest(),sources_sha256={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in sources}),indent=2)+'\n')
if __name__=='__main__':main()
