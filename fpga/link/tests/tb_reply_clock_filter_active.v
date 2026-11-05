`timescale 1ps/1ps
module tb_reply_clock_filter_active;
 reg clk=0,reset_n=0,raw=0,active=0;
 always #2315 clk=~clk;
 wire clean_old,fault_old,clean_pipe,fault_pipe;
 reply_clock_filter old_filter(clk,reset_n,raw,active,clean_old,fault_old);
 reply_clock_filter #(.ACTIVE_PIPELINE(1)) piped_filter(clk,reset_n,raw,active,clean_pipe,fault_pipe);
 integer old_rises=0,pipe_rises=0,n,old_before,pipe_before;
 always @(posedge clean_old) old_rises=old_rises+1;
 always @(posedge clean_pipe) pipe_rises=pipe_rises+1;
 task ticks;input integer count;begin repeat(count)@(negedge clk);end endtask
 task slow_pulse;begin raw=1;ticks(8);raw=0;ticks(8);end endtask
 task trip;begin
  raw=0;active=1;ticks(10);
  raw=1;ticks(2);raw=0;ticks(2);raw=1;ticks(2);raw=0;ticks(12);
  if(!fault_old || !fault_pipe)$fatal(1,"active short-spacing did not latch fault");
 end endtask
 initial begin
  ticks(3);reset_n=1;ticks(6);
  // Both versions retain the old inactive slow-request clock pass-through.
  old_before=old_rises;pipe_before=pipe_rises;
  for(n=0;n<12;n=n+1)slow_pulse();
  if(old_rises-old_before!=12 || pipe_rises-pipe_before!=12 || fault_old || fault_pipe)
   $fatal(1,"inactive request clocks changed");
  trip();
  // Reset clears even a latched fault while the external clock is stopped.
  reset_n=0;#1;
  if(clean_old || clean_pipe || fault_old || fault_pipe)$fatal(1,"async reset failed");
  ticks(3);active=0;reset_n=1;ticks(8);
  trip();
  // Check actual 2FF propagation: the consuming fault register clears on
  // the third sample edge after the inactive input changes before edge1.
  active=0;
  @(posedge clk);#1;if(fault_old || !fault_pipe)$fatal(1,"first-edge clear behavior wrong");
  @(posedge clk);#1;if(!fault_pipe)$fatal(1,"fault bypassed second synchronizer stage");
  @(posedge clk);#1;if(fault_pipe)$fatal(1,"synchronized inactive failed to clear fault");
  @(negedge clk);ticks(8);
  // A request clock may start immediately at the DIR/active falling edge.
  // Raw-clock qualification takes long enough to see synchronized inactive.
  trip();old_before=old_rises;pipe_before=pipe_rises;
  active=0;raw=1;ticks(8);raw=0;ticks(8);
  if(old_rises-old_before!=1 || pipe_rises-pipe_before!=1 || fault_old || fault_pipe)
   $fatal(1,"first inactive request pulse lost after a fault");
  active=1;ticks(8);old_before=old_rises;pipe_before=pipe_rises;
  for(n=0;n<12;n=n+1)slow_pulse();
  if(old_rises-old_before!=12 || pipe_rises-pipe_before!=12 || fault_old || fault_pipe)
   $fatal(1,"active restart failed");
  // Inactive close-spaced pulses may be dropped by the existing cooldown,
  // but must not latch a policy fault in either version.
  active=0;ticks(8);raw=1;ticks(2);raw=0;ticks(2);raw=1;ticks(2);raw=0;ticks(12);
  if(fault_old || fault_pipe)$fatal(1,"inactive fault unexpectedly latched");
  reset_n=0;#1;if(clean_old || clean_pipe || fault_old || fault_pipe)$fatal(1,"final reset failed");
  $display("FILTER ACTIVE PIPELINE PASS: legacy direct, 2FF policy latency, request clocks, fault, stop/restart, async reset");
  $finish;
 end
 initial begin #10000000;$fatal(1,"watchdog");end
endmodule
