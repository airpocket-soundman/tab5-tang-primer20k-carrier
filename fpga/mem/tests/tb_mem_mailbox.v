`timescale 1ns/1ps
module tb_mem_mailbox;
reg sys=0,user=0,run_user=1,run_sys=1;always #18.5185 if(run_sys)sys=~sys;always #6.17284 if(run_user)user=~user;
reg reset=0,cs=0;reg[7:0] op=0,a=0,b=0;wire cd;wire[7:0] status;wire[15:0] result;wire recal;
reg force_user_reset=0;
reg cal=1,busy=0,done=0,fault=0;reg[7:0] error=0;reg[2:0] phase=0;
reg[31:0] verified=32'h12345678,errors=32'h87654321,first=32'h1234560,accepted=32'hbeef1234;
reg[127:0] expected=128'h0123456789abcdef1122334455667788,actual=128'h99999999888888887777777766666666;
reg[63:0] elapsed=64'hfedcba9876543210;
wire bs,bc;wire[31:0] base,count,seed,job;
wire abort_user;
mem_mailbox #(.DEADLINE(40)) dut(sys,reset,user,reset&&!abort_user&&!force_user_reset,cs,op,a,b,cd,status,result,recal,
cal,busy,done,fault,error,phase,verified,errors,first,accepted,expected,actual,elapsed,bs,bc,base,count,seed,job,abort_user);
integer starts=0,cancels=0,checks=0,saved_starts=0;
realtime request_time=0,snapshot_time=0;
reg[511:0] previous_bundle=0;reg[15:0] previous_generation=0;
always @(posedge sys)begin
 if(cs&&op==8'h57)request_time=$realtime;
 #0.1;
 if(dut.generation!=previous_generation&&dut.generation!=0)begin
 if($realtime-snapshot_time<123.45)$fatal(1,"snapshot ack+settle bound");end
 previous_generation=dut.generation;
end
always @(posedge user)begin
 #0.1;
 if(bs&&$realtime-request_time<24.68)$fatal(1,"request bundle settle bound");
 if(dut.user_snapshot!=previous_bundle)begin snapshot_time=$realtime;previous_bundle=dut.user_snapshot;end
end
always @(posedge user)begin if(bs)starts=starts+1;if(bc)cancels=cancels+1;end
task command;input[7:0] opcode;input[15:0] arg;input[7:0] want;integer n;
begin @(negedge sys);op=opcode;a=arg[7:0];b=arg[15:8];cs=1;
@(negedge sys);cs=0;n=0;
while(!cd&&n<100)begin @(negedge sys);n=n+1;end
if(!cd||status!=want)$fatal(1,"command %x expected %d got %d",opcode,want,status);
checks=checks+1;end endtask
task new_job;begin
reset=0;run_user=1;force_user_reset=0;cal=1;busy=0;repeat(4)@(negedge sys);reset=1;
command(8'h51,0,0);command(8'h52,0,0);command(8'h53,1,0);command(8'h54,0,0);
command(8'h55,0,0);command(8'h56,0,0);repeat(260)@(negedge sys);command(8'h57,0,0);
end endtask
initial begin
repeat(4)@(negedge sys);reset=1;repeat(5)@(negedge sys);
command(8'h50,0,0);if(result!=16'h014d)$fatal(1,"cap");
command(8'h57,0,5); // Configuration completeness is mandatory.
command(8'h51,16'h1ff0,0);command(8'h52,0,0);
command(8'h53,33,0);command(8'h54,0,0);
command(8'h55,16'habcd,0);command(8'h56,16'h1234,0);
command(8'h57,0,5); // Complete config still cannot bypass calibration settle guard.
repeat(260)@(negedge sys);
command(8'h57,0,0);if(result!=1||base!=32'h1ff0||count!=33||seed!=32'h1234abcd||job!=1||starts!=1)$fatal(1,"held job payload");
busy=1;repeat(4)@(negedge sys);command(8'h51,0,5);busy=0;
command(8'h58,0,0);if(result!=1)$fatal(1,"snapshot generation");
// The input bundle changes immediately, while the accepted SYS bank stays fixed.
verified=0;expected=0;elapsed=0;
command(8'h59,4,0);if(result!=16'h5678)$fatal(1,"torn verified low");
command(8'h59,5,0);if(result!=16'h1234)$fatal(1,"torn verified high");
command(8'h59,10,0);if(result!=16'h7788)$fatal(1,"expected endian");
command(8'h59,26,0);if(result!=16'h3210)$fatal(1,"cycle endian");
command(8'h59,31,0);if(result!=16'h014d)$fatal(1,"snapshot signature");
command(8'h59,32,3);command(8'h59,16'h0100,3);
command(8'h5a,0,0);if(cancels!=1)$fatal(1,"cancel crossing");
// Stopped USER clock cannot hang SYS, replace a previous bank, or fake freshness.
@(negedge user);run_user=0;
command(8'h58,0,4);
command(8'h5c,6,0);if((result&16'h0038)!=16'h0038)$fatal(1,"stale timeout flags");
command(8'h59,4,0);if(result!=16'h5678)$fatal(1,"timeout corrupted old bank");
command(8'h57,0,5);
command(8'h5b,0,0);if(!recal)$fatal(1,"recal cannot depend on USER clock");
reset=0;run_user=1;repeat(4)@(negedge sys);reset=1;repeat(4)@(negedge sys);
command(8'h59,0,5);command(8'h57,0,5);
command(8'h51,0,0);command(8'h52,0,0);command(8'h53,1,0);command(8'h54,0,0);
command(8'h55,0,0);command(8'h56,0,0);
repeat(260)@(negedge sys);
@(negedge user);run_user=0;command(8'h57,0,4);
if(!abort_user)$fatal(1,"timed-out START did not inhibit USER");
run_user=1;repeat(8)@(negedge sys);if(starts!=1||bs)$fatal(1,"late START after deadline");
new_job;command(8'h58,0,0);cal=0;repeat(5)@(negedge sys);cal=1;
command(8'h5c,6,0);if((result&16'h0050)!=16'h0050||!abort_user)$fatal(1,"calibration loss not sticky/stale");
repeat(270)@(negedge sys);command(8'h57,0,5);command(8'h59,31,0);
if(result!=16'h014d)$fatal(1,"loss destroyed old held bank");
new_job;
// Even a reset pulse shorter than SYS period must not be missed.
saved_starts=starts;
@(negedge sys);#3;force_user_reset=1;#2;force_user_reset=0;repeat(5)@(negedge sys);
if(starts!=saved_starts)$fatal(1,"USER reset replayed an already accepted START");
command(8'h5c,6,0);if(!result[6]||!abort_user)$fatal(1,"short USER reset lost");command(8'h57,0,5);
// Healthy START must execute once with either request-toggle polarity.
new_job;saved_starts=starts;command(8'h57,0,0);
if(result!=2||job!=2||starts!=saved_starts+1)$fatal(1,"toggle0 START not exactly once");
saved_starts=starts;@(negedge sys);#3;force_user_reset=1;#2;force_user_reset=0;
repeat(8)@(negedge sys);if(starts!=saved_starts)$fatal(1,"toggle0 replayed START");
command(8'h57,0,5);
// A used USER epoch cannot reopen even before SYS has observed the reset.
new_job;saved_starts=starts;@(negedge sys);run_sys=0;
#3;force_user_reset=1;#2;force_user_reset=0;repeat(128)@(negedge user);
if(starts!=saved_starts||dut.user_mailbox_ready)$fatal(1,"quarantine rearmed while SYS paused");
run_sys=1;repeat(8)@(negedge sys);command(8'h57,0,5);
new_job;@(negedge user);run_user=0;
// The second request toggle is0; resetting USER ack0 must not fake its completion.
fork
 begin command(8'h58,0,5);end
 begin wait(dut.pending_sys);#2;force_user_reset=1;#2;force_user_reset=0;end
join
if(!abort_user)$fatal(1,"reset-to-zero ACK alias not inhibited");run_user=1;
// A pre-first-job clock halt expires readiness without a spurious old-job fault.
reset=0;force_user_reset=0;repeat(4)@(negedge sys);reset=1;
command(8'h51,0,0);command(8'h52,0,0);command(8'h53,1,0);command(8'h54,0,0);
command(8'h55,0,0);command(8'h56,0,0);repeat(270)@(negedge sys);
saved_starts=starts;@(negedge user);run_user=0;repeat(27010)@(negedge sys);
command(8'h5c,6,0);if(result[9]||result[6]||!result[7])$fatal(1,"boot clock-halt readiness/fault state");
command(8'h57,0,5);run_user=1;repeat(300)@(negedge sys);
if(starts!=saved_starts)$fatal(1,"clock resume automatically launched first job");
command(8'h57,0,0);if(starts!=saved_starts+1)$fatal(1,"fresh explicit first START rejected");
$display("PASS mem_mailbox %0d commands: CDC held payload, coherent snapshot, stopped-clock deadline, reset",checks);$finish;
end
endmodule
