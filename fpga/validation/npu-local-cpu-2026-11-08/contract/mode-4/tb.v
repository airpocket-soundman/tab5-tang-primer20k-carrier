
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,memory_ready=1,run_enable=0,abort=0,clear=0;reg[15:0]epoch=37;
wire cpu_trap,cpu_fault,safe_to_release;wire[3:0]cpu_error_code;wire[31:0]progress_node,progress_stage,app_error,finish_code;
wire tile_start,tile_clear,matrix_start,matrix_done_ack;wire[415:0]tile_descriptor;wire[287:0]matrix_job;
reg tile_start_ready=1,tile_busy=0,tile_done=0,tile_error=0,tile_quarantined=0,tile_result_valid=0;reg[3:0]tile_error_code=0;
reg matrix_start_ready=1,matrix_busy=0,matrix_done=0,matrix_error=0,matrix_quarantined=0,matrix_result_valid=0;reg[3:0]matrix_error_code=0;
wire req_t,cancel_t;wire[1:0]h_op;wire[31:0]h_addr,h_arg;wire[15:0]h_beats;wire[23:0]h_tag;
reg done_t=0;reg[23:0]r_tag=0;reg[3:0]r_status=0;reg[15:0]r_beats=0;
wire w_we;wire[7:0]w_addr,r_addr;wire[127:0]w_data;reg[127:0]r_data=0;
npu_local_cpu_subsystem #(.MEMORY_TIMEOUT(1000),.DRAIN_TIMEOUT(50),.MAC_TIMEOUT(10000))dut(.*);
reg[7:0]ddr[0:1048575],program_bytes[0:2571];reg[127:0]stage,readbuf;
reg req_ref=0;integer fault_mode=4,fault_age=0,fault_requests=0;reg cancel_seen=0;
integer pending=0,cycles=0,requests=0,writes=0,reads=0,tile_jobs=0,matrix_jobs=0;
reg[31:0]pending_addr;reg[1:0]pending_op;reg[23:0]pending_tag;
integer i,k,j,n,m,oc,ic,y,x,sum,pos,mac_timer=0;
function integer s8;input integer a;begin s8=$signed(ddr[a&1048575]);end endfunction
function[31:0]u32;input integer a;begin u32={ddr[(a+3)&1048575],ddr[(a+2)&1048575],ddr[(a+1)&1048575],ddr[a&1048575]};end endfunction
task put32;input integer a;input integer v;integer z;begin for(z=0;z<4;z=z+1)ddr[(a+z)&1048575]=v>>(z*8);end endtask
always @(posedge clk)begin
 cycles<=cycles+1;r_data<=readbuf;
 if(w_we)stage<=w_data;
 if(req_t!=req_ref)begin
  if(pending||tile_busy||matrix_busy)$fatal(1,"CPU DDR request while outstanding/MAC owns staging");
  if(h_beats!=1||h_addr[3:0]||h_addr>=32'h08000000)$fatal(1,"bad CPU request");
  req_ref<=req_t;pending<=7+(cycles%5);pending_addr<=h_addr;pending_op<=h_op;pending_tag<=h_tag;requests<=requests+1;
 end else if(pending>0)begin
  if(cancel_t)cancel_seen<=1;
  if(fault_mode==2&&!cancel_seen)pending<=pending;else begin
  pending<=pending-1;
  if(pending==1)begin
   if(pending_op==0)begin for(j=0;j<16;j=j+1)readbuf[j*8+:8]<=ddr[(pending_addr+j)&1048575];reads<=reads+1;end
   else if(pending_op==1)begin for(j=0;j<16;j=j+1)ddr[(pending_addr+j)&1048575]<=stage[j*8+:8];writes<=writes+1;end
   else $fatal(1,"unsupported CPU opcode");
   r_tag<=fault_mode==1?pending_tag+1:pending_tag;r_status<=fault_mode==5?3:fault_mode==2?8:0;r_beats<=fault_mode==2?0:1;done_t<=~done_t;
  end
 end end
 tile_done<=0;
 if(matrix_done_ack)begin matrix_done<=0;matrix_result_valid<=0;end
 if(tile_start)begin
  if(tile_busy||matrix_busy||pending)$fatal(1,"tile started without clean barrier");
  tile_busy<=1;tile_start_ready<=0;tile_result_valid<=0;tile_jobs<=tile_jobs+1;mac_timer<=25;
  for(oc=0;oc<tile_descriptor[8+:4];oc=oc+1)for(y=0;y<tile_descriptor[16+:5];y=y+1)for(x=0;x<tile_descriptor[24+:5];x=x+1)begin
   sum=0;
   for(ic=0;ic<tile_descriptor[0+:5];ic=ic+1)sum=sum+s8(tile_descriptor[160+:32]+ic*tile_descriptor[224+:32]+y*tile_descriptor[192+:32]+x)*s8(tile_descriptor[256+:32]+oc*tile_descriptor[288+:32]+ic);
   put32(tile_descriptor[320+:32]+oc*tile_descriptor[384+:32]+y*tile_descriptor[352+:32]+x*4,sum);
  end
 end
 if(matrix_start)begin
  if(tile_busy||matrix_busy||pending)$fatal(1,"matrix started without clean barrier");
  matrix_busy<=1;matrix_start_ready<=0;matrix_result_valid<=0;matrix_jobs<=matrix_jobs+1;mac_timer<=30;
  for(n=0;n<matrix_job[64+:32];n=n+1)for(m=0;m<matrix_job[0+:32];m=m+1)begin
   sum=0;for(k=0;k<matrix_job[32+:32];k=k+1)sum=sum+s8(matrix_job[96+:32]+k*matrix_job[128+:32]+m)*s8(matrix_job[160+:32]+n*matrix_job[192+:32]+k);
   put32(matrix_job[224+:32]+n*matrix_job[256+:32]+m*4,sum);
  end
 end
 if(mac_timer>0&&fault_mode!=7)begin mac_timer<=mac_timer-1;
  if(mac_timer==1)begin
   if(tile_busy)begin tile_busy<=0;tile_start_ready<=1;tile_done<=1;tile_result_valid<=1;end
   if(matrix_busy)begin matrix_busy<=0;matrix_start_ready<=1;matrix_done<=1;matrix_result_valid<=1;end
  end
 end
 if(cpu_fault||cpu_trap)begin
  if(fault_mode==0)$fatal(1,"CPU fault %d PC=%h state=%d cache=%d instr=%h",cpu_error_code,dut.cpu.reg_pc,dut.state,dut.memory.state,dut.cpu.dbg_insn_opcode);
  if(!fault_age)fault_requests<=requests;
  fault_age<=fault_age+1;
  if(fault_age==65)begin
   if(finish_code!=0||requests!=fault_requests)$fatal(1,"fault fabricated success or retried");
   if((fault_mode==1||fault_mode==4||fault_mode==7)&&safe_to_release)$fatal(1,"quarantine released owner");
   if((fault_mode==2||fault_mode==3||fault_mode==5||fault_mode==6)&&!safe_to_release)$fatal(1,"drained fault did not release");
   $display("PASS actual CPU fault mode%0d code%0d requests%0d no success/retry safe%0d",fault_mode,cpu_error_code,requests,safe_to_release);$finish;
  end
 end
 if((abort||!memory_ready)&&dut.native_ready)$fatal(1,"abort/cal-loss accepted native response");
 if(finish_code!=0)begin
  if(finish_code!=1||app_error!=0||u32(32'h07ff0030)!=4||u32(32'h07ff0034)!=0||u32(32'h07ff0040)!=14)$fatal(1,"firmware failure code=%d app=%d state=%d nodes=%d",finish_code,app_error,u32(32'h07ff0030),u32(32'h07ff0040));
  if(!safe_to_release)$fatal(1,"FINISH before drain");
  if(tile_jobs!=1||matrix_jobs!=1)$fatal(1,"wrong MAC counts");
  $display("PASS actual RV32IMC smoke:14 independent outputs; tile=%0d matrix=%0d requests=%0d reads=%0d writes=%0d cycles=%0d",tile_jobs,matrix_jobs,requests,reads,writes,cycles);$finish;
 end
 if(cycles>2000000)$fatal(1,"CPU smoke timeout PC=%h state=%d cache=%d",dut.cpu.reg_pc,dut.state,dut.memory.state);
end
always @(negedge clk)begin
 if(fault_mode==3&&pending==3&&requests==1)abort=1;
 if(fault_mode==4&&pending==3&&requests==1)memory_ready=0;
 if(fault_mode==6&&dut.memory.state==4)abort=1;
end
initial begin
 for(i=0;i<1048576;i=i+1)ddr[i]=0;stage=0;readbuf=0;
 $readmemh("program.hex",program_bytes);
 for(i=0;i<2572;i=i+1)ddr[i]=program_bytes[i];
 repeat(5)@(negedge clk);reset_n=1;repeat(5)@(negedge clk);
 if(!safe_to_release)$fatal(1,"initial START prerequisite deadlock");run_enable=1;
end
endmodule
