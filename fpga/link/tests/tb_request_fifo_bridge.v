`timescale 1ns/1ps
module tb_request_fifo_bridge;
reg clk=0,filter=0,rst=0,arm=0,dir=0,bus_clk=0;reg[7:0]data=0;
wire[7:0]out;wire oe,ready;
GSR GSR(1'b1);
always #9.259 clk=~clk;always #2.315 filter=~filter;
link_bringup_filtered #(.REQUEST_CAPTURE_FIFO(1)) dut(clk,rst,arm,bus_clk,dir,data,out,oe,ready,filter,rst);
reg[7:0]q[0:7];integer i,n;reg[15:0]crc;
function[15:0]step(input[15:0]c,input[7:0]b);reg[15:0]v;integer k;begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;step=v;end endfunction
task put(input[7:0]b);begin data=b;#25;bus_clk=1;#25;bus_clk=0;end endtask
task packet;begin for(i=0;i<8;i=i+1)put(q[i]);#500;end endtask
task waitready;begin n=0;while(!ready && n<1000)begin #20;n=n+1;end if(!ready)$fatal(1,"response timeout");end endtask
initial begin
 q[0]=8'ha5;q[1]=2;q[2]=7;q[3]=2;q[4]=8'h5a;q[5]=8'ha5;crc=16'hffff;
 for(i=0;i<6;i=i+1)crc=step(crc,q[i]);q[6]=crc[7:0];q[7]=crc[15:8];
 #1;rst=1;#5;rst=0;#40;rst=1;arm=1;#500;
 force dut.capture_ready=0;packet();if(dut.rx_index!==0)$fatal(1,"parser consumed without ready");
 release dut.capture_ready;waitready();if(dut.reply[1]!==0 || dut.reply[4]!==8'h5a || dut.reply[5]!==8'ha5)$fatal(1,"stalled packet corruption");
 // Response held in DIR0 blocks parser; excess incoming bytes must fail closed.
 for(i=0;i<40;i=i+1)put(i);#500;
 if(!dut.capture_overflow || ready || oe || !dut.batch_abort)$fatal(1,"overflow failclosed");
 dir=1;#300;dir=0;#300;if(!dut.capture_overflow || ready || oe)$fatal(1,"overflow not sticky");
 arm=0;#200;arm=1;#500;packet();waitready();if(dut.reply[1]!==0)$fatal(1,"reARM recovery");
 arm=0;bus_clk=1;#200;arm=1;#500;if(dut.rx_index!==0)$fatal(1,"stopped HIGH fake byte");
 bus_clk=0;#200;packet();waitready();if(dut.reply[1]!==0)$fatal(1,"stopped clock recovery");
 $display("FIFO bridge PASS backpressure/overflow/failclosed/DIR/sticky/ARM/stoppedHIGH");$finish;
end
initial begin #100000;$fatal(1,"watchdog");end
endmodule
