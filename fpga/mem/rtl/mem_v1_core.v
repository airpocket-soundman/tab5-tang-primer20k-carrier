// MEMV1 core: everything of the MEM image except the rPLL, the DDR3 controller IP and the pins.
// Reuses mem_bist (BIST kept, reachable through the legacy ops 0x50..0x5c) and mem_mailbox unchanged, adds
// memv1_sys (LINK + control), memv1_bridge (CDC) and mem_adapter (USER). The native interface is shared:
// the adapter owns it while the bridge is active, otherwise the BIST (the SYS side never runs both).
module mem_v1_core #(
 parameter FAST_REPLY_ENABLE=0,
 parameter [15:0] RESET_HOLD_INIT=16'hffff,
 parameter [15:0] RECAL_HOLD=16'd27000,
 parameter [15:0] MEM_MHZ=16'd398,parameter [15:0] USER_MHZ=16'd100,
 parameter APP_ROW_PAD=1,parameter BIST_PIPELINE=4,
 parameter LINK_TIMEOUT=2700000,parameter DEADLINE=2700000,parameter ADAPTER_TIMEOUT=8100000,
 parameter ADAPTER_SETTLE=256,parameter BIST_SETTLE=256,
 parameter MAILBOX_DEADLINE=2700000,parameter CAL_GUARD=256,parameter HEARTBEAT_DEADLINE=27000
)(
 input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire[3:0] aux,
 inout wire[7:0] data,output wire ready,output wire[3:0] led,
 // IP side (provided by mem_v1_top or by the simulation model)
 input wire pll_lock,user_clk,ip_user_reset,calibrated,
 output wire controller_reset_n,
 output wire[2:0] cmd,output wire cmd_en,output wire[26:0] address,input wire cmd_ready,
 output wire[127:0] wr_data,output wire wr_en,wr_end,output wire[15:0] mask,input wire wr_ready,
 input wire[127:0] rd_data,input wire rd_valid,rd_end,
 input wire reply_sample_clk,reply_sample_reset_n
);
wire raw_reset_n=reset_n&&arm_sw;
reg[15:0] reset_hold=RESET_HOLD_INIT;reg[23:0] heartbeat=0;
reg[3:0] mailbox_epoch=15;
wire recalibrate;
always @(posedge sys_clk or negedge raw_reset_n)begin
if(!raw_reset_n)begin reset_hold<=RESET_HOLD_INIT;heartbeat<=0;mailbox_epoch<=15;end
else begin heartbeat<=heartbeat+1;
if(recalibrate)mailbox_epoch<=15;else if(mailbox_epoch!=0)mailbox_epoch<=mailbox_epoch-1;
if(recalibrate||!pll_lock)reset_hold<=RECAL_HOLD;
else if(reset_hold!=0)reset_hold<=reset_hold-1;end end
assign controller_reset_n=raw_reset_n&&pll_lock&&reset_hold==0;
wire user_abort;
wire user_async_reset_n=controller_reset_n&&!user_abort&&!ip_user_reset;
reg[2:0] user_reset_sync;
always @(posedge user_clk or negedge user_async_reset_n)begin
if(!user_async_reset_n)user_reset_sync<=0;else user_reset_sync<={user_reset_sync[1:0],1'b1};end
wire user_reset_n=user_reset_sync[2];
// ---- SYS side ----
wire command_start,command_done;wire[7:0] op,a,b,status,out;wire[15:0] result;wire oe;
assign data=oe?out:8'bz;
wire req_t,cancel_t,done_t;wire[1:0] h_op;wire[31:0] h_addr,h_arg,r_crc;wire[15:0] h_beats,r_beats;
wire[23:0] h_tag,r_tag;wire[3:0] r_status;
wire w_we;wire[7:0] w_addr,r_addr;wire[127:0] w_data,r_data;wire[15:0] generation;
wire bist_busy;
reg[7:0] uc=0;
always @(posedge user_clk) uc<=uc+1'b1;
wire[8:0] diag={uc[7],mailbox_epoch==0,user_abort,reset_hold==0,calibrated,user_reset_n,ip_user_reset,controller_reset_n,pll_lock};
wire reply_read_clk;
memv1_sys #(.FAST_REPLY_ENABLE(FAST_REPLY_ENABLE),.TIMEOUT(LINK_TIMEOUT),.DEADLINE(DEADLINE)) link(
 sys_clk,reset_n,arm_sw,bus_clk,dir,data,out,oe,ready,
 command_start,op,a,b,command_done,status,result,
 calibrated,user_reset_n,bist_busy,
 req_t,cancel_t,h_op,h_addr,h_beats,h_arg,h_tag,done_t,r_tag,r_status,r_crc,r_beats,
 w_we,w_addr,w_data,r_addr,r_data,generation,diag,reply_sample_clk,reply_sample_reset_n,reply_read_clk);
// ---- mailbox / BIST (unchanged blocks) ----
wire bist_start,bist_cancel,done,faulted;
wire[31:0] base,count,seed,job,verified,errors,first,accepted;
wire[7:0] error;wire[2:0] phase;wire[127:0] expected,actual;wire[63:0] cycles;
wire[175:0] native_debug;
mem_mailbox #(.DEADLINE(MAILBOX_DEADLINE),.CAL_GUARD_CYCLES(CAL_GUARD),.HEARTBEAT_DEADLINE(HEARTBEAT_DEADLINE),
 .MEM_MHZ(MEM_MHZ),.USER_MHZ(USER_MHZ)) control(sys_clk,raw_reset_n&&mailbox_epoch==0,user_clk,user_reset_n,
command_start,op,a,b,command_done,status,result,recalibrate,
calibrated,bist_busy,done,faulted,error,phase,verified,errors,first,accepted,expected,actual,cycles,
bist_start,bist_cancel,base,count,seed,job,user_abort,native_debug,256'b0);
wire[2:0] b_cmd;wire b_cmd_en,b_wr_en,b_wr_end;wire[26:0] b_addr;wire[127:0] b_wr_data;wire[15:0] b_mask;
mem_bist #(.APP_ROW_PAD(APP_ROW_PAD),.PIPELINE(BIST_PIPELINE),.CALIBRATION_SETTLE_CYCLES(BIST_SETTLE)) engine(
user_clk,user_reset_n,calibrated,bist_start,bist_cancel,base,count,seed,job,
bist_busy,done,faulted,error,phase,verified,errors,first,accepted,expected,actual,cycles,
b_cmd,b_cmd_en,b_addr,cmd_ready,b_wr_data,b_wr_en,b_wr_end,b_mask,wr_ready,rd_data,rd_valid,rd_end,native_debug);
// ---- USER side: bridge + adapter + staging RAMs ----
wire bridge_active,a_cmd_valid,a_cmd_ready,a_cancel,a_rsp_valid,a_busy;
wire[1:0] a_op;wire[31:0] a_addr,a_arg,a_rsp_crc;wire[15:0] a_beats,a_rsp_beats;wire[23:0] a_tag,a_rsp_tag;wire[3:0] a_rsp_status;
wire[7:0] s_raddr,s_waddr;wire[127:0] s_rdata,s_wdata;wire s_we;
wire[2:0] a_cmd;wire a_cmd_en,a_wr_en,a_wr_end;wire[26:0] a_app_addr;wire[127:0] a_wr_data;wire[15:0] a_mask;
memv1_bridge bridge(user_clk,user_reset_n,req_t,cancel_t,h_op,h_addr,h_beats,h_arg,h_tag,done_t,
 r_tag,r_status,r_crc,r_beats,bridge_active,a_cmd_valid,a_cmd_ready,a_op,a_addr,a_beats,a_arg,a_tag,a_cancel,
 a_rsp_valid,a_rsp_tag,a_rsp_status,a_rsp_crc,a_rsp_beats);
mem_adapter #(.APP_ROW_PAD(APP_ROW_PAD),.TIMEOUT_CYCLES(ADAPTER_TIMEOUT),.SETTLE_CYCLES(ADAPTER_SETTLE)) adapter(
 user_clk,user_reset_n,calibrated,a_cmd_valid,a_cmd_ready,a_op,a_addr,a_beats,a_arg,a_tag,a_cancel,
 a_rsp_valid,a_rsp_tag,a_rsp_status,a_rsp_crc,a_rsp_beats,a_busy,
 s_raddr,s_rdata,s_we,s_waddr,s_wdata,
 a_cmd,a_cmd_en,a_app_addr,cmd_ready,a_wr_data,a_wr_en,a_wr_end,a_mask,wr_ready,rd_data,rd_valid,rd_end);
// write staging: SYS writes, USER reads. read buffer: USER writes, SYS reads.
memv1_dpram #(.AW(8),.DW(128)) write_stage(sys_clk,w_we,w_addr,w_data,user_clk,s_raddr,s_rdata);
memv1_dpram #(.AW(8),.DW(128)) read_buffer(user_clk,s_we,s_waddr,s_wdata,reply_read_clk,r_addr,r_data);
// ---- native interface sharing ----
assign cmd=bridge_active?a_cmd:b_cmd;
assign address=bridge_active?a_app_addr:b_addr;
assign wr_data=bridge_active?a_wr_data:b_wr_data;
assign mask=bridge_active?a_mask:b_mask;
assign cmd_en=bridge_active?a_cmd_en:b_cmd_en;
assign wr_en=bridge_active?a_wr_en:b_wr_en;
assign wr_end=bridge_active?a_wr_end:b_wr_end;
assign led=~{heartbeat[23],ready,calibrated,arm_sw};
endmodule
