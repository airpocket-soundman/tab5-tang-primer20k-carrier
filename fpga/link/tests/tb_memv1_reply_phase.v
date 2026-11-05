`timescale 1ps/1ps
module tb_memv1_reply_phase;
parameter TICKS=3;
reg clock=0,run_clock=1,reset_n=0,clean=0;
always #2315 if(run_clock)clock=~clock;
wire delayed;
generate if(TICKS==0)assign delayed=clean;
else reply_phase_delay #(.TICKS(TICKS)) dut(clock,reset_n,clean,delayed);
endgenerate
integer inputs=0,outputs=0,i;time last_input=0,last_output=0;
always @(posedge clean)begin inputs=inputs+1;last_input=$time;end
always @(posedge delayed)begin
 outputs=outputs+1;last_output=$time;
 #1;if($time-last_input!=TICKS*4630+1)$fatal(1,"phase latency %0d ticks%0d",$time-last_input,TICKS);
end
always @(negedge delayed)if(reset_n&&last_output&&$time-last_output!=9260)$fatal(1,"phase changed pulse width");
initial begin
 #10000;reset_n=1;
 for(i=0;i<200;i=i+1)begin
  @(posedge clock);clean<=1;
  repeat(2)@(posedge clock);clean<=0;
  repeat(8)@(posedge clock);
 end
 #30000;if(outputs!=200||inputs!=200)$fatal(1,"phase lost/repeated edge");
 // Reset with the sampler clock stopped, while a delayed pulse is HIGH.
 @(posedge clock);clean<=1;wait(delayed);#1;run_clock=0;reset_n=0;clean=0;
 #1;if(delayed)$fatal(1,"phase reset did not kill stopped-clock output");
 reset_n=1;#20000;if(delayed)$fatal(1,"phase reset resurrected stale pulse");
 run_clock=1;#30000;if(delayed)$fatal(1,"phase resume resurrected stale pulse");
 $display("PASS reply phase ticks=%0d: 200 exact-delay pulses, width preserved, stopped-clock reset and no stale resume",TICKS);$finish;
end
initial begin #20000000;$fatal(1,"deadline");end
endmodule
