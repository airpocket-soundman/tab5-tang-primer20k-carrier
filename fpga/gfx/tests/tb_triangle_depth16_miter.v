`timescale 1ns/1ps
module tb_triangle_depth16_miter;
 localparam COUNT=6000;
 reg clk=0,reset_n=0,in_valid=0,out_ready=0;
 reg [383:0] sample=0;
 reg [383:0] inputs[0:COUNT-1];reg [63:0] expected[0:COUNT-1];
 wire ready_new,valid_new,bad_new,pass_new,ready_old,valid_old,bad_old,pass_old;
 wire [15:0] depth_new,depth_old;
 wire [63:0] actual_new={46'b0,pass_new,bad_new,depth_new},actual_old={46'b0,pass_old,bad_old,depth_old};
 integer n,cycle,lat_new,lat_old,k,aborts=0;
 reg [383:0] saved;reg [63:0] held_new,held_old;
 always #5 clk=~clk;
 triangle_depth newer(.clk(clk),.reset_n(reset_n),.in_valid(in_valid),.in_ready(ready_new),.covered(sample[0]),.area(sample[383:320]),.weight_a(sample[319:256]),.weight_b(sample[255:192]),.weight_c(sample[191:128]),.za(sample[127:112]),.zb(sample[111:96]),.zc(sample[95:80]),.old_depth(sample[79:64]),.out_valid(valid_new),.out_ready(out_ready),.invalid_input(bad_new),.depth_pass(pass_new),.new_depth(depth_new));
 triangle_depth49_reference older(.clk(clk),.reset_n(reset_n),.in_valid(in_valid),.in_ready(ready_old),.covered(sample[0]),.area(sample[383:320]),.weight_a(sample[319:256]),.weight_b(sample[255:192]),.weight_c(sample[191:128]),.za(sample[127:112]),.zb(sample[111:96]),.zc(sample[95:80]),.old_depth(sample[79:64]),.out_valid(valid_old),.out_ready(out_ready),.invalid_input(bad_old),.depth_pass(pass_old),.new_depth(depth_old));
 initial begin
  $readmemh("miter-inputs.mem",inputs);$readmemh("miter-expected.mem",expected);
  #1;reset_n=1;#1;reset_n=0;#1;
  if(ready_new!==0 || valid_new!==0 || actual_new!==0 || ready_old!==0 || valid_old!==0 || actual_old!==0)$fatal(1,"initial reset");
  @(negedge clk);reset_n=1;
  for(n=0;n<COUNT;n=n+1)begin
   @(negedge clk);if(!ready_new || !ready_old)$fatal(1,"not ready %0d",n);
   saved=inputs[n];sample=saved;in_valid=1;out_ready=0;
   @(posedge clk);#1;lat_new=valid_new?0:-1;lat_old=valid_old?0:-1;cycle=0;
   while(!valid_old || !valid_new)begin
    @(negedge clk);sample=~sample;in_valid=1;
    if(ready_new || ready_old)$fatal(1,"accepted mutable inputs while busy");
    @(posedge clk);#1;cycle=cycle+1;
    if(valid_new && lat_new<0)begin lat_new=cycle;held_new=actual_new;end
    if(valid_old && lat_old<0)lat_old=cycle;
    if(lat_new>=0 && actual_new!==expected[n])$fatal(1,"new mismatch %0d",n);
    if(cycle>50)$fatal(1,"timeout");
   end
   if(actual_new!==expected[n] || actual_old!==expected[n])$fatal(1,"numeric mismatch %0d new%h old%h expected%h",n,actual_new,actual_old,expected[n]);
   if(saved[0] && !expected[n][16])begin
    if(lat_new!=16 || lat_old!=49)$fatal(1,"latency %0d %0d",lat_new,lat_old);
   end else if(lat_new!=0 || lat_old!=0)$fatal(1,"early latency");
   held_new=actual_new;held_old=actual_old;
   for(k=0;k<n%7;k=k+1)begin @(posedge clk);#1;if(!valid_new || !valid_old || actual_new!==held_new || actual_old!==held_old)$fatal(1,"stall changed output");end
   @(negedge clk);in_valid=0;out_ready=1;@(posedge clk);#1;
   if(valid_new || valid_old || !ready_new || !ready_old)$fatal(1,"consume");
   @(negedge clk);out_ready=0;
   // Abort at differing pipeline positions, including new-held/old-dividing.
   if(n%17==0)begin
    sample=inputs[100];in_valid=1;@(posedge clk);#1;
    @(negedge clk);in_valid=0;
    for(k=0;k<n%55;k=k+1)begin @(posedge clk);#1;end
    @(negedge clk);reset_n=0;#1;
    if(valid_new!==0 || valid_old!==0 || actual_new!==0 || actual_old!==0)$fatal(1,"abort reset");
    @(negedge clk);reset_n=1;aborts=aborts+1;
   end
  end
  $display("PASS depth16 old/new + Python oracle cases=%0d aborts=%0d valid latency16vs49; invalid/uncovered0; stalls0..6",COUNT,aborts);$finish;
 end
endmodule
