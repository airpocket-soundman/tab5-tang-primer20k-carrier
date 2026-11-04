`timescale 1ps/1ps
// Same vector protocol as tb_triangle_model.v, but against link_bringup_filtered (216 MHz reply
// filter + source-synchronous reply, the structure of the 85bac224-class filtered image) with the
// MODEL_ENABLE=1 resident model. Tagged (sync-prefix) replies are read with the 40 MHz-style half period of tb_filteredreply_control.v;
// untagged ordinary 8-byte replies use the slow legacy half period (500 ns), as that bench does.
module tb_triangle_model_filtered;
reg filter_clk=0;always #2315 filter_clk=~filter_clk;
reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;reg[7:0] host_data=0;
wire[7:0] data_o;wire oe,ready;
always #9259 clk=~clk;
link_bringup_filtered #(.GFX_ENABLE(2),.MODEL_ENABLE(1),.FAST_REPLY_ENABLE(1),.CLOCK_QUERY_ENABLE(1),.CORE_CLOCK_MHZ(54),.TIMEOUT_CYCLES(5400000)) dut(clk,reset_n,arm,bus_clk,dir,host_data,data_o,oe,ready,filter_clk,reset_n&&arm);
always @(posedge clk) begin
 if(host_oe && oe)$fatal(1,"contention");
 if(dut.model_receiving && dut.model_cmd_start)$fatal(1,"unvalidated execution");
end
reg[7:0] q[0:1289],r[0:2065];integer fd,qlen,rlen,i,n,waits,vectors=0;reg[1023:0] path;
initial begin
#100000;reset_n=1;arm=1;#200000;
if(!$value$plusargs("vectors=%s",path))$fatal(1,"vectors missing");fd=$fopen(path,"r");
while(!$feof(fd)) begin
 n=$fscanf(fd,"%d %d",qlen,rlen);
 if(n==2)begin
 for(i=0;i<qlen;i=i+1)n=$fscanf(fd,"%h",q[i]);
 for(i=0;i<rlen;i=i+1)n=$fscanf(fd,"%h",r[i]);
 dir=0;bus_clk=0;#200000;host_oe=1;
 for(i=0;i<qlen;i=i+1)begin host_data=q[i];#500000;bus_clk=1;#500000;bus_clk=0;#500000;
  if(qlen>8 && i<qlen-1 && dut.model_cmd_start)$fatal(1,"execution before final CRC");end
 host_oe=0;waits=0;while(!ready && waits<400000000)begin #1000;waits=waits+1;end
 if(!ready)$fatal(1,"READY timeout vector%0d",vectors);
 bus_clk=1;#200000;bus_clk=0;dir=1;#2000000;
 for(i=0;i<rlen;i=i+1)begin
  if(!ready || !oe || data_o!==r[i])$fatal(1,"vector%0d byte%0d got%h want%h ready%0d oe%0d op%h",vectors,i,data_o,r[i],ready,oe,q[1]);
  if(q[1][7])begin bus_clk=1;#12500;bus_clk=0;#12500;end else begin bus_clk=1;#500000;bus_clk=0;#500000;end end
 #1;if(ready||oe)$fatal(1,"not released after last byte vector%0d",vectors);
 dir=0;#200000;vectors=vectors+1;
 end
end
$display("PASS filtered model pin-level vectors=%0d",vectors);$finish;
end
initial begin #400000000000;$fatal(1,"watchdog");end
endmodule
