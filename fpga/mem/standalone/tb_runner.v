`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,cal=0;wire tx;wire [5:0] burst;wire [2:0] cmd;wire ce,we,wend;wire [26:0] addr;wire [127:0] wd;wire [15:0] mask;reg [127:0] rd;reg rv=0;
ddr_bw_runner #(.BEATS(64),.CAL_TIMEOUT(10000),.UART_DIV(4)) dut(.clk(clk),.reset_n(reset_n),.calibrated(cal),.uart_tx(tx),.burst(burst),.cmd(cmd),.cmd_en(ce),.addr(addr),.cmd_ready(1'b1),.wr_data(wd),.wr_en(we),.wr_end(wend),.mask(mask),.wr_ready(1'b1),.rd_data(rd),.rd_valid(rv),.rd_end(1'b1));
reg [127:0] mem[0:63];integer q[0:1023];integer head=0,tail=0,wpos=0,k;integer fd;reg [7:0] bytev;integer bitn;integer frames=0;
function integer beataddr;input [26:0] a;reg [25:0] l;begin l={a[22:10],a[26:24],a[9:0]};beataddr=(l<<1)>>4;end endfunction
always @(posedge clk) if(reset_n) begin
 if(ce && cmd==0) wpos=beataddr(addr);
 if(we) begin if(wpos>=64) $fatal(1,"write range");if(!($test$plusargs("dropwrite") && dut.job==2)) mem[wpos]=wd;wpos=wpos+1;end
 if(ce && cmd==1) for(k=0;k<=burst;k=k+1) begin q[tail]=beataddr(addr)+k;tail=tail+1;end
end
always @(negedge clk) begin rv=0;if(reset_n && head<tail) begin rd=mem[q[head]];if($test$plusargs("corrupt") && dut.job==3 && head%64==0) rd=rd^128'd1;head=head+1;rv=1;end end
initial begin fd=$fopen("fpga/build/standalone-sim.bin","wb"); #40;reset_n=1;#100;cal=1;end
initial forever begin
 @(negedge tx); repeat(6) @(posedge clk);
 for(bitn=0;bitn<8;bitn=bitn+1) begin bytev[bitn]=tx;repeat(4) @(posedge clk);end
 if(tx!==1'b1) $fatal(1,"UART stop bit");$fwrite(fd,"%c",bytev);frames=frames+1;
end
initial begin wait(dut.state==7);repeat(20) @(posedge clk);$fclose(fd);if(frames!=(($test$plusargs("corrupt") || $test$plusargs("dropwrite"))?4:26)*111) $fatal(1,"wrong stream length %0d",frames);$display("PASS standalone runner UART records=%0d",frames/111);$finish;end
initial begin #2000000;$fatal(1,"timeout state=%d job=%d error=%d",dut.state,dut.job,dut.result_error);end
endmodule
