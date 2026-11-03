`timescale 1ns/1ps
module tb_tx_capture;
reg clk=0,rst=0,arm=0,bus=0,dir=0;reg[7:0]din=0;wire[7:0]dout;wire oe,ready;
link_bringup #(.TIMEOUT_CYCLES(10000),.TX_CAPTURE_ENABLE(1)) dut(clk,rst,arm,bus,dir,din,dout,oe,ready);
always #9.259 clk=~clk;
reg[7:0]q[0:7],got[0:7];reg[15:0]c;integer i,j,n=0;
function[15:0]crc(input[15:0]c,input[7:0]b);reg[15:0]v;integer k;begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end endfunction
task pulse;begin #500;bus=1;#1000;bus=0;#500;end endtask
task send;begin dir=0;#250;for(i=0;i<8;i=i+1)begin din=q[i];pulse();end end endtask
task make(input[7:0]op,input[7:0]a,input[7:0]b);begin
q[0]=8'ha5;q[1]=op;q[2]=8'h72;q[3]=2;q[4]=a;q[5]=b;c=16'hffff;for(j=0;j<6;j=j+1)c=crc(c,q[j]);q[6]=c[7:0];q[7]=c[15:8];end endtask
task read;begin wait(ready);dir=1;#250;for(i=0;i<8;i=i+1)begin got[i]=dout;pulse();end
c=16'hffff;for(j=0;j<6;j=j+1)c=crc(c,got[j]);if(got[6]!=c[7:0]||got[7]!=c[15:8])$fatal(1,"replyCRC");dir=0;#250;n=n+1;end endtask
task query(input[7:0]op,input[7:0]a,input[7:0]status,input[15:0]word);begin make(op,a,0);send();read();if(got[1]!=status || (status==0 && {got[5],got[4]}!=word))$fatal(1,"query%h/%d status%h word%h expected%h",op,a,got[1],{got[5],got[4]},word);end endtask
initial begin
#100;rst=1;arm=1;#250;
query(8'h42,0,0,16'h0103);query(8'h43,0,5,0);
// Actualmisframed8samplebytes, plus2extraDIR0clocks, not inventedheader.
q[0]=1;q[1]=8'h0c;q[2]=2;q[3]=0;q[4]=0;q[5]=8'h3a;q[6]=8'h27;q[7]=8'hd9;send();din=8'hee;pulse();pulse();read();
if(got[1]!=1||got[2]!=2)$fatal(1,"badrequestresponse");
query(8'h44,0,0,10);query(8'h44,1,0,16'h0805);query(8'h44,2,0,1);
query(8'h43,0,0,16'h0c01);query(8'h43,1,0,16'h0002);query(8'h43,2,0,16'h3a00);query(8'h43,3,0,16'hd927);
// ValidID/debugqueries never overwritecapture, partial3bytes neverformbad8.
make(1,0,0);send();read();dir=0;#250;din=8'h11;pulse();din=8'h22;pulse();din=8'h33;pulse();dir=1;#250;dir=0;#250;
query(8'h43,3,0,16'hd927);query(8'h44,0,0,10);query(8'h44,2,0,1);
// CRC-onlybadpacketcapturesall8, includingCURRENTlastbyte, notoldbyte7.
make(2,8'h55,8'haa);q[7]=q[7]^8'h80;send();read();query(8'h44,2,0,2);query(8'h44,0,0,8);
query(8'h43,0,0,16'h02a5);query(8'h43,2,0,16'haa55);
query(8'h43,4,3,0);query(8'h44,3,3,0);query(8'h42,1,3,0);
// Completebadheader timeout retainsactual8 butneverclaimsDIRcountlatched.
make(2,0,0);q[7]=q[7]^1;send();#200000;
query(8'h44,1,0,16'h0801);query(8'h44,0,0,0);
// Saturationlogiccheckedbyforcedregisterstate, not a physicalfrequencytest.
make(2,0,0);q[7]=q[7]^1;send();force dut.dir_edges=16'hffff;din=0;pulse();release dut.dir_edges;read();
query(8'h44,1,0,16'h0807);query(8'h44,0,0,16'hffff);
arm=0;#100;arm=1;#100;query(8'h43,0,5,0);
$display("PASS TXcapture%0dqueries actual8/persistence/extraedges/partial/CRC/reset",n);$finish;
end
initial begin #3000000;$fatal(1,"watchdog");end
endmodule
