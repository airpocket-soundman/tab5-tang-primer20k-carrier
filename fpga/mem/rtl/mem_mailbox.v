// Standalone diagnostic control. Bundles remain held until their toggle ack.
// No DDR-native signal crosses directly into the 27MHz LINK domain.
module mem_mailbox # (parameter DEADLINE=2700000)(
 input wire sys_clk,sys_reset_n,user_clk,user_reset_n,
 input wire command_start,input wire[7:0] opcode,a,b,
 output reg command_done,output reg[7:0] status,output reg[15:0] result,
 output reg recalibrate,
 input wire calibrated,busy,done,faulted,input wire[7:0] error_code,
 input wire[2:0] phase,input wire[31:0] verified_beats,error_beats,first_bad_byte,accepted_job_id,
 input wire[127:0] first_expected,first_actual,input wire[63:0] elapsed_cycles,
 output reg bist_start,bist_cancel,
 output reg[31:0] job_base,job_count,job_seed,job_id,
 output wire user_abort
);
 reg[31:0] cfg_base,cfg_count,cfg_seed,next_job;
 reg[5:0] cfg_written;
 reg request_toggle,ack_toggle;
 reg[1:0] request_sync,ack_sync,cal_sync,busy_sync,fault_sync;
 reg[7:0] held_op;
 reg[31:0] held_base,held_count,held_seed,held_job;
 reg[511:0] user_snapshot,sys_snapshot;
 reg pending_user,pending_sys,settle;
 reg[31:0] deadline;
 reg snapshot_valid,snapshot_stale,mailbox_timeout;
 reg[15:0] generation;
 // A timed-out START must never become a delayed write when USER resumes.
 // Top asynchronously asserts USER logic reset, held until explicit recalibration.
 assign user_abort=mailbox_timeout;
 wire[63:0] cfg_end={32'b0,cfg_base}+({32'b0,cfg_count}<<4);
 wire range_ok=cfg_base[3:0]==0&&cfg_count!=0&&cfg_count<=8388608&&cfg_end<=134217728;
 wire[15:0] flags={8'b0,1'b0,(done&&!faulted&&error_beats==0&&job_base==0&&job_count==8388608),
                   1'b0,(error_beats!=0),faulted,done,busy,calibrated};
 wire[511:0] snapshot_bundle={16'h014d,16'd81,elapsed_cycles,first_actual,first_expected,
                             first_bad_byte,error_beats,verified_beats,accepted_job_id,
                             {5'b0,phase,error_code},flags};
 // USER half: first cycle accepts stable payload, following cycle acknowledges.
 always @(posedge user_clk or negedge user_reset_n)begin
 if(!user_reset_n)begin request_sync<=0;ack_toggle<=0;pending_user<=0;
 bist_start<=0;bist_cancel<=0;job_base<=0;job_count<=0;job_seed<=0;job_id<=0;user_snapshot<=0;end
 else begin
 request_sync<={request_sync[0],request_toggle};bist_start<=0;bist_cancel<=0;
 if(pending_user)begin pending_user<=0;ack_toggle<=request_sync[1];end
 else if(request_sync[1]!=ack_toggle)begin
 pending_user<=1;
 if(held_op==8'h57)begin job_base<=held_base;job_count<=held_count;
 job_seed<=held_seed;job_id<=held_job;bist_start<=1;end
 else if(held_op==8'h5a)bist_cancel<=1;
 else if(held_op==8'h58)user_snapshot<=snapshot_bundle;
 end
 end end
 always @(posedge sys_clk or negedge sys_reset_n)begin
 if(!sys_reset_n)begin
 cfg_base<=0;cfg_count<=0;cfg_seed<=0;cfg_written<=0;next_job<=1;
 request_toggle<=0;ack_sync<=0;cal_sync<=0;busy_sync<=0;fault_sync<=0;
 held_op<=0;held_base<=0;held_count<=0;held_seed<=0;held_job<=0;
 pending_sys<=0;settle<=0;deadline<=0;command_done<=0;status<=0;result<=0;
 recalibrate<=0;sys_snapshot<=0;snapshot_valid<=0;snapshot_stale<=1;
 mailbox_timeout<=0;generation<=0;
 end else begin
 command_done<=0;recalibrate<=0;
 ack_sync<={ack_sync[0],ack_toggle};cal_sync<={cal_sync[0],calibrated};
 busy_sync<={busy_sync[0],busy};fault_sync<={fault_sync[0],faulted};
 if(pending_sys)begin
 deadline<=deadline+1;
 if(ack_sync[1]==request_toggle)begin
 // One extra SYS cycle after synchronized ack allows held snapshot settling.
 if(!settle)settle<=1;
 else begin pending_sys<=0;settle<=0;command_done<=1;status<=0;
 if(held_op==8'h58)begin sys_snapshot<=user_snapshot;generation<=generation+1;
 result<=generation+1;snapshot_valid<=1;snapshot_stale<=0;end
 else if(held_op==8'h57)result<=held_job[15:0];else result<=0;
 end
 end else if(deadline>=DEADLINE-1)begin
 pending_sys<=0;command_done<=1;status<=4;result<=0;mailbox_timeout<=1;snapshot_stale<=1;
 end
 end
 if(command_start&&!pending_sys)begin
 command_done<=1;status<=0;result<=0;
 case(opcode)
 8'h50:if({b,a}!=0)status<=3;else result<=16'h014d;
 8'h51,8'h52,8'h53,8'h54,8'h55,8'h56:begin
 if(busy_sync[1]||mailbox_timeout)status<=5;
 else begin
 case(opcode)
 8'h51:cfg_base[15:0]<={b,a};8'h52:cfg_base[31:16]<={b,a};
 8'h53:cfg_count[15:0]<={b,a};8'h54:cfg_count[31:16]<={b,a};
 8'h55:cfg_seed[15:0]<={b,a};8'h56:cfg_seed[31:16]<={b,a};endcase
 cfg_written[opcode-8'h51]<=1;result<={b,a};end end
 8'h57,8'h58,8'h5a:begin
 if({b,a}!=0)status<=3;
 else if(mailbox_timeout)status<=5;
 else if(opcode==8'h57&&(!cal_sync[1]||busy_sync[1]||fault_sync[1]||cfg_written!=6'h3f))status<=5;
 else if(opcode==8'h57&&!range_ok)status<=3;
 else begin
 command_done<=0;pending_sys<=1;settle<=0;deadline<=0;
 held_op<=opcode;held_base<=cfg_base;held_count<=cfg_count;held_seed<=cfg_seed;held_job<=next_job;
 request_toggle<=~request_toggle;
 if(opcode==8'h57)begin next_job<=next_job+1;snapshot_stale<=1;end
 end end
 8'h59:if(b!=0||a>31)status<=3;else if(!snapshot_valid)status<=5;
 else result<=sys_snapshot[a*16+:16];
 // Recalibration resets BOTH mailbox halves through the top-level reset epoch.
 // SYS config/mailbox state resets with it; no request depends on USER clock.
 8'h5b:if({b,a}!=0)status<=3;else begin recalibrate<=1;snapshot_stale<=1;end
 8'h5c:if(b!=0)status<=3;else case(a)
 0:result<=16'h014d;1:result<=2048;2:result<=16'h0d0a;3:result<=16'h0310;
 4:result<=324;5:result<=81;6:result<={10'b0,mailbox_timeout,snapshot_stale,snapshot_valid,fault_sync[1],busy_sync[1],cal_sync[1]};
 7:result<=generation;default:status<=3;endcase
 default:status<=2;
 endcase
 end
 end end
endmodule
