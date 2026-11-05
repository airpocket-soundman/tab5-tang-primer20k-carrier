`timescale 1ns/1ps
module tb_request_ff_equivalence;
reg clk=0,filter=0,rst=0,arm=0,bus_clk=0,dir=0;
reg[7:0] d=0;
wire[7:0] a,b;wire ao,bo,ar,br;
always #9.259 clk=~clk;
always #2.315 filter=~filter;
GSR GSR(1'b1);
link_bringup_filtered #(.REQUEST_DATA_PIPELINE(1),.REQUEST_DATA_FF(0)) oldcore(clk,rst,arm,bus_clk,dir,d,a,ao,ar,filter,rst);
link_bringup_filtered #(.REQUEST_DATA_PIPELINE(1),.REQUEST_DATA_FF(1)) newcore(clk,rst,arm,bus_clk,dir,d,b,bo,br,filter,rst);
integer i;
always @(negedge clk) begin
 if(oldcore.request_data!==newcore.request_data || a!==b || ao!==bo || ar!==br) $fatal(1,"legacy/FF mismatch");
end
initial begin
 #1;rst=1;#3;rst=0;#30;rst=1;arm=1;
 for(i=0;i<10000;i=i+1) begin
 #7;d=$random;bus_clk=$random;dir=$random;
 if(i%137==0) begin rst=0;#3;rst=1;end
 end
 #100;$display("request FF/default equivalence PASS 10000 async changes/reset pulses");$finish;
end
endmodule
