module mem_top(
input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire[3:0] aux,
inout wire[7:0] data,output wire ready,output wire[3:0] led,
output wire[12:0] ddr_addr,output wire[2:0] ddr_bank,
output wire ddr_cs,ddr_ras,ddr_cas,ddr_we,ddr_ck,ddr_ck_n,ddr_cke,ddr_odt,ddr_reset_n,
output wire[1:0] ddr_dm,inout wire[15:0] ddr_dq,inout wire[1:0] ddr_dqs,ddr_dqs_n
);
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
assign data=oe?out:8'bz;
mem_link link(sys_clk,reset_n,arm_sw,bus_clk,dir,data,out,oe,ready,
command_start,op,a,b,command_done,status,result);
wire bist_start,bist_cancel,busy,done,faulted;
wire[31:0] base,count,seed,job,verified,errors,first,accepted;
wire[7:0] error;wire[2:0] phase;wire[127:0] expected,actual;wire[63:0] cycles;
wire[175:0] native_debug;
// SYS observations remain available even if PLL/user clock disappears.
mem_mailbox control(sys_clk,raw_reset_n&&mailbox_epoch==0,user_clk,user_reset_n,
command_start,op,a,b,command_done,status,result,recalibrate,
calibrated,busy,done,faulted,error,phase,verified,errors,first,accepted,expected,actual,cycles,
bist_start,bist_cancel,base,count,seed,job,user_abort,native_debug);
wire[2:0] cmd;wire cmd_en,cmd_ready,wr_en,wr_end,wr_ready,rd_valid,rd_end;
wire[26:0] address;wire[127:0] wr_data,rd_data;wire[15:0] mask;
mem_bist engine(user_clk,user_reset_n,calibrated,bist_start,bist_cancel,base,count,seed,job,
busy,done,faulted,error,phase,verified,errors,first,accepted,expected,actual,cycles,
cmd,cmd_en,address,cmd_ready,wr_data,wr_en,wr_end,mask,wr_ready,rd_data,rd_valid,rd_end,native_debug);
MemDDR3 controller(.clk(sys_clk),.memory_clk(memory_clk),.pll_lock(pll_lock),.rst_n(controller_reset_n),
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
