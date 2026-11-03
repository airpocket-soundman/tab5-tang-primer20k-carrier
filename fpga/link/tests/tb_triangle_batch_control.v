`timescale 1ns/1ps
module tb_triangle_batch_control;
reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0;reg[7:0] data_i=0;
wire[7:0] data_o;wire oe,ready;integer i,cycles,commands=0,before_commands;reg[7:0] q[0:7];reg[15:0] c;reg[15:0] record[0:9];integer k;
link_bringup #(.GFX_ENABLE(2),.FAST_REPLY_ENABLE(1),.TIMEOUT_CYCLES(10000)) dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready);
always #5 clk=~clk;
always @(posedge clk)if(dut.batch_cmd_start)commands=commands+1;
function[15:0] crc(input[15:0] c,input[7:0] b);reg[15:0]v;integer k;begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end endfunction
task pulse;begin #60;bus_clk=1;#60;bus_clk=0;#60;end endtask
task header(input[7:0]op,input[7:0]a,input[7:0]b);begin
 dir=0;#100;q[0]=8'ha5;q[1]=op;q[2]=8'hff;q[3]=2;q[4]=a;q[5]=b;c=16'hffff;
 for(i=0;i<6;i=i+1)c=crc(c,q[i]);q[6]=c[7:0];q[7]=c[15:8];
 for(i=0;i<8;i=i+1)begin data_i=q[i];pulse();end
end endtask
task id;begin header(1,0,0);cycles=0;while(!ready && cycles<500)begin #10;cycles=cycles+1;end
 if(!ready)$fatal(1,"ID recovery timeout");dir=1;#100;
 for(i=0;i<8;i=i+1)begin if(i==4 && data_o!=8'h54)$fatal(1,"bad ID");pulse();end
 dir=0;#100;
end endtask
task partial;begin before_commands=commands;header(8'hc1,64,1);
 for(i=0;i<37;i=i+1)begin data_i=i;pulse();end
 if(ready||commands!=before_commands)$fatal(1,"partial executed");end endtask
initial begin
#100;reset_n=1;arm=1;#100;id();
partial();dir=1;#200;if(oe||ready||dut.batch_busy)$fatal(1,"DIR abort failed");dir=0;#100;id();
partial();arm=0;#1;if(oe||ready)$fatal(1,"ARM immediate");#100;arm=1;#100;id();
partial();reset_n=0;#1;if(oe||ready)$fatal(1,"reset immediate");#100;reset_n=1;#100;id();
partial();force dut.idle_count=9999;#20;release dut.idle_count;#100;if(dut.batch_busy||ready)$fatal(1,"timeout failed");id();
if(commands!=0)$fatal(1,"partial batch issued commands");
// Initialize tile, then interrupt a validated batch during real raster work.
header(8'h2b,0,0);wait(ready);dir=1;#100;for(i=0;i<8;i=i+1)pulse();dir=0;#100;
record[0]=0;record[1]=0;record[2]=512;record[3]=0;record[4]=0;record[5]=512;
record[6]=100;record[7]=100;record[8]=100;record[9]=16'hffff;
header(8'hc1,1,1);
for(k=0;k<20;k=k+1)begin data_i=k[0]?record[k/2][15:8]:record[k/2][7:0];c=crc(c,data_i);pulse();end
data_i=c[7:0];pulse();data_i=c[15:8];pulse();
wait(dut.triangle.renderer.state==5);arm=0;#1;if(oe||ready)$fatal(1,"execution ARM did not immediately remove drive");
#100;if(dut.batch_busy || dut.triangle.renderer.initialized)$fatal(1,"execution abort retained tile/batch");
before_commands=commands;#100;if(commands!=before_commands)$fatal(1,"postabort command replay");
arm=1;#100;id();
$display("PASS batch partial DIR/ARM/reset/timeout plus active raster ARM cancellation/recovery");$finish;
end
initial begin #1000000;$fatal(1,"watchdog");end
endmodule
