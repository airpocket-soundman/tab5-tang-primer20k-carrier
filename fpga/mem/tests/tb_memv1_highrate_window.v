`timescale 1ps/1ps
// Isolated real RTL filter/phase/serializer plus synchronous128bit read RAM.
// A bounded sensitivity model, not electrical timing or metastability proof.
module tb_memv1_highrate_window;
parameter PHASE_TICKS=3;
integer sample_rising=0;
integer period_ps=37500,high_ps=18750,phase_ps=0,wire_ps=0,tco_ps=0,jitter_ps=0;
reg configured=0,sample=0,reset_n=0,host_clk=0,host_dir=0,offer=0;
integer jitter_sign=1;
initial begin wait(configured);#(phase_ps);forever begin #(2315+jitter_sign*jitter_ps);sample=1;#2315;sample=0;jitter_sign=-jitter_sign;end end
wire raw_clk,dir;wire clean_clk,reply_clk,fault;
assign #(wire_ps) raw_clk=host_clk;assign #(wire_ps) dir=host_dir;
reply_clock_filter filter(sample,reset_n,raw_clk,offer&&dir,clean_clk,fault);
reply_phase_delay #(.TICKS(PHASE_TICKS)) phase(sample,reset_n,clean_clk,reply_clk);
wire [7:0] data_o,addr;wire done,started,progress,error;reg [127:0] ram_data=0;
memv1_reply_raw serializer(reply_clk,reset_n&&offer,dir,48'h0001025c005a,2'd1,9'd256,32'b0,1'b1,ram_data,data_o,addr,done,started,progress,error);
reg [127:0] ram[0:255];integer a,b;
function [7:0] pattern;input integer i;begin pattern=(i*73)^(i>>3)^((i>>8)*29)^8'ha7;end endfunction
initial for(a=0;a<256;a=a+1)for(b=0;b<16;b=b+1)ram[a][b*8+:8]=pattern(a*16+b);
always @(posedge reply_clk)ram_data<=ram[addr];
wire [7:0] returned;
assign #(wire_ps+tco_ps) returned=(reset_n&&host_dir&&offer&&!done&&!error&&!fault)?data_o:8'bz;
reg [7:0] expected[0:4113],got[0:4121];
integer i,k,offset,hits,matched,first_bad;
integer raw_rises=0,clean_rises=0,reply_rises=0,fault_seen=0;
time last_raw=0,min_filter=999999,max_filter=0,latency;
always @(posedge raw_clk)if(offer&&dir)begin raw_rises=raw_rises+1;last_raw=$time;end
always @(posedge clean_clk)if(offer&&dir)begin
 clean_rises=clean_rises+1;latency=$time-last_raw;
 if(latency<min_filter)min_filter=latency;if(latency>max_filter)max_filter=latency;
end
always @(posedge reply_clk)if(offer&&dir)reply_rises=reply_rises+1;
always @(posedge fault)fault_seen=1;
reg [1023:0] vecpath;
initial begin
 if(!$value$plusargs("RISING=%d",sample_rising))begin end
 if(!$value$plusargs("PERIOD=%d",period_ps))begin end
 if(!$value$plusargs("HIGH=%d",high_ps))begin end
 if(!$value$plusargs("PHASE=%d",phase_ps))begin end
 if(!$value$plusargs("WIRE=%d",wire_ps))begin end
 if(!$value$plusargs("TCO=%d",tco_ps))begin end
 if(!$value$plusargs("JITTER=%d",jitter_ps))begin end
 if(!$value$plusargs("VEC=%s",vecpath))$fatal(1,"missing vector");
 $readmemh(vecpath,expected);configured=1;
 #200000;reset_n=1;
 #200000;host_clk=1; // Physical idle HIGH established while DIR0.
 #200000;offer=1;#200000;host_dir=1;#200000;
 // Positive API corresponds to physical falling in the current host route.
 for(i=0;i<4122;i=i+1)begin
  #(high_ps);host_clk=0;if(!sample_rising)got[i]=returned;
  #(period_ps-high_ps);host_clk=1;if(sample_rising)got[i]=returned;
 end
 #200000;hits=0;offset=-1;first_bad=-1;
 for(i=0;i<=8;i=i+1)begin
  matched=1;
  for(k=0;k<4114;k=k+1)if(got[i+k]!==expected[k])matched=0;
  if(matched)begin hits=hits+1;offset=i;end
 end
 if(hits!=1)begin
  // Characterize mismatch against the nominal prefix9/header9 alignment.
  for(k=0;k<4114;k=k+1)if(first_bad<0&&got[1+k]!==expected[k])first_bad=k;
 end
 $display("WINDOW,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",period_ps,high_ps,phase_ps,wire_ps,tco_ps,jitter_ps,hits,offset,raw_rises,clean_rises,reply_rises,min_filter,max_filter,fault_seen,first_bad);
 if(raw_rises!=clean_rises||clean_rises!=reply_rises||fault_seen||error)$fatal(1,"nominal waveform lost/repeated qualified edge");
 $finish;
end
initial begin #200000000;$fatal(1,"deadline");end
endmodule
