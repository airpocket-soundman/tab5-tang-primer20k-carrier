module mem_top(
input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire[3:0] aux,
inout wire[7:0] data,output wire ready,output wire[3:0] led,
output wire[12:0] ddr_addr,output wire[2:0] ddr_bank,
output wire ddr_cs,ddr_ras,ddr_cas,ddr_we,ddr_ck,ddr_ck_n,ddr_cke,ddr_odt,ddr_reset_n,
output wire[1:0] ddr_dm,inout wire[15:0] ddr_dq,inout wire[1:0] ddr_dqs,ddr_dqs_n
);
// BW_ENABLE=0 (default): BIST-only image, logic identical to the version without the bandwidth engine.
// BW_ENABLE=1: adds mem_bw_port (LINK opcodes 0x60..0x6F; MEM diagnostic ABI 0x50..0x5C unchanged) sharing the native bus.
parameter BW_ENABLE=0;
parameter BW_EN_PIPE=0; // mem_bw native-enable structure (0 original, 1 registered enables with identical cycles, 2 stale-block like BIST PIPELINE=4)
parameter BW_SHARED_GATE=0; // 1 (only with `define BW_GATES, mem_bist PIPELINE=4): IP-facing enables from shared registered gates; 0: OR of the engines' enables
parameter BW_ROW_PAD=0; // APP_ROW_PAD of the bandwidth engine (1 for the 14-row-bit Sipeed sample IP)
wire memory_clk,pll_lock,user_clk,calibrated,ip_user_reset;
mem_pll frequency(sys_clk,!reset_n,memory_clk,pll_lock);
wire raw_reset_n=reset_n&&arm_sw;
reg[15:0] reset_hold=16'hffff;reg[23:0] heartbeat=0;
reg[3:0] mailbox_epoch=15;
wire recalibrate;
always @(posedge sys_clk or negedge raw_reset_n)begin
if(!raw_reset_n)begin reset_hold<=16'hffff;heartbeat<=0;mailbox_epoch<=15;end
else begin heartbeat<=heartbeat+1;
if(recalibrate)mailbox_epoch<=15;else if(mailbox_epoch!=0)mailbox_epoch<=mailbox_epoch-1;
if(recalibrate||!pll_lock)reset_hold<=16'd27000;
else if(reset_hold!=0)reset_hold<=reset_hold-1;end end
wire controller_reset_n=raw_reset_n&&pll_lock&&reset_hold==0;
wire user_abort;
wire user_async_reset_n=controller_reset_n&&!user_abort&&!ip_user_reset;
reg[2:0] user_reset_sync;
always @(posedge user_clk or negedge user_async_reset_n)begin
if(!user_async_reset_n)user_reset_sync<=0;else user_reset_sync<={user_reset_sync[1:0],1'b1};end
wire user_reset_n=user_reset_sync[2];
wire command_start,command_done;wire[7:0] op,a,b,status,out;wire[15:0] result;wire oe;
wire mb_start,mb_done,mb_busy;wire[7:0] mb_status;wire[15:0] mb_result;
wire[2:0] b_cmd;wire b_cmd_en,b_wr_en,b_wr_end;wire[26:0] b_address;wire[127:0] b_wr_data;wire[15:0] b_mask;
wire[5:0] burst_number; // app_burst_number of the old (sample) IP; 0 outside bandwidth jobs
assign data=oe?out:8'bz;
mem_link #(.BW_ENABLE(BW_ENABLE)) link(sys_clk,reset_n,arm_sw,bus_clk,dir,data,out,oe,ready,
command_start,op,a,b,command_done,status,result);
wire bist_start,bist_cancel,busy,done,faulted;
`ifdef BW_GATES
wire bist_cancel_pre,b_gwc,b_grc,b_gwd;
`endif
wire[31:0] base,count,seed,job,verified,errors,first,accepted;
wire[7:0] error;wire[2:0] phase;wire[127:0] expected,actual;wire[63:0] cycles;
wire[175:0] native_debug;
wire[63:0] deep_taps;wire[255:0] deep_debug;
mem_deep_monitor observer(user_clk,user_reset_n,bist_start,busy,native_debug,deep_taps,deep_debug);
// SYS observations remain available even if PLL/user clock disappears.
mem_mailbox control(sys_clk,raw_reset_n&&mailbox_epoch==0,user_clk,user_reset_n,
mb_start,op,a,b,mb_done,mb_status,mb_result,recalibrate,
calibrated,mb_busy,done,faulted,error,phase,verified,errors,first,accepted,expected,actual,cycles,
bist_start,bist_cancel,base,count,seed,job,user_abort,native_debug,deep_debug
`ifdef BW_GATES
,bist_cancel_pre
`endif
);
wire[2:0] cmd;wire cmd_en,cmd_ready,wr_en,wr_end,wr_ready,rd_valid,rd_end;
wire[26:0] address;wire[127:0] wr_data,rd_data;wire[15:0] mask;
mem_bist engine(user_clk,user_reset_n,calibrated,bist_start,bist_cancel,base,count,seed,job,
busy,done,faulted,error,phase,verified,errors,first,accepted,expected,actual,cycles,
b_cmd,b_cmd_en,b_address,cmd_ready,b_wr_data,b_wr_en,b_wr_end,b_mask,wr_ready,rd_data,rd_valid,rd_end,native_debug
`ifdef BW_GATES
,b_gwc,b_grc,b_gwd
`endif
);
generate if(BW_ENABLE!=0) begin:bw
// Bandwidth jobs own the native bus while bw_busy; the BIST command/data enables are zero when it is idle, so they are OR-ed.
wire bw_op=op[6:4]==3'b110; // 0x60..0x6F
wire bw_start=command_start&&bw_op;wire bw_done,bw_busy;wire[7:0] bw_status;wire[15:0] bw_result;
reg route_bw;
always @(posedge sys_clk or negedge raw_reset_n)begin
if(!raw_reset_n)route_bw<=0;else if(command_start)route_bw<=bw_op;end
assign mb_start=command_start&&!bw_op;
assign command_done=mb_done||bw_done;
assign status=route_bw?bw_status:mb_status;
assign result=route_bw?bw_result:mb_result;
wire[2:0] w_cmd;wire w_cmd_en,w_wr_en,w_wr_end,w_gwc,w_grc,w_gwb,w_cpre;wire[26:0] w_address;wire[127:0] w_wr_data;wire[15:0] w_mask;wire[5:0] w_burst;
mem_bw_port #(.ROW_PAD(BW_ROW_PAD),.EN_PIPE(BW_EN_PIPE)) port(.sys_clk(sys_clk),.sys_reset_n(raw_reset_n&&mailbox_epoch==0),.user_clk(user_clk),.user_reset_n(user_reset_n),
.command_start(bw_start),.opcode(op),.a(a),.b(b),.command_done(bw_done),.status(bw_status),.result(bw_result),
.calibrated(calibrated),.bist_busy(busy),.bw_busy(bw_busy),
.app_cmd(w_cmd),.app_cmd_en(w_cmd_en),.app_addr(w_address),.app_burst_number(w_burst),
.app_write_data(w_wr_data),.app_write_en(w_wr_en),.app_write_end(w_wr_end),.app_write_mask(w_mask),
.app_cmd_ready(cmd_ready),.app_write_ready(wr_ready),.app_read_data(rd_data),.app_read_valid(rd_valid),.app_read_end(rd_end),
.gate_wc_d(w_gwc),.gate_rc_d(w_grc),.gate_wb_d(w_gwb),.cancel_pre(w_cpre));
assign cmd=bw_busy?w_cmd:b_cmd;assign address=bw_busy?w_address:b_address;
assign wr_data=bw_busy?w_wr_data:b_wr_data;assign mask=bw_busy?w_mask:b_mask;
`ifdef BW_GATES
if(BW_SHARED_GATE==0) begin:orgate
assign cmd_en=b_cmd_en||w_cmd_en;assign wr_en=b_wr_en||w_wr_en;assign wr_end=b_wr_end||w_wr_end;
end else begin:sharedgate
// Shared registered enable gates: the IP-facing enables are 4-input functions of the IP ready flags and registered gates (BIST and
// bandwidth engine never run together; the gates are the OR of the two next-cycle gate values with the next-cycle cancel folded in).
// They are equal to b_cmd_en||w_cmd_en / b_wr_en||w_wr_en (the engines' own accounting strobes), which tb_mem_bw_top asserts.
reg g_c,g_r,g_d,g_b;
always @(posedge user_clk or negedge user_reset_n) begin
if(!user_reset_n) begin g_c<=0;g_r<=0;g_d<=0;g_b<=0; end
else begin
g_c<=(b_gwc&&!bist_cancel_pre)||(w_gwc&&!w_cpre);
g_r<=(b_grc&&!bist_cancel_pre)||(w_grc&&!w_cpre);
g_d<=(b_gwd&&!bist_cancel_pre)||(w_gwc&&!w_cpre);
g_b<=w_gwb&&!w_cpre;
end end
assign cmd_en=cmd_ready&&(g_r||(g_c&&wr_ready));
assign wr_en=wr_ready&&(g_b||(g_d&&cmd_ready));
assign wr_end=wr_en;
end
`else
assign cmd_en=b_cmd_en||w_cmd_en;assign wr_en=b_wr_en||w_wr_en;assign wr_end=b_wr_end||w_wr_end;
`endif
assign burst_number=bw_busy?w_burst:6'd0;
assign mb_busy=busy||bw_busy;
end else begin:nobw
assign mb_start=command_start;assign command_done=mb_done;assign status=mb_status;assign result=mb_result;
assign cmd=b_cmd;assign cmd_en=b_cmd_en;assign address=b_address;assign wr_data=b_wr_data;
assign wr_en=b_wr_en;assign wr_end=b_wr_end;assign mask=b_mask;assign burst_number=6'd0;
assign mb_busy=busy;
end endgenerate
MemDDR3 controller(.deep_taps(deep_taps),.clk(sys_clk),.memory_clk(memory_clk),.pll_lock(pll_lock),.rst_n(controller_reset_n),
.cmd(cmd),.cmd_en(cmd_en),.addr(address),.cmd_ready(cmd_ready),
.wr_data(wr_data),.wr_data_en(wr_en),.wr_data_end(wr_end),.wr_data_mask(mask),.wr_data_rdy(wr_ready),
.rd_data(rd_data),.rd_data_valid(rd_valid),.rd_data_end(rd_end),.sr_req(1'b0),.ref_req(1'b0),.burst(1'b1),
.clk_out(user_clk),.ddr_rst(ip_user_reset),.init_calib_complete(calibrated),.sr_ack(),.ref_ack(),
.O_ddr_addr(ddr_addr),.O_ddr_ba(ddr_bank),.O_ddr_cs_n(ddr_cs),.O_ddr_ras_n(ddr_ras),.O_ddr_cas_n(ddr_cas),
.O_ddr_we_n(ddr_we),.O_ddr_clk(ddr_ck),.O_ddr_clk_n(ddr_ck_n),.O_ddr_cke(ddr_cke),.O_ddr_odt(ddr_odt),
.O_ddr_reset_n(ddr_reset_n),.O_ddr_dqm(ddr_dm),.IO_ddr_dq(ddr_dq),.IO_ddr_dqs(ddr_dqs),.IO_ddr_dqs_n(ddr_dqs_n));
// USER state is only an LED observation here; software uses synchronized mailbox.
assign led=~{heartbeat[23],ready,calibrated,arm_sw};
endmodule
