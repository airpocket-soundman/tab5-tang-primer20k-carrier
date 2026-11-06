"""Real mem_adapter+bridge and async staging RTL with a mock native DDR port."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
from run_ddr_tile_loader import ROOT,TB,fixtures
MODEL=r'''
 reg user_clk=0;always #5.022 user_clk=~user_clk;
 wire bridge_active,cmd_valid,cmd_ready,cancel,rsp_valid,adapter_busy;
 wire[1:0]cmd_op;wire[31:0]cmd_addr,cmd_arg,rsp_crc;wire[15:0]cmd_beats,rsp_beats;wire[23:0]cmd_tag,rsp_tag;wire[3:0]rsp_status;
 wire[7:0]stage_raddr,stage_waddr;wire[127:0]stage_rdata,stage_wdata;wire stage_we;
 wire[2:0]app_cmd;wire app_cmd_en;wire[26:0]app_addr;wire[127:0]app_write_data;
 wire app_write_en,app_write_end;wire[15:0]app_write_mask;reg[127:0]app_read_data=0;reg app_read_valid=0,app_read_end=0;
 reg[7:0]user_count=0;wire app_cmd_ready=reset_n && user_count[2:0]!=2;wire app_write_ready=reset_n && user_count[2:0]!=5;
 function [31:0] decode_native;input[26:0]a;reg[25:0]linear_word;
 begin linear_word={a[22:10],a[26:24],a[9:0]};decode_native={5'd0,linear_word,1'b0};end endfunction
 reg read_pending=0,write_cmd_pending=0,write_data_pending=0;reg[31:0]native_read_addr,native_write_addr;reg[127:0]native_write_data;integer read_delay=0;
 memv1_bridge bridge(user_clk,reset_n,req_t,cancel_t,h_op,h_addr,h_beats,h_arg,h_tag,done_t,r_tag,r_status, ,r_beats,
  bridge_active,cmd_valid,cmd_ready,cmd_op,cmd_addr,cmd_beats,cmd_arg,cmd_tag,cancel,
  rsp_valid,rsp_tag,rsp_status,rsp_crc,rsp_beats);
 mem_adapter #(.APP_ROW_PAD(1),.CAPACITY(CAP),.SETTLE_CYCLES(0),.TIMEOUT_CYCLES(128)) adapter(
  user_clk,reset_n,memory_ready,cmd_valid,cmd_ready,cmd_op,cmd_addr,cmd_beats,cmd_arg,cmd_tag,cancel,
  rsp_valid,rsp_tag,rsp_status,rsp_crc,rsp_beats,adapter_busy,
  stage_raddr,stage_rdata,stage_we,stage_waddr,stage_wdata,
  app_cmd,app_cmd_en,app_addr,app_cmd_ready,app_write_data,app_write_en,app_write_end,app_write_mask,app_write_ready,
  app_read_data,app_read_valid,app_read_end);
 memv1_dpram #(.AW(8),.DW(128)) write_ram(clk,w_we,w_addr,w_data,user_clk,stage_raddr,stage_rdata);
 memv1_dpram #(.AW(8),.DW(128)) read_ram(user_clk,stage_we,stage_waddr,stage_wdata,clk,r_addr,r_data);
 always @(posedge user_clk)begin
  if(!reset_n)begin user_count<=0;requests<=0;reads<=0;writes<=0;read_pending<=0;write_cmd_pending<=0;write_data_pending<=0;app_read_valid<=0;app_read_end<=0;app_read_data<=0;read_delay<=0;end
  else begin
   user_count<=user_count+1'b1;app_read_valid<=0;app_read_end<=0;
   if(cmd_valid && cmd_ready)begin
    if(cmd_addr[3:0]!=0 || cmd_beats<1 || cmd_beats>256 || {1'b0,cmd_addr}+cmd_beats*16>CAP || cmd_op>1)$fatal(1,"invalid real adapter request");requests<=requests+1;
   end
   if(app_cmd_en && app_cmd_ready)begin
    if(decode_native(app_addr)+16>CAP || app_addr[2:0]!=0)$fatal(1,"native alignment/range");
    if(app_cmd==1)begin if(read_pending)$fatal(1,"overlapping native read");read_pending<=1;native_read_addr<=decode_native(app_addr);read_delay<=4+user_count[1:0];end
    else if(app_cmd==0)begin if(write_cmd_pending)$fatal(1,"overlapping native write command");write_cmd_pending<=1;native_write_addr<=decode_native(app_addr);end
    else $fatal(1,"unexpected native command");
   end
   if(app_write_en && app_write_ready)begin
    if(write_data_pending || app_write_mask!=0 || !app_write_end)$fatal(1,"native write pairing/mask");write_data_pending<=1;native_write_data<=app_write_data;
   end
   if(write_cmd_pending && write_data_pending)begin
    for(z=0;z<16;z=z+1)mem[native_write_addr+z]<=native_write_data[z*8+:8];writes<=writes+1;write_cmd_pending<=0;write_data_pending<=0;
   end
   if(read_pending)begin
    if(read_delay!=0)read_delay<=read_delay-1;
    else begin for(z=0;z<16;z=z+1)app_read_data[z*8+:8]<=mem[native_read_addr+z];app_read_valid<=1;app_read_end<=1;read_pending<=0;reads<=reads+1;end
   end
  end
 end
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.output=a.output.resolve();vec=a.output/'vectors.txt';count=fixtures(vec)
 tbtext=TB.replace('reg done_t=0;reg[23:0]r_tag=0;reg[3:0]r_status=0;reg[15:0]r_beats=0;','wire done_t;wire[23:0]r_tag;wire[3:0]r_status;wire[15:0]r_beats;').replace('reg[127:0]r_data=0;','wire[127:0]r_data;')
 lo=tbtext.index(' always @(posedge clk)begin\n  if(w_we)');hi=tbtext.index(' integer f,rc,',lo);tbtext=tbtext[:lo]+MODEL+tbtext[hi:]
 cut=tbtext.index(' $fclose(f);');tbtext=tbtext[:cut]+''' $fclose(f);
 $display("PASS real mem_adapter/bridge dualclock DDR Conv jobs=%0d, independent fullDDRguard, random native stalls",good_jobs);$finish;
 end
 initial begin #300000000;$fatal(1,"global timeout");end
endmodule
'''
 tb=a.output/'tb_ddr_adapter.v';tb.write_text(tbtext.replace('VECTORS',vec.as_posix()));binary=a.output/'test.vvp';env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');logs=[];result={'passed':False,'jobs':count,'device_access':'none','scope':'Real mem_adapter/bridge/dualclockstaging RTL, mock native DDR; no PHY/board'}
 sources=[ROOT/'npu/rtl/npu_ddr_tile_loader.v',ROOT/'npu/rtl/conv_tile_engine.v',ROOT/'mem/rtl/mem_adapter.v',ROOT/'mem/rtl/memv1_bridge.v',ROOT/'mem/rtl/memv1_crc32b.v']
 try:
  for cmd in [[a.iverilog,'-g2012','-Wall','-s','tb_ddr_loader','-o',str(binary),*map(str,sources),str(tb)],[a.vvp,str(binary)]]:
   r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=300);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
  result.update(passed=True,output=logs[-1],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in sources})
 except Exception as e:result['error']=str(e);raise
 finally:(a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(logs[-1])
if __name__=='__main__':main()
