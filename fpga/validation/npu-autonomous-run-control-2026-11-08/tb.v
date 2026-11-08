
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,arm=1,memory_ready=1,start=0,abort=0,clear=0;
reg[15:0]epoch=37;reg arb_active=0,arb_fault=0,mac_busy=0,mac_quarantined=0;
reg cpu_safe_to_release=1,cpu_fault=0,cpu_trap=0;reg[3:0]cpu_error_code=0;
reg[31:0]cpu_node=0,cpu_stage=0,cpu_app_error=0,cpu_finish=0;
wire run_enable,abort_level,start_ready,done,error,aborted,quarantined;wire[15:0]status;
reg[5:0]monitor_index=0;wire[31:0]monitor_data;integer checks=0,cases=0;reg[31:0]saved_cycles;
npu_local_run_control dut(.*);
task tick;begin @(posedge clk);#1;end endtask
task check;input value;input[1023:0]name;begin checks=checks+1;if(value!==1'b1)$fatal(1,"check %0d: %0s",checks,name);end endtask
task monitor;input[5:0]sel;input[31:0]expected;begin monitor_index=sel;#1;check(monitor_data===expected,"monitor latest exact value");end endtask
task launch;begin @(negedge clk);start=1;#1;check(start_ready,"clean START ready");tick();check(run_enable&&!done&&!error,"START holds RUN lease");@(negedge clk);start=0;end endtask
task cleanup;begin @(negedge clk);start=0;abort=0;arb_active=0;arb_fault=0;mac_busy=0;mac_quarantined=0;cpu_fault=0;cpu_trap=0;cpu_error_code=0;cpu_finish=0;cpu_app_error=0;cpu_safe_to_release=1;memory_ready=1;clear=1;tick();@(negedge clk);clear=0;tick();check(start_ready&&!done&&!error&&!aborted&&!abort_level,"idle CLEAR retires sticky flags");end endtask
initial begin
 tick();tick();@(negedge clk);reset_n=1;tick();check(start_ready,"initial ready");cases=cases+1;
 @(negedge clk);memory_ready=0;#1;check(!start_ready,"calibration gates START");memory_ready=1;cpu_safe_to_release=0;#1;check(!start_ready,"CPU drain gates START");cpu_safe_to_release=1;arb_active=1;#1;check(!start_ready,"arbiter gates START");arb_active=0;mac_busy=1;#1;check(!start_ready,"MAC gates START");mac_busy=0;cases=cases+1;
 @(negedge clk);start=1;abort=1;#1;check(!start_ready,"START plus ABORT rejected");tick();check(!run_enable&&!done,"ABORT cannot launch idle RUN");@(negedge clk);start=0;abort=0;cases=cases+1;
 cpu_fault=1;#1;check(!start_ready,"CPU fault gates START");cpu_fault=0;cpu_trap=1;#1;check(!start_ready,"CPU trap gates START");cpu_trap=0;cases=cases+1;
 launch();monitor(6,37);monitor(7,1);@(negedge clk);cpu_node=123;cpu_stage=3;tick();monitor(1,123);monitor(2,3);monitor_index=8;#1;check(monitor_data>0,"cycles advance while RUN");saved_cycles=monitor_data;cases=cases+1;
 @(negedge clk);clear=1;start=1;tick();check(run_enable&&!start_ready,"CLEAR/reSTART ignored during RUN");monitor(7,1);@(negedge clk);clear=0;start=0;cases=cases+1;
 @(negedge clk);cpu_finish=1;cpu_safe_to_release=0;arb_active=1;mac_busy=1;tick();check(run_enable&&!done,"FINISH waits CPU/DDR/MAC drain");@(negedge clk);cpu_safe_to_release=1;mac_busy=0;tick();check(run_enable&&!done,"FINISH retains arbiter owner");@(negedge clk);arb_active=0;tick();check(!run_enable&&done&&!error&&!start_ready,"success only after full drain");monitor(4,1);monitor_index=8;#1;check(monitor_data>saved_cycles,"cycles cover drain");saved_cycles=monitor_data;tick();check(monitor_data==saved_cycles,"cycles stop after lease release");cases=cases+1;cleanup();
 launch();@(negedge clk);abort=1;cpu_finish=1;tick();check(!done&&error&&aborted&&!run_enable,"same-edge ABORT dominates successful FINISH");cases=cases+1;cleanup();
 launch();@(negedge clk);epoch=38;cpu_finish=1;tick();check(!done&&error&&!run_enable,"same-edge epoch change dominates FINISH");monitor(6,37);cases=cases+1;cleanup();
 launch();@(negedge clk);memory_ready=0;cpu_finish=1;cpu_safe_to_release=0;tick();check(run_enable&&error&&!done&&abort_level,"calibration loss retains unsafe lease");@(negedge clk);clear=1;tick();check(run_enable&&error,"CLEAR cannot release unsafe lease");@(negedge clk);clear=0;memory_ready=1;cpu_safe_to_release=1;tick();check(!run_enable&&error&&!done,"recovered drain cannot publish stale FINISH");cases=cases+1;cleanup();
 launch();@(negedge clk);cpu_trap=1;cpu_error_code=15;cpu_safe_to_release=0;tick();check(run_enable&&error&&status[5]&&!done,"trap sticky until CPU drain");monitor(5,15);@(negedge clk);cpu_trap=0;cpu_safe_to_release=1;tick();check(!run_enable&&error&&status[5],"trap remains sticky after drain");cases=cases+1;cleanup();
 launch();@(negedge clk);abort=1;arb_active=1;cpu_safe_to_release=0;tick();check(run_enable&&error&&aborted,"abort holds outstanding transaction");@(negedge clk);abort=0;cpu_safe_to_release=1;tick();check(run_enable&&!done,"CPU alone cannot retire DDR owner");@(negedge clk);arb_active=0;tick();check(!run_enable&&error&&!done,"abort drain release never success");cases=cases+1;cleanup();
 launch();@(negedge clk);arb_fault=1;mac_quarantined=1;cpu_safe_to_release=0;tick();check(run_enable&&quarantined&&error&&!done,"quarantine retains unsafe RUN");@(negedge clk);clear=1;tick();check(run_enable&&quarantined,"CLEAR cannot retire quarantine owner");@(negedge clk);arm=0;tick();check(!run_enable&&!done&&!error,"coordinated ARM reset clears local lease");cases=cases+1;
 $display("PASS run-control cases%0d checks%0d",cases,checks);$finish;
end
initial begin #100000;$fatal(1,"test deadline");end
endmodule
