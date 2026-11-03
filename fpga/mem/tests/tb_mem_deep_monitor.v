`timescale 1ns/1ps
module tb_mem_deep_monitor;
reg clk=0;always #5 clk=~clk;
reg reset=0,start=0,busy=0;reg[175:0] native=0;reg[63:0] taps=0;wire[255:0] out;
mem_deep_monitor d(clk,reset,start,busy,native,taps,out);
task tick;begin @(posedge clk);#1;end endtask
initial begin
 tick;reset=1;start=1;taps[5:3]=6;taps[20:16]=30;tick;start=0;busy=1;
 taps[5:3]=7;taps[20:16]=31;taps[11]=1;tick;
 taps[5:3]=0;taps[20:16]=0;tick;
 taps[5:3]=1;taps[20:16]=1;taps[11]=0;taps[63:26]=38'h2abcde1234;tick;
 busy=0;native[11]=1;tick;
 if(out[95:64]!=3||out[127:96]!=3||out[159:128]!=2||!out[160])$fatal(1,"counter wrap or freeze");
 if(out[5:3]!=1||out[20:16]!=1||out[63:26]!=38'h2abcde1234)$fatal(1,"fault edge observation");
 taps=64'hdeadbeef;native=0;repeat(5)tick;
 if(out[5:3]!=1||out[95:64]!=3)$fatal(1,"cleanup changed first fault");
 start=1;tick;start=0;if(out[160]||out[95:64]!=0)$fatal(1,"new job did not clear");
 reset=0;tick;if(out[160:64]!=0)$fatal(1,"reset");
 $display("PASS deep monitor: modulo pointers, event counts, first-fault freeze, cleanup, new job/reset");$finish;
end
endmodule

