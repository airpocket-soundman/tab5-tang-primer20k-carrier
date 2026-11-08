// NPU+DDR top: pinned Sipeed sample controller, established398.25MHz PLL.
// The vendor row14 output is clipped to physical row13; CS is tied low, as MEMV1.
module tab5_dock_npu_ddr_autonomous_top(
 input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire[3:0]aux,
 inout wire[7:0]data,output wire ready,output wire[3:0]led,
 output wire[12:0]ddr_addr,output wire[2:0]ddr_bank,
 output wire ddr_cs,ddr_ras,ddr_cas,ddr_we,ddr_ck,ddr_ck_n,ddr_cke,ddr_odt,ddr_reset_n,
 output wire[1:0]ddr_dm,inout wire[15:0]ddr_dq,inout wire[1:0]ddr_dqs,ddr_dqs_n
);
 wire memory_clk,pll_lock,user_clk,calibrated,ip_user_reset,controller_reset_n;
 wire[2:0]cmd;wire cmd_en,cmd_ready,wr_en,wr_end,wr_ready,rd_valid,rd_end;
 wire[26:0]address;wire[127:0]wr_data,rd_data;wire[15:0]mask;
 mem_pll frequency(sys_clk,!reset_n,memory_clk,pll_lock);
 npu_ddr_core_autonomous #(.REQUEST_DATA_PIPELINE(1),.CPU_FAST_MUL(1)) core(sys_clk,reset_n,arm_sw,bus_clk,dir,aux,data,ready,led,
  pll_lock,user_clk,ip_user_reset,calibrated,controller_reset_n,
  cmd,cmd_en,address,cmd_ready,wr_data,wr_en,wr_end,mask,wr_ready,rd_data,rd_valid,rd_end);
 wire[13:0]sample_ddr_addr;wire sample_cs_unused;
 assign ddr_addr=sample_ddr_addr[12:0];assign ddr_cs=1'b0;
 DDR3_Memory_Interface_Top controller(.clk(sys_clk),.memory_clk(memory_clk),.pll_lock(pll_lock),.rst_n(controller_reset_n),
  .app_burst_number(6'd0),.cmd(cmd),.cmd_en(cmd_en),.addr({1'b0,address}),.cmd_ready(cmd_ready),
  .wr_data(wr_data),.wr_data_en(wr_en),.wr_data_end(wr_end),.wr_data_mask(mask),.wr_data_rdy(wr_ready),
  .rd_data(rd_data),.rd_data_valid(rd_valid),.rd_data_end(rd_end),.sr_req(1'b0),.ref_req(1'b0),.burst(1'b1),
  .clk_out(user_clk),.ddr_rst(ip_user_reset),.init_calib_complete(calibrated),.sr_ack(),.ref_ack(),
  .O_ddr_addr(sample_ddr_addr),.O_ddr_ba(ddr_bank),.O_ddr_cs_n(sample_cs_unused),.O_ddr_ras_n(ddr_ras),.O_ddr_cas_n(ddr_cas),
  .O_ddr_we_n(ddr_we),.O_ddr_clk(ddr_ck),.O_ddr_clk_n(ddr_ck_n),.O_ddr_cke(ddr_cke),.O_ddr_odt(ddr_odt),
  .O_ddr_reset_n(ddr_reset_n),.O_ddr_dqm(ddr_dm),.IO_ddr_dqs(ddr_dqs),.IO_ddr_dqs_n(ddr_dqs_n),.IO_ddr_dq(ddr_dq));
endmodule
