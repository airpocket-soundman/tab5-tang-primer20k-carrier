`timescale 1ns/1ps
// Functional post-PnR netlist simulation with ideal PLL outputs. No SDF/STA claim.
module tb_all_scenes_gate;
reg sys_clk=0,core_clock=0,filter_clock=0,reset_n=0,arm_sw=0,bus_clk=0,dir=0;
reg [7:0] data_i=0;
wire [7:0] data;
wire ready;wire [3:0] led;
assign data=dir?8'bz:data_i;
GSR GSR(1'b1);
always #18.5185 sys_clk=~sys_clk;
always #9.259 core_clock=~core_clock;
always #2.3148 filter_clock=~filter_clock;
tab5_dock_all_scenes_top dut(sys_clk,reset_n,arm_sw,bus_clk,dir,4'b0,ready,led,data);
initial begin
 force dut.core_clk=core_clock;force dut.filter_clk=filter_clock;
 force dut.core_locked=1'b1;force dut.filter_locked=1'b1;
end
always @(posedge core_clock) begin
 if(dut.\core/triangle.d2_cmd_start )
  $display("D2CMD t%0t field%0d word%h a%h b%h",$time,dut.\core/field_0 ,dut.\core/command_word_0 ,dut.\core/renderer_a ,dut.\core/renderer_b );
 if(dut.\core/gfx_done )
  $display("GFXDONE t%0t status%0d result%h",$time,dut.\core/gfx_status ,dut.\core/gfx_result );
end
reg [7:0] q[0:1289],r[0:2065];
integer fd,qlen,rlen,i,n,cycles,vectors=0;
reg [2047:0] path;
task pulse;begin
`ifdef BUS8
 #31.25;bus_clk=1;#62.5;bus_clk=0;#31.25;
`else
 #200;bus_clk=1;#200;bus_clk=0;#200;
`endif
end endtask
initial begin
 #200;reset_n=1;arm_sw=1;#1000;
 if(!$value$plusargs("vectors=%s",path))$fatal(1,"vectors missing");
 fd=$fopen(path,"r");
 while(!$feof(fd)) begin
  n=$fscanf(fd,"%d %d",qlen,rlen);
  if(n==2)begin
   for(i=0;i<qlen;i=i+1)n=$fscanf(fd,"%h",q[i]);
   for(i=0;i<rlen;i=i+1)n=$fscanf(fd,"%h",r[i]);
   dir=0;#200;
   for(i=0;i<qlen;i=i+1)begin data_i=q[i];pulse();end
   cycles=0;while(!ready && cycles<200000)begin #20;cycles=cycles+1;end
   if(!ready)$fatal(1,"gate timeout vector%0d",vectors);
   dir=1;#400;
   for(i=0;i<rlen;i=i+1)begin
    if(data!==r[i])$fatal(1,"gate vector%0d byte%0d got%h want%h",vectors,i,data,r[i]);
    pulse();
   end
   #200;if(ready)$fatal(1,"gate reply not complete");
   dir=0;#400;vectors=vectors+1;
  end
 end
 $display("all-scenes post-PnR functional gate PASS vectors%0d",vectors);$finish;
end
initial begin #50000000;$fatal(1,"gate watchdog");end
endmodule
