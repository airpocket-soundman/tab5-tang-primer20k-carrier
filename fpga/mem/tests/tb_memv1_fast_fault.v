`timescale 1ns/1ps
// Conditioned-clock fault must kill output ownership, then allow an explicit
// new request. No DDR3 vendor model is involved in this control-path test.
module tb_memv1_fast_fault;
reg cal=1;
reg sys=0,sample=0,bus=0,reset_n=0,arm=1,dir=0;reg [7:0] di=0;
always #18.5185 sys=~sys;always #2.314815 sample=~sample;
wire [7:0] data_o;wire oe,ready;
memv1_sys #(.FAST_REPLY_ENABLE(1)) dut(.clk(sys),.reset_n(reset_n),.arm(arm),.bus_clk(bus),.dir(dir),.data_i(di),
 .data_o(data_o),.data_oe(oe),.ready(ready),.command_done(1'b0),.command_status(8'b0),.command_result(16'b0),
 .cal_user(cal),.user_rst_n_user(1'b1),.bist_busy_user(1'b0),.done_t(1'b0),.r_tag(24'b0),.r_status(4'b0),
 .r_crc(32'b0),.r_beats(16'b0),.r_data(128'b0),.diag(9'b0),.reply_sample_clk(sample),.reply_sample_reset_n(reset_n));
function [15:0] crc_byte;input [15:0] c;input [7:0] b;reg [15:0] v;integer k;
 begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
endfunction
reg [7:0] frame[0:17];reg [15:0] crc;integer i;
task request;begin
 dir=0;#500;frame[0]=8'ha5;frame[1]=8'h60;frame[2]=8'h17;frame[3]=2;frame[4]=0;frame[5]=0;
 crc=16'hffff;for(i=0;i<6;i=i+1)crc=crc_byte(crc,frame[i]);frame[6]=crc[7:0];frame[7]=crc[15:8];
 for(i=0;i<8;i=i+1)begin di=frame[i];#250;bus=1;#250;bus=0;end
 wait(ready);dir=1;#500;
end endtask
reg saw_fault=0;
always @(posedge dut.filter_fault)begin saw_fault=1;#0.001;if(ready||oe)$fatal(1,"filter fault failed immediate kill");end
initial begin
 #200;reset_n=1;#2000;request;
 // 50MHz pulses are narrower than the conditioning cooldown. Fault is expected.
 repeat(30)begin bus=1;#10;bus=0;#10;end
 #200;if(!saw_fault)$fatal(1,"no filter fault observed");if(ready||oe)$fatal(1,"reply resumed after fault");
 dir=0;#500;request;if(data_o!==8'h5a||!oe)$fatal(1,"new request did not recover");
 repeat(8)begin #250;bus=1;#250;bus=0;end
 #500;
 // In-flight generation loss creates STALE on the same edge as gen++.
 dir=0;#500;frame[0]=8'ha5;frame[1]=8'h62;frame[2]=8'h18;frame[3]=2;frame[4]=1;frame[5]=0;
 crc=16'hffff;for(i=0;i<6;i=i+1)crc=crc_byte(crc,frame[i]);frame[6]=crc[7:0];frame[7]=crc[15:8];
 for(i=8;i<16;i=i+1)begin frame[i]=0;crc=crc_byte(crc,0);end
 frame[16]=crc[7:0];frame[17]=crc[15:8];
 for(i=0;i<18;i=i+1)begin di=frame[i];#250;bus=1;#250;bus=0;end
 #500;cal=0;#500;cal=1;wait(ready);dir=1;#500;
 for(i=0;i<8;i=i+1)begin
  #250;if(i==1&&data_o!==8'd10)$fatal(1,"same-edge STALE lost or wrong status");
  bus=1;#250;bus=0;
 end
 #500;if(ready)$fatal(1,"STALE response did not retire");
 arm=0;#1;if(oe||ready)$fatal(1,"ARM kill");
 $display("PASS memv1 fast fault: cooldown fault kills OE/READY, no automatic resume, new request recovers, same-edge gen STALE is delivered");$finish;
end
initial begin #100000;$fatal(1,"deadline");end
endmodule
