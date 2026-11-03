`timescale 1ns/1ps
module tb_triangle_batch;
reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0;reg[7:0] data_i=0;
wire[7:0] data_o;wire oe,ready;
link_bringup #(.GFX_ENABLE(2),.FAST_REPLY_ENABLE(1),.TIMEOUT_CYCLES(2000000)) dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready);
always #5 clk=~clk;
always @(posedge clk) if(dut.batch_receiving && dut.batch_cmd_start)$fatal(1,"unvalidated execution");
reg[7:0] q[0:1289],r[0:2065];integer fd,qlen,rlen,i,n,cycles,vectors=0;reg[1023:0] path;
task pulse;begin #60;bus_clk=1;#60;bus_clk=0;#60;end endtask
initial begin
#100;reset_n=1;arm=1;#100;
if(!$value$plusargs("vectors=%s",path))$fatal(1,"vectors missing");fd=$fopen(path,"r");
while(!$feof(fd)) begin
 n=$fscanf(fd,"%d %d",qlen,rlen);
 if(n==2)begin
 for(i=0;i<qlen;i=i+1)n=$fscanf(fd,"%h",q[i]);
 for(i=0;i<rlen;i=i+1)n=$fscanf(fd,"%h",r[i]);
 dir=0;#100;
 for(i=0;i<qlen;i=i+1)begin data_i=q[i];pulse();
 if(qlen>8 && i<qlen-1 && dut.batch_cmd_start)$fatal(1,"execution before finalCRC");end
 cycles=0;while(!ready && cycles<1900000)begin #10;cycles=cycles+1;end
 if(!ready)$fatal(1,"timeout vector%0d",vectors);
 dir=1;#100;
 for(i=0;i<rlen;i=i+1)begin
 if(!oe || data_o!==r[i])$fatal(1,"vector%0d byte%0d got%h want%h oe%0d",vectors,i,data_o,r[i],oe);
 pulse();end
 #50;if(ready||oe)$fatal(1,"not complete");dir=0;#100;vectors=vectors+1;
 end
end
$display("PASS batch pin-level vectors=%0d",vectors);$finish;
end
initial begin #1000000000;$fatal(1,"watchdog");end
endmodule
