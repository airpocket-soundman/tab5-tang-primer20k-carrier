`timescale 1ns/1ps
module tb_mem_link;
reg clk=0;always #18.5185 clk=~clk;
reg reset=0,arm=0,bus=0,dir=0;reg[7:0] di=0;
wire[7:0] dout,op,a,b,status;wire[15:0] result;wire oe,ready,cs,cd;
reg done=0;reg[7:0] response_status=0;reg[15:0] response_result=0;
assign cd=done;assign status=response_status;assign result=response_result;
mem_link #(.TIMEOUT(10000)) dut(clk,reset,arm,bus,dir,di,dout,oe,ready,cs,op,a,b,cd,status,result);
always @(posedge clk)begin done<=cs;if(cs)begin
if(op==8'h50&&{b,a}==0)begin response_status<=0;response_result<=16'h014d;end
else begin response_status<=3;response_result<=0;end end end
function[15:0] crc;input[15:0] old;input[7:0] byte_value;reg[15:0] v;integer k;
begin v=old^{byte_value,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end endfunction
reg[7:0] q[0:7],r[0:7];reg[15:0] c;integer i,n,checks=0;reg[7:0] seqid=0;
task pulse;begin #500;bus=1;#500;bus=0;end endtask
task exchange;input[7:0] code,x,y,want_status;input[15:0] want_result;input bad;
begin
dir=0;#500;q[0]=8'ha5;q[1]=code;q[2]=seqid;q[3]=2;q[4]=x;q[5]=y;
c=16'hffff;for(i=0;i<6;i=i+1)c=crc(c,q[i]);q[6]=c[7:0];q[7]=c[15:8]^(bad?1:0);
for(i=0;i<8;i=i+1)begin di=q[i];pulse;end
n=0;while(!ready&&n<100)begin #100;n=n+1;end if(!ready)$fatal(1,"no reply");
dir=1;#500;if(!oe)$fatal(1,"no OE");
if(code[7]&&!bad)for(i=0;i<8;i=i+1)begin if(dout!=8'hc3)$fatal(1,"prefix");pulse;end
for(i=0;i<8;i=i+1)begin r[i]=dout;pulse;end
c=16'hffff;for(i=0;i<6;i=i+1)c=crc(c,r[i]);
if(r[0]!=8'h5a||r[1]!=want_status||r[2]!=seqid||r[3]!=2||{r[7],r[6]}!=c||{r[5],r[4]}!=want_result)$fatal(1,"reply %x status%0d seq%0d result%x",code,r[1],r[2],{r[5],r[4]});
if(ready||oe)$fatal(1,"reply did not end");dir=0;#500;seqid=seqid+1;checks=checks+1;
end endtask
initial begin
#500;reset=1;arm=1;#500;
exchange(1,0,0,0,16'h5054,0);exchange(8'h82,8'h5a,8'ha5,0,16'ha55a,0);
exchange(8'hd0,0,0,0,16'h014d,0);exchange(8'h50,1,0,3,0,0);
exchange(8'h40,0,0,2,0,0);exchange(8'h50,0,0,1,0,1);
// No complete request is fabricated after a partial transfer changes direction.
di=8'ha5;pulse;dir=1;#500;dir=0;#500;if(ready)$fatal(1,"partial request replied");
exchange(8'h84,0,0,0,16'h0108,0);
// Raw ARM removes OE without any SYS clock latency.
dir=0;for(i=0;i<8;i=i+1)begin di=q[i];pulse;end
dir=1;#500;arm=0;#1;if(oe||ready)$fatal(1,"raw disarm");
$display("PASS mem_link %0d packets: legacy/tagged CRC, dispatch, bad CRC, partial DIR, raw ARM",checks);$finish;
end
endmodule

