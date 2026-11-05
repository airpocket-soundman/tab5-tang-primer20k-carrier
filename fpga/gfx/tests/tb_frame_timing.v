`timescale 1ns/1ps
module tb_frame_timing;
 reg clk=0,reset_n=0,abort=0,start=0;
 always #5 clk=~clk;
 reg [7:0] opcode=0,a=0,b=0;
 wire done,off_done;wire [7:0] status,off_status;wire [15:0] result;
`ifdef VENDOR_RAM
 GSR GSR(1'b1);
`endif
 triangle_tile #(.CLOCK_QUERY_ENABLE(1),.FRAME_TIMING_ENABLE(1)) dut(
  .clk(clk),.reset_n(reset_n),.abort(abort),.start(start),.opcode(opcode),.a(a),.b(b),
  .done(done),.status(status),.result(result),.row_index(11'b0),.row_byte(),
  .raw_clk(clk),.raw_enable(1'b0),.raw_address(10'b0),.raw_color(),.raw_depth());
 triangle_tile #(.CLOCK_QUERY_ENABLE(1)) off_dut(
  .clk(clk),.reset_n(reset_n),.abort(abort),.start(start),.opcode(opcode),.a(a),.b(b),
  .done(off_done),.status(off_status),.result(),.row_index(11'b0),.row_byte(),
  .raw_clk(clk),.raw_enable(1'b0),.raw_address(10'b0),.raw_color(),.raw_depth());
 integer exchanges=0,cycles,n;
 reg [31:0] sum,tile_cycles;
 reg [15:0] low_word;
 task command;
  input [7:0] op;input [15:0] value;input [7:0] expected_status;
  input check_value;input [15:0] expected_result;
  begin
   @(negedge clk);opcode=op;a=value[7:0];b=value[15:8];start=1;
   @(negedge clk);start=0;cycles=0;
   if(op>=8'h79 && op<=8'h7c && (!off_done || off_status!==2))$fatal(1,"featureOFF accepted op%h",op);
   while(!done)begin @(negedge clk);cycles=cycles+1;if(cycles>200000)$fatal(1,"command timeout %h",op);end
   if(status!==expected_status || (check_value && result!==expected_result))
    $fatal(1,"op%h status%h result%h expected%h/%h",op,status,result,expected_status,expected_result);
   exchanges=exchanges+1;@(negedge clk);
  end
 endtask
 task configure;
  input [15:0] config_value;
  begin
   command(8'h31,16'hf000,0,1,16'hf000);command(8'h32,16'hf800,0,1,16'hf800);
   command(8'h33,132,0,1,132);command(8'h34,132,0,1,132);
   command(8'h35,16'hf47b,0,1,16'hf47b);command(8'h36,819,0,1,819);
   command(8'h37,config_value,0,1,config_value);
  end
 endtask
 task draw_and_count;
  begin
   command(8'h38,0,0,1,1024);
   command(8'h39,0,0,0,0);low_word=result;
   command(8'h3a,0,0,0,0);tile_cycles={result,low_word};
   if(!tile_cycles)$fatal(1,"zero tile cycles");
  end
 endtask
 task read_sum;
  input [31:0] expected;
  begin command(8'h7b,0,0,1,expected[15:0]);command(8'h7c,0,0,1,expected[31:16]);end
 endtask
 initial begin
  repeat(3)@(negedge clk);reset_n=1;
  command(8'h30,0,0,1,16'h021f); // unchanged strict legacy capability value
  command(8'h79,0,0,1,16'h0120);
  command(8'h7b,0,5,1,0);command(8'h7c,0,5,1,0);
  command(8'h79,1,3,1,0);command(8'h7a,1,3,1,0);
  command(8'h7b,1,3,1,0);command(8'h7c,256,3,1,0);
  configure(16);draw_and_count();
  command(8'h7b,0,5,1,0); // draws before RESET do not enable frame timing
  command(8'h7a,0,0,1,0);sum=0;read_sum(0);
  for(n=0;n<4;n=n+1)begin
   configure(n[0]?16'h0118:16'h0010);draw_and_count();sum=sum+tile_cycles;read_sum(sum);
  end
  // Invalid reset cannot clear a valid accumulated frame.
  command(8'h7a,1,3,1,0);read_sum(sum);
  command(8'h7a,0,0,1,0);read_sum(0);
  command(8'h2b,16'h0042,0,1,0);read_sum(0); // nonfractal work excluded
  configure(24);draw_and_count();read_sum(tile_cycles); // next frame independent
  // Fault injection avoids billions of simulated cycles, tests the real
  // add/carry path on the next legitimate complete tile, not a forced flag.
  @(negedge clk);dut.frame_cycles_total=32'hfffffff0;
  draw_and_count();
  if(!dut.frame_timer_overflow)$fatal(1,"overflow carry not sticky");
  command(8'h7b,0,5,1,0);command(8'h7c,0,5,1,0);
  command(8'h2b,0,0,1,0);command(8'h7b,0,5,1,0);
  command(8'h7a,0,0,1,0);read_sum(0);
  configure(128);
  @(negedge clk);opcode=8'h38;a=0;b=0;start=1;
  @(negedge clk);start=0;repeat(20)@(negedge clk);abort=1;
  @(negedge clk);abort=0;
  command(8'h7b,0,5,1,0);command(8'h7c,0,5,1,0);
  command(8'h7a,0,0,1,0);read_sum(0);
  reset_n=0;#1;reset_n=1;
  command(8'h7b,0,5,1,0);command(8'h7c,0,5,1,0);
  $display("FRAME TIMING RTL PASS: %0d commands, exact per-tile sum, independent frames, disabled, args, overflow, abort/reset",exchanges);
  $finish;
 end
 initial begin #100000000;$fatal(1,"watchdog");end
endmodule
