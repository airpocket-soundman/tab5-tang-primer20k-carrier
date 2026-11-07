
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,abort=0,clear=0,memory_ready=1,job_valid=0,out_ready=0;
reg[575:0]job=0;
wire job_ready,busy,out_valid,result_valid,error,quarantined,tile_abort,descriptor_valid;
wire[3:0]error_code;wire[31:0]accepted_tiles,completed_tiles,expected_tiles;wire[415:0]descriptor;
reg descriptor_ready=0,tile_busy=0,tile_done=0,tile_error=0,tile_quarantined=0,tile_result_valid=0;
npu_ddr_conv_strip_sequencer #(.TILE_TIMEOUT(40),.DRAIN_TIMEOUT(12))dut(.*);
integer mode=0,cycle=0,timer=0,sticky=0,seen=0,ci=0,f,fd,rc,t,holdn,public_accepts=0,before_accepts;reg saved_final;
reg stalled=0;reg[415:0]snapshot;
always @(negedge clk)begin
 cycle=cycle+1;descriptor_ready=mode!=1&&(cycle%5!=0)&&(cycle%7!=0);
 if(!reset_n)begin tile_busy=0;tile_done=0;tile_error=0;tile_quarantined=0;tile_result_valid=0;timer=0;sticky=0;seen=0;end
 else if(tile_abort&&mode!=2)begin tile_busy=0;timer=0;if(sticky>0)begin sticky=sticky-1;if(!sticky)tile_done=0;end end
 else if(tile_busy)begin
  if(mode==2)begin end
  else begin timer=timer-1;if(timer==0)begin tile_busy=0;tile_done=1;sticky=2+(cycle%4);tile_result_valid=saved_final&&mode!=8;
   if(mode==4)tile_error=1;if(mode==7)tile_quarantined=1;
  end end
 end else if(tile_done)begin sticky=sticky-1;if(!sticky)tile_done=0;end
 if(reset_n&&seen>0&&mode==6)memory_ready=0;
 if(reset_n&&seen>0&&mode==9)abort=1;
end
always @(posedge clk)begin
 // Independent consumer: only standard valid&&ready, not a private consumer gate.
 if(reset_n&&out_valid&&out_ready)begin
  public_accepts=public_accepts+1;
  if(abort||!memory_ready)$fatal(1,"public result handshake during abort/cal-loss");
 end

 if(!reset_n)stalled<=0;
 else begin
  if(stalled&&descriptor_valid&&snapshot!==descriptor)$fatal(1,"descriptor changed under backpressure");
  stalled<=descriptor_valid&&!descriptor_ready;snapshot<=descriptor;
  if(abort&&descriptor_valid)$fatal(1,"descriptor visible during abort");
  if(descriptor_valid&&descriptor_ready)begin
   if(tile_busy||tile_done)$fatal(1,"overlapping/stale completion");
   $fdisplay(fd,"D %0d %0104h",ci,descriptor);seen=seen+1;saved_final=descriptor[49];tile_busy<=1;timer=2+(cycle%8);
  end
 end
end
initial begin
 f=$fopen("jobs.txt","r");fd=$fopen("trace.txt","w");
 while(!$feof(f))begin
  @(negedge clk);reset_n=0;abort=0;clear=0;job_valid=0;out_ready=0;memory_ready=1;
  repeat(4)@(negedge clk);reset_n=1;
  rc=$fscanf(f,"%d %h\n",mode,job);if(rc!=2)$fatal(1,"input parse");
  job_valid=1;if(mode==5)abort=1;
  @(posedge clk);#1;
  @(negedge clk);job_valid=0;job=0;
  if(mode==5)begin
   repeat(10)@(negedge clk);if(busy||out_valid||seen)$fatal(1,"abort did not dominate accept");
   $fdisplay(fd,"R %0d 0 0 0 0 0 0",ci);
  end else begin
   t=0;while(!out_valid&&t<200000)begin @(negedge clk);t=t+1;
    if(mode==6&&dut.out_valid_q)begin memory_ready=1;mode=16;end
    if(mode==9&&dut.out_valid_q)begin abort=0;mode=10;end
   end
   if(!out_valid)$fatal(1,"job did not finish");
   $fdisplay(fd,"R %0d %0d %0d %0d %0d %0d %0d",ci,result_valid,error,error_code,quarantined,accepted_tiles,completed_tiles);
   if(mode==9)begin abort=0;mode=10;end
   // Completion stays stable until consumed, no numeric validity on failure.
   for(holdn=0;holdn<5;holdn=holdn+1)begin @(negedge clk);if(!out_valid||busy||(error&&result_valid))$fatal(1,"completion/backpressure");end
   if((mode==0||mode==15)&&result_valid)begin
    before_accepts=public_accepts;out_ready=1;job_valid=1;
    if(mode==15)memory_ready=0;else abort=1;

    @(negedge clk);job_valid=0;out_ready=0;
    if(public_accepts!=before_accepts||result_valid||out_valid||busy)$fatal(1,"abort/cal-loss accepted stale success");
    abort=0;
   end
  end
  ci=ci+1;
 end
 $display("PASS RTL strip jobs=%0d",ci);$fclose(fd);$finish;
end
endmodule
