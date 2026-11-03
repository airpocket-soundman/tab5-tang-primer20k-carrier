`timescale 1ns/1ps
module tb_mem_heartbeat_abort;
reg sys=0,user=0,run_user=1,reset=0,force_user_reset=0;always #18.5185 sys=~sys;always #6.17284 if(run_user)user=~user;
wire[175:0] native_debug;wire abort_user;wire asynchronous_user_reset=reset&&!abort_user&&!force_user_reset;
reg[2:0] release_user=0;
always @(posedge user or negedge asynchronous_user_reset)begin
if(!asynchronous_user_reset)release_user<=0;else release_user<={release_user[1:0],1'b1};end
wire user_reset=release_user[2];
reg cs=0;reg[7:0] op=0,a=0,b=0;wire cd;wire[7:0] status;wire[15:0] result;wire recal;
wire busy,done,fault,bs,bc;wire[7:0] error;wire[2:0] phase;
wire[31:0] base,count,seed,job,verified,errors,first,accepted;
wire[127:0] expected,actual,wd;wire[63:0] cycles;wire[2:0] cmd;wire ce,we,wend;wire[26:0] addr;wire[15:0] mask;
reg stall=1,rv=0;reg[127:0] memory=0,rd=0;reg pending=0;integer delay_read=0,i,checks=0;
integer native_commands=0,native_data=0,saved_commands=0,saved_data=0;
mem_mailbox #(.DEADLINE(200)) control(sys,reset,user,user_reset,cs,op,a,b,cd,status,result,recal,
1'b1,busy,done,fault,error,phase,verified,errors,first,accepted,expected,actual,cycles,bs,bc,base,count,seed,job,abort_user,native_debug,256'b0);
mem_bist engine(user,user_reset,1'b1,bs,bc,base,count,seed,job,busy,done,fault,error,phase,
verified,errors,first,accepted,expected,actual,cycles,cmd,ce,addr,!stall,wd,we,wend,mask,!stall,rd,rv,1'b1,native_debug);
always @(posedge user)begin
if((ce&&!stall)||(we&&!stall))begin
 if(!user_reset||!control.user_mailbox_ready||abort_user)$fatal(1,"native acceptance during reset/quarantine/loss");
end
if(ce&&!stall)native_commands=native_commands+1;
if(we&&!stall)native_data=native_data+1;
end
always @(posedge user or negedge user_reset)begin
if(!user_reset)begin rv<=0;pending<=0;delay_read<=0;memory<=0;rd<=0;end
else begin rv<=0;
if(we&&!stall)for(i=0;i<16;i=i+1)if(!mask[i])memory[i*8+:8]<=wd[i*8+:8];
if(ce&&!stall&&cmd==1)begin pending<=1;delay_read<=2;end
if(pending)begin if(delay_read==0)begin rv<=1;rd<=memory;pending<=0;end else delay_read<=delay_read-1;end
end end
task command;input[7:0] opcode;input[15:0] value;input[7:0] want;integer n;
begin @(negedge sys);op=opcode;a=value[7:0];b=value[15:8];cs=1;@(negedge sys);cs=0;n=0;
while(!cd&&n<300)begin @(negedge sys);n=n+1;end
if(!cd||status!=want)$fatal(1,"command%x status%0d expected%0d",opcode,status,want);checks=checks+1;end endtask
task configure;begin
command(8'h51,0,0);command(8'h52,0,0);command(8'h53,1,0);command(8'h54,0,0);
command(8'h55,16'h1234,0);command(8'h56,16'habcd,0);repeat(270)@(negedge sys);
end endtask
task fresh_epoch;begin
reset=0;#1;if(control.user_epoch_used)$fatal(1,"explicit epoch reset did not clear retained marker");
run_user=1;force_user_reset=0;repeat(4)@(negedge sys);reset=1;configure;
end endtask
initial begin
repeat(4)@(negedge sys);reset=1;configure;
command(8'h57,0,0);command(8'h58,0,0);
if(!busy||!ce||!we)$fatal(1,"test did not hold native command and data valids");
@(negedge user);run_user=0;repeat(10)@(negedge sys);
if(!ce||!we)$fatal(1,"USER did not actually halt with valids held");
repeat(27010)@(negedge sys);
// No USER edge occurs after halt; SYS watchdog must asynchronously kill valids.
if(!abort_user||ce||we||busy)$fatal(1,"halted USER valids escaped async inhibit");
command(8'h5c,6,0);if((result&16'h1050)!=16'h1050||result[9])$fatal(1,"heartbeat loss/stale flags");
run_user=1;repeat(300)@(negedge sys);command(8'h57,0,5);
if(ce||we||busy)$fatal(1,"job resumed without recalibration");
command(8'h5b,0,0);if(!recal)$fatal(1,"explicit recalibrate request missing");
// Emulate top-level recalibration epoch reset; no automatic retry.
reset=0;repeat(4)@(negedge sys);reset=1;stall=0;configure;
command(8'h57,0,0);repeat(100)@(negedge sys);
if(!done||error||verified!=2)$fatal(1,"explicit recalibration did not rearm");
if(native_commands!=4||native_data!=2)$fatal(1,"normal job native acceptance count");
command(8'h58,0,0);command(8'h59,0,0);if((result&31)!=5)$fatal(1,"completed job snapshot not captured");
@(negedge user);run_user=0;repeat(27010)@(negedge sys);
command(8'h59,0,0);if((result&31)!=5)$fatal(1,"held DONE bank unexpectedly destroyed");
command(8'h5c,6,0);if(!result[6]||!result[4]||!result[12])$fatal(1,"old DONE misrepresented as current after halt");
command(8'h5b,0,0);fresh_epoch;
// Reset after dispatch but before BIST consumes its START pulse, toggle0.
command(8'h58,0,0);saved_commands=native_commands;saved_data=native_data;
fork
 begin command(8'h57,0,5);end
 begin wait(bs);#1;force_user_reset=1;#2;force_user_reset=0;end
join
repeat(128)@(negedge user);
if(native_commands!=saved_commands||native_data!=saved_data||ce||we||busy)$fatal(1,"pre-acceptance reset replay/native operation");
command(8'h5b,0,0);fresh_epoch;
// Reset just after BIST accepts START, before the first native beat, toggle1.
saved_commands=native_commands;saved_data=native_data;
fork
 begin command(8'h57,0,5);end
 begin wait(busy);#1;force_user_reset=1;#2;force_user_reset=0;end
join
repeat(128)@(negedge user);
if(native_commands!=saved_commands||native_data!=saved_data||ce||we||busy)$fatal(1,"post-acceptance reset replay/native operation");
$display("PASS mem_heartbeat_abort %0d commands: held native valids killed without USER edge, no auto-resume, explicit rearm, stale DONE",checks);$finish;
end
endmodule
