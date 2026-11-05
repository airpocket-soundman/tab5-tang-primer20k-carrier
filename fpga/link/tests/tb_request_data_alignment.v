// Synthetic digital timing model only: no analog/signal-integrity claim.
// TX DATA changes on falling CLK, while CLK arrives later by CLK_SKEW_PS.
`timescale 1ps/1ps
module tb_request_data_alignment;
 parameter integer CLK_SKEW_PS=0;
 reg clk=0,filter_clk=0,reset_n=0,arm=0,raw_clk=0,dir=0;
 reg [7:0] data_i=0;
 always #9259 clk=~clk;       //18518ps approximates54MHz
 always #2315 filter_clk=~filter_clk;
 wire bus_clk;assign #(CLK_SKEW_PS) bus_clk=raw_clk;
 wire [7:0] legacy_data,aligned_data;
 wire legacy_oe,legacy_ready,aligned_oe,aligned_ready;
`ifdef FILTERED_CORE
 link_bringup_filtered #(.GFX_ENABLE(2),.ALL_SCENES_ENABLE(1),.REQUEST_DATA_PIPELINE(0),.TIMEOUT_CYCLES(2000000)) old_core(
  clk,reset_n,arm,bus_clk,dir,data_i,legacy_data,legacy_oe,legacy_ready,filter_clk,reset_n);
 link_bringup_filtered #(.GFX_ENABLE(2),.ALL_SCENES_ENABLE(1),.REQUEST_DATA_PIPELINE(1),.TIMEOUT_CYCLES(2000000)) new_core(
  clk,reset_n,arm,bus_clk,dir,data_i,aligned_data,aligned_oe,aligned_ready,filter_clk,reset_n);
`else
 link_bringup #(.GFX_ENABLE(2),.ALL_SCENES_ENABLE(1),.REQUEST_DATA_PIPELINE(0),.TIMEOUT_CYCLES(2000000)) old_core(
  clk,reset_n,arm,bus_clk,dir,data_i,legacy_data,legacy_oe,legacy_ready);
 link_bringup #(.GFX_ENABLE(2),.ALL_SCENES_ENABLE(1),.REQUEST_DATA_PIPELINE(1),.TIMEOUT_CYCLES(2000000)) new_core(
  clk,reset_n,arm,bus_clk,dir,data_i,aligned_data,aligned_oe,aligned_ready);
`endif
 reg [7:0] q[0:1289],r[0:7];
 reg [15:0] c,value;
 reg mismatch;
 integer length=8,i,j,n,phase,seq=0,packets=0,legacy_mismatches=0,cycles;
 function [15:0] crc;
  input [15:0] old;input [7:0] b;reg [15:0] v;integer k;
  begin v=old^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end
 endfunction
 task header;
  input [7:0] op;input [15:0] args;input [7:0] status;input [15:0] result;
  begin
   seq=seq+1;length=8;
   q[0]=8'ha5;q[1]=op;q[2]=seq;q[3]=2;q[4]=args[7:0];q[5]=args[15:8];
   c=16'hffff;for(i=0;i<6;i=i+1)c=crc(c,q[i]);q[6]=c[7:0];q[7]=c[15:8];
   r[0]=8'h5a;r[1]=status;r[2]=seq;r[3]=2;r[4]=result[7:0];r[5]=result[15:8];
   c=16'hffff;for(i=0;i<6;i=i+1)c=crc(c,r[i]);r[6]=c[7:0];r[7]=c[15:8];
  end
 endtask
 task exchange;
  begin
   dir=0;raw_clk=0;#200000;
   for(j=0;j<length;j=j+1) begin
    // Exactly one byte per125ns at8MHz; stable only between falls.
    data_i=q[j];#62500;raw_clk=1;#62500;raw_clk=0;
   end
   // Preserve final byte like the real TX driver does.
   #2000000;
   cycles=0;while(!aligned_ready && cycles<1000000)begin #18518;cycles=cycles+1;end
   if(!aligned_ready)$fatal(1,"aligned timeout packet%0d",packets);
   mismatch=!legacy_ready;dir=1;#200000;
   for(j=0;j<8;j=j+1)begin
    if(!aligned_oe || aligned_data!==r[j])
     $fatal(1,"aligned packet%0d byte%0d got%02x expected%02x",packets,j,aligned_data,r[j]);
    if(!legacy_oe || legacy_data!==r[j])mismatch=1;
    #100000;raw_clk=1;#100000;raw_clk=0;#100000;
   end
   if(mismatch)legacy_mismatches=legacy_mismatches+1;
   if(aligned_ready || aligned_oe)$fatal(1,"aligned reply not consumed");
   dir=0;#200000;packets=packets+1;
  end
 endtask
 initial begin
  #100000;reset_n=1;arm=1;#100000;
  for(phase=0;phase<5;phase=phase+1)begin
   // Distinct request/sample phases; the long frame also walks SYS phases.
   #(phase*3500+1);
   header(1,0,0,16'h5054);exchange();
   header(2,16'ha35c,0,16'ha35c);exchange();
   header(8'h60,0,0,16'h011f);exchange();
   header(8'h2b,16'h0042,0,0);exchange();
   header(8'h6e,16'h0140,0,16'h0140);
   for(n=0;n<64;n=n+1)begin
    for(i=0;i<10;i=i+1)begin
     case(i)
      0,2:value=n%32;1,3:value=n/32;4:value=16'h6b5a;
      default:value=0;
     endcase
     q[8+n*20+i*2]=value[7:0];q[9+n*20+i*2]=value[15:8];
    end
   end
   c=16'hffff;for(i=0;i<6;i=i+1)c=crc(c,q[i]);
   for(i=8;i<1288;i=i+1)c=crc(c,q[i]);
   q[1288]=c[7:0];q[1289]=c[15:8];length=1290;exchange();
   // Bad header CRC must still be rejected with aligned diagnostics.
   header(1,0,1,0);q[6]=q[6]^1;exchange();
  end
  if(CLK_SKEW_PS==0 && legacy_mismatches!=0)$fatal(1,"legacy zero-skew regression");
  if(CLK_SKEW_PS>=20000 && legacy_mismatches==0)$fatal(1,"timing stress did not exercise the late-sample failure");
  $display("REQUEST DATA ALIGNMENT PASS: skew%0dps packets%0d aligned_exact%0d legacy_mismatches%0d",CLK_SKEW_PS,packets,packets,legacy_mismatches);
  $finish;
 end
 initial begin #10000000000;$fatal(1,"watchdog");end
endmodule
