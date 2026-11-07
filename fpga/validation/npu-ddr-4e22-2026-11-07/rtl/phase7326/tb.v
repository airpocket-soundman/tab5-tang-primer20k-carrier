
`timescale 1ps/1ps
module tb;
 reg clk=0;always begin #18518;clk=1;#18519;clk=0;end
 reg reset_n=0,arm=0,bus_clk=0,dir=0;reg[7:0]data_i=0;
 wire[7:0]bo,ao;wire be,ae,br,ar;
 npu_ddr_sys_baseline #(.TIMEOUT(27000000),.REQUEST_DATA_PIPELINE(0)) baseline(.clk(clk),.reset_n(reset_n),.arm(arm),.bus_clk(bus_clk),.dir(dir),.data_i(data_i),.data_o(bo),.data_oe(be),.ready(br),.memory_ready(1'b1),.generation(16'd0),.arbiter_fault(1'b0),.arbiter_active(1'b0),.conv_start_ready(1'b1),.conv_busy(1'b0),.conv_done(1'b0),.conv_error(1'b0),.conv_quarantined(1'b0),.conv_error_code(4'd0),.kernel_cycles(32'd0),.ddr_wait_cycles(32'd0),.total_cycles(32'd0),.done_t(1'b0),.r_tag(24'd0),.r_status(4'd0),.r_beats(16'd0),.r_data(128'd0));npu_ddr_sys_aligned #(.TIMEOUT(27000000),.REQUEST_DATA_PIPELINE(1)) aligned(.clk(clk),.reset_n(reset_n),.arm(arm),.bus_clk(bus_clk),.dir(dir),.data_i(data_i),.data_o(ao),.data_oe(ae),.ready(ar),.memory_ready(1'b1),.generation(16'd0),.arbiter_fault(1'b0),.arbiter_active(1'b0),.conv_start_ready(1'b1),.conv_busy(1'b0),.conv_done(1'b0),.conv_error(1'b0),.conv_quarantined(1'b0),.conv_error_code(4'd0),.kernel_cycles(32'd0),.ddr_wait_cycles(32'd0),.total_cycles(32'd0),.done_t(1'b0),.r_tag(24'd0),.r_status(4'd0),.r_beats(16'd0),.r_data(128'd0));
 integer f,rc,tests,id,freq,mode,phase,delay_data,half,n,j,k,waited,scount_b,scount_a,bad_b,bad_a,first_b,first_a,bstat,astat,bh,ah,packet_b,packet_a;
 reg[7:0]frame[0:2063],rb[0:7],ra[0:7];reg recording=0;
 function[15:0]crcbyte;input[15:0]c;input[7:0]b;reg[15:0]v;integer z;begin v=c^{b,8'd0};for(z=0;z<8;z=z+1)v=v[15]?(v<<1)^16'h1021:v<<1;crcbyte=v;end endfunction
 reg[15:0]bc,ac;
 always @(posedge clk)if(recording&&reset_n&&arm)begin
  if(baseline.state==0&&baseline.rise&&!dir&&!baseline.ds[1])begin if(scount_b>=n||data_i!==frame[scount_b])begin bad_b=bad_b+1;if(first_b<0)first_b=scount_b;end scount_b=scount_b+1;end
  if(aligned.state==0&&aligned.rise&&!dir&&!aligned.ds[1])begin if(scount_a>=n||aligned.data_capture!==frame[scount_a])begin bad_a=bad_a+1;if(first_a<0)first_a=scount_a;end scount_a=scount_a+1;end
 end
 initial begin
 f=$fopen("D:/GitHub/airpocket-soundman/tab5-tang-primer20k-carrier-resume-20261106/fpga/build/npu-rx-production-param-full/vectors.txt","r");rc=$fscanf(f,"%d",tests);
 for(id=0;id<tests;id=id+1)begin
  rc=$fscanf(f,"%d %d %d %d %d %d",freq,mode,phase,delay_data,half,n);if(rc!=6)$fatal(1,"vector header");
  for(j=0;j<n;j=j+1)begin rc=$fscanf(f,"%d",k);frame[j]=k;end
  recording=0;reset_n=0;arm=0;bus_clk=0;dir=0;data_i=8'h7e;repeat(5)@(posedge clk);#123;reset_n=1;arm=1;repeat(5)@(posedge clk);
  scount_b=0;scount_a=0;bad_b=0;bad_a=0;first_b=-1;first_a=-1;recording=1;
  @(posedge clk);#(phase);if(mode==0)data_i=frame[0];
  #(half);
  for(j=0;j<n;j=j+1)begin
   bus_clk=1;
   if(mode==1)begin #(delay_data);data_i=frame[j];#(half-delay_data);end else #(half);
   bus_clk=0;
   if(mode==0)begin #(delay_data);data_i=j+1<n?frame[j+1]:8'h7e;#(half-delay_data);end else #(half);
  end
  #500000;recording=0;packet_b=1;packet_a=1;
  for(j=0;j<n-18;j=j+1)begin if(baseline.packet[j]!==frame[j+16])packet_b=0;if(aligned.packet[j]!==frame[j+16])packet_a=0;end
  dir=1;waited=0;while((!br||!ar)&&waited<100)begin #37037;waited=waited+1;end
  bstat=255;astat=255;bh=0;ah=0;
  for(j=0;j<8;j=j+1)begin
   #1000000;rb[j]=br?bo:8'hxx;ra[j]=ar?ao:8'hxx;bus_clk=1;#1000000;bus_clk=0;
  end
  if(rb[0]===8'h5a)bstat=rb[1];if(ra[0]===8'h5a)astat=ra[1];bc=16'hffff;ac=16'hffff;
  for(j=0;j<6;j=j+1)begin bc=crcbyte(bc,rb[j]);ac=crcbyte(ac,ra[j]);end
  if({rb[7],rb[6]}===bc)bh=1;if({ra[7],ra[6]}===ac)ah=1;
  $display("CASE %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",id,freq,mode,phase,delay_data,n,bstat,astat,bh,ah,scount_b,scount_a,bad_b,bad_a,packet_b,packet_a);
  dir=0;#2000000;
 end
 $display("DONE %0d",tests);$finish;
 end
 initial begin #10000000000000;$fatal(1,"global timeout");end
endmodule
