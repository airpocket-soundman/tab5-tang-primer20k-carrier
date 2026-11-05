`timescale 1ps/1ps
module tb_fast_filter_sync;
 parameter integer DIV_INTEGER=8,DIV_NUMERATOR=0,DIV_DENOMINATOR=1,PHASE_PS=0;
 reg clk=0,reset_n=0,raw=0,active=0;
 always #2315 clk=~clk;
 wire legacy_clean,legacy_fault,default_clean,default_fault,fast_clean,fast_fault;
 reply_clock_filter_legacy #(.ACTIVE_PIPELINE(1)) legacy(clk,reset_n,raw,active,legacy_clean,legacy_fault);
 reply_clock_filter #(.ACTIVE_PIPELINE(1)) unchanged(clk,reset_n,raw,active,default_clean,default_fault);
 reply_clock_filter #(.ACTIVE_PIPELINE(1),.FAST_FILTER_SYNC(1)) fast(clk,reset_n,raw,active,fast_clean,fast_fault);
 integer slow_rises=0,fast_rises=0,n,accumulator=0,divider,period_now,high_now,slow_before,fast_before;
 time raw_time[0:199],slow_time[0:199],fast_time[0:199];
 time minimum_fast=999999,maximum_fast=0,last_fast=0,fast_high=0;
 reg measuring=0;
 always @(posedge clk) begin
  #1;if(default_clean!==legacy_clean || default_fault!==legacy_fault)
    $fatal(1,"FAST_FILTER_SYNC default0 changed legacy waveform");
 end
 always @(posedge default_clean) begin
  if(measuring && slow_rises<200)slow_time[slow_rises]=$time;
  slow_rises=slow_rises+1;
 end
 always @(posedge fast_clean) begin
  if(last_fast && $time-last_fast<23150)$fatal(1,"fast cooldown changed");
  if(measuring && fast_rises<200)fast_time[fast_rises]=$time;
  last_fast=$time;fast_high=$time;fast_rises=fast_rises+1;
 end
 always @(negedge fast_clean)if(reset_n && fast_high && $time-fast_high!=9260)
  $fatal(1,"fast HIGH no longer exactly two sample ticks");
 task ticks;input integer count;begin repeat(count)@(negedge clk);end endtask
 initial begin
  ticks(3);reset_n=1;active=1;ticks(8);#PHASE_PS;measuring=1;
  for(n=0;n<200;n=n+1)begin
   accumulator=accumulator+DIV_NUMERATOR;divider=DIV_INTEGER;
   if(accumulator>=DIV_DENOMINATOR)begin accumulator=accumulator-DIV_DENOMINATOR;divider=divider+1;end
   period_now=6250*divider;high_now=6250*(divider/2);
   raw_time[n]=$time;raw=1;#(high_now);raw=0;#(period_now-high_now);
  end
  ticks(12);measuring=0;
  if(slow_rises!=200 || fast_rises!=200 || default_fault || fast_fault)
   $fatal(1,"regular edge count/fault changed slow%0d fast%0d",slow_rises,fast_rises);
  for(n=0;n<200;n=n+1)begin
   if(slow_time[n]-fast_time[n]!=4630)$fatal(1,"not exactly one tick faster edge%0d",n);
   if(fast_time[n]-raw_time[n]<9260 || fast_time[n]-raw_time[n]>13890)
    $fatal(1,"fast latency outside two-to-three tick window");
   if(fast_time[n]-raw_time[n]<minimum_fast)minimum_fast=fast_time[n]-raw_time[n];
   if(fast_time[n]-raw_time[n]>maximum_fast)maximum_fast=fast_time[n]-raw_time[n];
  end
  // Deliberately document the changed filter policy: one sampled HIGH passes
  // fast mode, but the exact legacy/default waveform rejects it.
  slow_before=slow_rises;fast_before=fast_rises;
  @(negedge clk);raw=1;ticks(1);raw=0;ticks(12);
  if(slow_rises!=slow_before || fast_rises!=fast_before+1 || default_fault || fast_fault)
   $fatal(1,"one-sample excursion policy unexpected");
  // Two such events too close together must still fault closed in fast mode.
  @(negedge clk);raw=1;ticks(1);raw=0;ticks(1);raw=1;ticks(1);raw=0;ticks(12);
  if(!fast_fault)$fatal(1,"fast close-spacing fault lost");
  reset_n=0;#1;
  if(default_clean || default_fault || fast_clean || fast_fault)$fatal(1,"stopped-clock async reset failed");
  last_fast=0;fast_high=0;active=0;ticks(3);reset_n=1;ticks(8);
  // Inactive request clocks retain pass-through and do not latch a fault.
  slow_before=slow_rises;fast_before=fast_rises;
  for(n=0;n<8;n=n+1)begin raw=1;ticks(8);raw=0;ticks(8);end
  if(slow_rises-slow_before!=8 || fast_rises-fast_before!=8 || default_fault || fast_fault)
   $fatal(1,"inactive request clocks changed");
  $display("FAST_SYNC,%0d,%0d,%0d,%0d,%0d,%0d",DIV_INTEGER,DIV_NUMERATOR,DIV_DENOMINATOR,PHASE_PS,minimum_fast,maximum_fast);
  $finish;
 end
 initial begin #1000000000;$fatal(1,"fast sync watchdog");end
endmodule
