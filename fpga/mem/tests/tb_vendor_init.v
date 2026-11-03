// Functional vendor model audit, not a DRAM electrical or timing simulation.
// No DRAM device model is connected; calibration completion is NOT expected.
`timescale 1ns/1ps
module tb_vendor_init;
reg clk=0,memory_clk=0,rst=0;
always #18.518519 clk=~clk;
always #1.543210 memory_clk=~memory_clk;
wire user_clk,cal,ip_reset;wire[15:0] dq;wire[1:0] dqs,dqsn;
GSR GSR(.GSRI(1'b1));
MemDDR3 dut(.clk(clk),.memory_clk(memory_clk),.pll_lock(1'b1),.rst_n(rst),
.cmd(3'b0),.cmd_en(1'b0),.addr(27'b0),.wr_data(128'b0),.wr_data_en(1'b0),
.wr_data_end(1'b0),.wr_data_mask(16'b0),.sr_req(1'b0),.ref_req(1'b0),.burst(1'b1),
.clk_out(user_clk),.ddr_rst(ip_reset),.init_calib_complete(cal),
.IO_ddr_dq(dq),.IO_ddr_dqs(dqs),.IO_ddr_dqs_n(dqsn));
wire update_hold=dut.\gw3_top/u_ddr_phy_top/uddcntln ;
wire init_start=dut.\gw3_top/u_ddr_phy_top/ddr_init_st_Z ;
wire[7:0] step=dut.\gw3_top/u_ddr_phy_top/dll_step ;
wire capture_step=dut.\gw3_top/u_ddr_phy_top/n1426_3 ;
wire lock=dut.\gw3_top/u_ddr_phy_top/dll_lock ;
realtime last_step_change=0,hold_time=0;integer captures=0;
always @(step)begin last_step_change=$realtime;$display("STEP at%0t value%0d",$time,step);end
always @(update_hold)begin if(update_hold)hold_time=$realtime;$display("UPDATE_HOLD at%0t value%b",$time,update_hold);end
always @(init_start)$display("INIT_START at%0t value%b",$time,init_start);
always @(posedge user_clk)if(capture_step)begin
captures=captures+1;
$display("STEP_CAPTURE at%0t stable_ns%0f hold_age_ns%0f lock%b value%0d",$time,$realtime-last_step_change,$realtime-hold_time,lock,step);
if(!lock||!update_hold||$realtime-last_step_change<24.69)$fatal(1,"DLL step capture not held and settled");
end
initial begin #100;rst=1;#2000000;
if(captures==0)$fatal(1,"initialization did not reach DLL step capture");
$display("PASS vendor initialization model: captures%0d; no physical DDR or full calibration claim",captures);$finish;end
endmodule
