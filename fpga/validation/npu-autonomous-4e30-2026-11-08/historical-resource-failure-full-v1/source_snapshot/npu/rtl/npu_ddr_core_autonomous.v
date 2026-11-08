// DDR NPU core excluding the physical controller IP/PLL/pins.
// SYS packet master and Conv loader share one tagged arbiter, adapter and RAMs.
module npu_ddr_core_autonomous #(
 parameter [15:0] RESET_HOLD_INIT=16'hffff,RECAL_HOLD=16'd27000,
 parameter SYS_SETTLE=256,ADAPTER_SETTLE=256,
 parameter LINK_TIMEOUT=27000000,ADAPTER_TIMEOUT=8100000,
 parameter LOADER_MEMORY_TIMEOUT=2700000,LOADER_DRAIN_TIMEOUT=2700000,
 parameter REQUEST_DATA_PIPELINE=0
)(
 input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire[3:0] aux,
 inout wire[7:0] data,output wire ready,output wire[3:0] led,
 input wire pll_lock,user_clk,ip_user_reset,calibrated,
 output wire controller_reset_n,
 output wire[2:0] cmd,output wire cmd_en,output wire[26:0] address,input wire cmd_ready,
 output wire[127:0] wr_data,output wire wr_en,wr_end,output wire[15:0] mask,input wire wr_ready,
 input wire[127:0] rd_data,input wire rd_valid,rd_end
);
 reg[2:0] sys_reset_sync=0;
 always @(posedge sys_clk or negedge reset_n)begin
  if(!reset_n)sys_reset_sync<=0;else sys_reset_sync<={sys_reset_sync[1:0],1'b1};
 end
 wire sys_reset_n=reset_n&&sys_reset_sync[2];
 wire raw_reset_n=reset_n&&arm_sw;
 reg[15:0] reset_hold=RESET_HOLD_INIT;reg[23:0] heartbeat=0;
 always @(posedge sys_clk or negedge raw_reset_n)begin
  if(!raw_reset_n)begin reset_hold<=RESET_HOLD_INIT;heartbeat<=0;end
  else begin heartbeat<=heartbeat+1'b1;
   if(!pll_lock)reset_hold<=RECAL_HOLD;else if(reset_hold!=0)reset_hold<=reset_hold-1'b1;
  end
 end
 assign controller_reset_n=raw_reset_n&&pll_lock&&reset_hold==0;
 wire user_async_reset_n=controller_reset_n&&!ip_user_reset;
 (* ASYNC_REG="TRUE" *) reg[2:0] user_reset_sync;
 always @(posedge user_clk or negedge user_async_reset_n)begin
  if(!user_async_reset_n)user_reset_sync<=0;else user_reset_sync<={user_reset_sync[1:0],1'b1};
 end
 wire user_reset_n=user_reset_sync[2];
 wire operation_reset_n=user_reset_n&&calibrated;
 (* ASYNC_REG="TRUE" *) reg[1:0] memory_ready_sync;
 reg[15:0] memory_settle;
 always @(posedge sys_clk or negedge raw_reset_n)begin
  if(!raw_reset_n)begin memory_ready_sync<=0;memory_settle<=0;end
  else begin memory_ready_sync<={memory_ready_sync[0],operation_reset_n};
   if(!memory_ready_sync[1])memory_settle<=0;else if(memory_settle<SYS_SETTLE)memory_settle<=memory_settle+1'b1;
  end
 end
 wire memory_ready=raw_reset_n&&memory_ready_sync[1]&&memory_settle>=SYS_SETTLE;
 wire coordinated_reset_n=sys_reset_n&&raw_reset_n&&memory_ready;
 // Generation survives ARM/calibration resets and changes on every readiness loss.
 reg[15:0] generation=0;reg memory_ready_prev=0;
 always @(posedge sys_clk or negedge reset_n)begin
  if(!reset_n)begin generation<=0;memory_ready_prev<=0;end
  else begin memory_ready_prev<=memory_ready;if(memory_ready_prev&&!memory_ready)generation<=generation+1'b1;end
 end
 wire[7:0] data_out;wire data_oe;
 assign data=data_oe?data_out:8'bz;
 wire arbiter_active,arbiter_owner,arbiter_fault,inner_active,inner_fault,outer_active,outer_owner,outer_fault;
 assign arbiter_active=inner_active||outer_active;assign arbiter_fault=inner_fault||outer_fault;
 wire conv_start,conv_abort,conv_clear,conv_start_ready,conv_busy,conv_done,conv_error,conv_quarantined,conv_result_valid;
 wire[3:0] conv_error_code,conv_mem_status;wire[31:0] kernel_cycles,ddr_wait_cycles,total_cycles,conv_read_beats,conv_write_beats;
 wire[415:0] descriptor;
 wire matrix_start,matrix_start_ready,matrix_busy,matrix_done,matrix_error,matrix_quarantined,matrix_result_valid,matrix_done_ack,seq_valid,seq_abort;
 wire[287:0] matrix_job;wire[3:0] matrix_error_code;wire[31:0] matrix_accepted,matrix_completed,matrix_expected;
 wire host_conv_start,host_conv_abort,host_conv_clear,host_matrix_start,host_matrix_done_ack;
 wire[287:0]host_matrix_job;
 wire local_start,local_abort,local_clear,local_start_ready,local_running,local_abort_level,local_done,local_error,local_aborted,local_quarantined;
 wire[15:0]local_status;wire[5:0]monitor_index;wire[31:0]monitor_data;
 wire cpu_tile_start,cpu_tile_clear,cpu_matrix_start,cpu_matrix_done_ack,cpu_fault,cpu_trap,cpu_safe;
 wire[415:0]cpu_descriptor;wire[287:0]cpu_matrix_job;wire[3:0]cpu_error_code;
 wire[31:0]cpu_node,cpu_stage,cpu_app_error,cpu_finish;
 assign conv_start=host_conv_start||cpu_tile_start;
 assign conv_abort=host_conv_abort||local_abort_level;
 assign conv_clear=host_conv_clear||cpu_tile_clear||local_clear;
 assign matrix_start=host_matrix_start||cpu_matrix_start;
 assign matrix_job=local_running?cpu_matrix_job:host_matrix_job;
 assign matrix_done_ack=host_matrix_done_ack||cpu_matrix_done_ack;
 wire[415:0] seq_descriptor;wire[415:0] active_descriptor=matrix_busy?seq_descriptor:(local_running?cpu_descriptor:descriptor);
 reg[31:0] accepted_ref,completed_ref;
 always @(posedge sys_clk)begin
  if(!coordinated_reset_n||(matrix_start&&matrix_start_ready))begin accepted_ref<=0;completed_ref<=0;end
  else begin accepted_ref<=matrix_accepted;completed_ref<=matrix_completed;end
 end
 wire matrix_progress=matrix_accepted!=accepted_ref||matrix_completed!=completed_ref;
 wire m0_req_t,m0_cancel_t,m0_done_t;wire[1:0]m0_h_op;wire[31:0]m0_h_addr,m0_h_arg,m0_r_crc;wire[15:0]m0_h_beats,m0_r_beats;wire[23:0]m0_h_tag,m0_r_tag;wire[3:0]m0_r_status;
 wire m0_w_we;wire[7:0]m0_w_addr,m0_r_addr;wire[127:0]m0_w_data,sys_read_data;
 npu_ddr_sys_autonomous #(.TIMEOUT(LINK_TIMEOUT),.REQUEST_DATA_PIPELINE(REQUEST_DATA_PIPELINE)) link(
  sys_clk,sys_reset_n,arm_sw,bus_clk,dir,data,data_out,data_oe,ready,
  memory_ready,generation,arbiter_fault,arbiter_active,
  host_conv_start,host_conv_abort,host_conv_clear,descriptor,
  conv_start_ready&&!matrix_busy&&!matrix_error,conv_busy||matrix_busy,conv_done,conv_error,conv_quarantined,conv_error_code,
  kernel_cycles,ddr_wait_cycles,total_cycles,
  m0_req_t,m0_cancel_t,m0_h_op,m0_h_addr,m0_h_arg,m0_h_beats,m0_h_tag,
  m0_done_t,m0_r_tag,m0_r_status,m0_r_beats,m0_w_we,m0_w_addr,m0_w_data,m0_r_addr,sys_read_data,
  host_matrix_start,host_matrix_job,matrix_start_ready,matrix_busy,matrix_done,matrix_error,matrix_quarantined,matrix_result_valid,
  matrix_error_code,matrix_progress,matrix_accepted,matrix_completed,host_matrix_done_ack,
  local_start,local_abort,local_clear,local_start_ready,local_running,local_status,monitor_index,monitor_data);
 wire m1_req_t,m1_cancel_t,m1_done_t;wire[1:0]m1_h_op;wire[31:0]m1_h_addr,m1_h_arg,m1_r_crc;wire[15:0]m1_h_beats,m1_r_beats;wire[23:0]m1_h_tag,m1_r_tag;wire[3:0]m1_r_status;
 wire m1_w_we;wire[7:0]m1_w_addr,m1_r_addr;wire[127:0]m1_w_data;
 npu_ddr_tile_loader_8oc #(.MEMORY_TIMEOUT(LOADER_MEMORY_TIMEOUT),.DRAIN_TIMEOUT(LOADER_DRAIN_TIMEOUT)) loader(
  .clk(sys_clk),.reset_n(coordinated_reset_n),.memory_ready(memory_ready),.start(conv_start||(seq_valid&&conv_start_ready)),.abort(conv_abort||seq_abort),.clear(conv_clear),
  .start_ready(conv_start_ready),.busy(conv_busy),
  .cfg_ic(active_descriptor[0+:5]),.cfg_oc(active_descriptor[8+:4]),.cfg_oh(active_descriptor[16+:5]),.cfg_ow(active_descriptor[24+:5]),
  .cfg_kernel(active_descriptor[32+:2]),.cfg_stride(active_descriptor[40+:2]),.first_block(active_descriptor[48]),.final_block(active_descriptor[49]),
  .input_full_h(active_descriptor[64+:16]),.input_full_w(active_descriptor[80+:16]),.input_origin_y(active_descriptor[96+:32]),.input_origin_x(active_descriptor[128+:32]),
  .input_base(active_descriptor[160+:32]),.input_row_pitch(active_descriptor[192+:32]),.input_channel_pitch(active_descriptor[224+:32]),
  .weight_base(active_descriptor[256+:32]),.weight_oc_stride(active_descriptor[288+:32]),.output_base(active_descriptor[320+:32]),
  .output_row_pitch(active_descriptor[352+:32]),.output_channel_pitch(active_descriptor[384+:32]),.output_tail_owned(active_descriptor[50]),
  .block_done(conv_done),.result_valid(conv_result_valid),.error(conv_error),.quarantined(conv_quarantined),.error_code(conv_error_code),.mem_status(conv_mem_status),
  .total_cycles(total_cycles),.ddr_wait_cycles(ddr_wait_cycles),.read_beats(conv_read_beats),.write_beats(conv_write_beats),.kernel_cycles(kernel_cycles),
  .req_t(m1_req_t),.cancel_t(m1_cancel_t),.h_op(m1_h_op),.h_addr(m1_h_addr),.h_beats(m1_h_beats),.h_arg(m1_h_arg),.h_tag(m1_h_tag),
  .done_t(m1_done_t),.r_tag(m1_r_tag),.r_status(m1_r_status),.r_beats(m1_r_beats),
  .w_we(m1_w_we),.w_addr(m1_w_addr),.w_data(m1_w_data),.r_addr(m1_r_addr),.r_data(sys_read_data));
 wire req_t,cancel_t,done_t;wire[1:0]h_op;wire[31:0]h_addr,h_arg,r_crc;wire[15:0]h_beats,r_beats;wire[23:0]h_tag,r_tag;wire[3:0]r_status;
 npu_ddr_matmul_sequencer sequence_matrix(
  .clk(sys_clk),.reset_n(coordinated_reset_n),.abort(conv_abort&&matrix_busy),.clear(local_clear),.memory_ready(memory_ready),
  .job_valid(matrix_start),.job_ready(matrix_start_ready),
  .job_m(matrix_job[0+:32]),.job_k(matrix_job[32+:32]),.job_n(matrix_job[64+:32]),
  .job_a_base(matrix_job[96+:32]),.job_a_pitch(matrix_job[128+:32]),.job_b_base(matrix_job[160+:32]),.job_b_pitch(matrix_job[192+:32]),.job_c_base(matrix_job[224+:32]),.job_c_pitch(matrix_job[256+:32]),
  .busy(matrix_busy),.out_valid(matrix_done),.out_ready(matrix_done_ack),.result_valid(matrix_result_valid),.error(matrix_error),.quarantined(matrix_quarantined),.error_code(matrix_error_code),
  .accepted_tiles(matrix_accepted),.completed_tiles(matrix_completed),.expected_tiles(matrix_expected),
  .descriptor_valid(seq_valid),.descriptor_ready(conv_start_ready),
  .cfg_ic(seq_descriptor[0+:5]),.cfg_oc(seq_descriptor[8+:4]),.cfg_oh(seq_descriptor[16+:5]),.cfg_ow(seq_descriptor[24+:5]),
  .cfg_kernel(seq_descriptor[32+:2]),.cfg_stride(seq_descriptor[40+:2]),.first_block(seq_descriptor[48]),.final_block(seq_descriptor[49]),
  .input_full_h(seq_descriptor[64+:16]),.input_full_w(seq_descriptor[80+:16]),.input_origin_y(seq_descriptor[96+:32]),.input_origin_x(seq_descriptor[128+:32]),
  .input_base(seq_descriptor[160+:32]),.input_row_pitch(seq_descriptor[192+:32]),.input_channel_pitch(seq_descriptor[224+:32]),
  .weight_base(seq_descriptor[256+:32]),.weight_oc_stride(seq_descriptor[288+:32]),
  .output_base(seq_descriptor[320+:32]),.output_row_pitch(seq_descriptor[352+:32]),.output_channel_pitch(seq_descriptor[384+:32]),.output_tail_owned(seq_descriptor[50]),
  .tile_busy(conv_busy),.tile_done(conv_done),.tile_error(conv_error),.tile_quarantined(conv_quarantined),.tile_result_valid(conv_result_valid),.tile_abort(seq_abort));
 assign seq_descriptor[7:5]=0;assign seq_descriptor[15:12]=0;assign seq_descriptor[23:21]=0;assign seq_descriptor[31:29]=0;
 assign seq_descriptor[39:34]=0;assign seq_descriptor[47:42]=0;assign seq_descriptor[63:51]=0;
 wire m2_req_t,m2_cancel_t,m2_done_t,m2_w_we;wire[1:0]m2_h_op;
 wire[31:0]m2_h_addr,m2_h_arg,m2_r_crc;wire[15:0]m2_h_beats,m2_r_beats;wire[23:0]m2_h_tag,m2_r_tag;wire[3:0]m2_r_status;
 wire[7:0]m2_w_addr,m2_r_addr;wire[127:0]m2_w_data;
 wire mx_req_t,mx_cancel_t,mx_done_t;wire[1:0]mx_h_op;
 wire[31:0]mx_h_addr,mx_h_arg,mx_r_crc;wire[15:0]mx_h_beats,mx_r_beats;wire[23:0]mx_h_tag,mx_r_tag;wire[3:0]mx_r_status;
 npu_ddr_arbiter host_cpu_owner(
  sys_clk,coordinated_reset_n,
  m0_req_t,m0_cancel_t,m0_h_op,m0_h_addr,m0_h_beats,m0_h_arg,m0_h_tag,m0_done_t,m0_r_tag,m0_r_status,m0_r_crc,m0_r_beats,
  m2_req_t,m2_cancel_t,m2_h_op,m2_h_addr,m2_h_beats,m2_h_arg,m2_h_tag,m2_done_t,m2_r_tag,m2_r_status,m2_r_crc,m2_r_beats,
  mx_req_t,mx_cancel_t,mx_h_op,mx_h_addr,mx_h_beats,mx_h_arg,mx_h_tag,mx_done_t,mx_r_tag,mx_r_status,mx_r_crc,mx_r_beats,
  outer_active,outer_owner,outer_fault);
 npu_local_run_control local_run(
  .clk(sys_clk),.reset_n(sys_reset_n),.arm(arm_sw),.memory_ready(memory_ready),.epoch(generation),
  .start(local_start),.abort(local_abort),.clear(local_clear),.arb_active(arbiter_active),.arb_fault(arbiter_fault),
  .mac_busy(conv_busy||matrix_busy),.mac_quarantined(conv_quarantined||matrix_quarantined),
  .cpu_safe_to_release(cpu_safe),.cpu_fault(cpu_fault),.cpu_trap(cpu_trap),.cpu_error_code(cpu_error_code),
  .cpu_node(cpu_node),.cpu_stage(cpu_stage),.cpu_app_error(cpu_app_error),.cpu_finish(cpu_finish),
  .run_enable(local_running),.abort_level(local_abort_level),.start_ready(local_start_ready),
  .done(local_done),.error(local_error),.aborted(local_aborted),.quarantined(local_quarantined),.status(local_status),
  .monitor_index(monitor_index),.monitor_data(monitor_data));
 npu_local_cpu_subsystem local_cpu(
  .clk(sys_clk),.reset_n(coordinated_reset_n),.memory_ready(memory_ready),.run_enable(local_running),
  .abort(local_abort_level),.clear(local_clear),.epoch(generation),
  .cpu_trap(cpu_trap),.cpu_fault(cpu_fault),.cpu_error_code(cpu_error_code),.safe_to_release(cpu_safe),
  .progress_node(cpu_node),.progress_stage(cpu_stage),.app_error(cpu_app_error),.finish_code(cpu_finish),
  .tile_start(cpu_tile_start),.tile_descriptor(cpu_descriptor),.tile_clear(cpu_tile_clear),
  .tile_start_ready(conv_start_ready&&!matrix_busy),.tile_busy(conv_busy),.tile_done(conv_done),
  .tile_error(conv_error),.tile_quarantined(conv_quarantined),.tile_result_valid(conv_result_valid),.tile_error_code(conv_error_code),
  .matrix_start(cpu_matrix_start),.matrix_job(cpu_matrix_job),.matrix_done_ack(cpu_matrix_done_ack),
  .matrix_start_ready(matrix_start_ready&&!conv_busy),.matrix_busy(matrix_busy),.matrix_done(matrix_done),
  .matrix_error(matrix_error),.matrix_quarantined(matrix_quarantined),.matrix_result_valid(matrix_result_valid),.matrix_error_code(matrix_error_code),
  .req_t(m2_req_t),.cancel_t(m2_cancel_t),.h_op(m2_h_op),.h_addr(m2_h_addr),.h_beats(m2_h_beats),.h_arg(m2_h_arg),.h_tag(m2_h_tag),
  .done_t(m2_done_t),.r_tag(m2_r_tag),.r_status(m2_r_status),.r_beats(m2_r_beats),
  .w_we(m2_w_we),.w_addr(m2_w_addr),.w_data(m2_w_data),.r_addr(m2_r_addr),.r_data(sys_read_data));
 npu_ddr_arbiter arbitration(
  sys_clk,coordinated_reset_n,
  mx_req_t,mx_cancel_t,mx_h_op,mx_h_addr,mx_h_beats,mx_h_arg,mx_h_tag,mx_done_t,mx_r_tag,mx_r_status,mx_r_crc,mx_r_beats,
  m1_req_t,m1_cancel_t,m1_h_op,m1_h_addr,m1_h_beats,m1_h_arg,m1_h_tag,m1_done_t,m1_r_tag,m1_r_status,m1_r_crc,m1_r_beats,
  req_t,cancel_t,h_op,h_addr,h_beats,h_arg,h_tag,done_t,r_tag,r_status,r_crc,r_beats,inner_active,arbiter_owner,inner_fault);
 wire bridge_active,adapter_cmd_valid,adapter_cmd_ready,adapter_cancel,adapter_rsp_valid,adapter_busy;
 wire[1:0]adapter_op;wire[31:0]adapter_addr,adapter_arg,adapter_rsp_crc;wire[15:0]adapter_beats,adapter_rsp_beats;wire[23:0]adapter_tag,adapter_rsp_tag;wire[3:0]adapter_rsp_status;
 memv1_bridge bridge(user_clk,operation_reset_n,req_t,cancel_t,h_op,h_addr,h_beats,h_arg,h_tag,done_t,
  r_tag,r_status,r_crc,r_beats,bridge_active,adapter_cmd_valid,adapter_cmd_ready,adapter_op,adapter_addr,adapter_beats,adapter_arg,adapter_tag,adapter_cancel,
  adapter_rsp_valid,adapter_rsp_tag,adapter_rsp_status,adapter_rsp_crc,adapter_rsp_beats);
 wire[7:0]stage_raddr,stage_waddr;wire[127:0]stage_rdata,stage_wdata;wire stage_we;
 mem_adapter #(.APP_ROW_PAD(1),.TIMEOUT_CYCLES(ADAPTER_TIMEOUT),.SETTLE_CYCLES(ADAPTER_SETTLE)) adapter(
  user_clk,operation_reset_n,calibrated,adapter_cmd_valid,adapter_cmd_ready,adapter_op,adapter_addr,adapter_beats,adapter_arg,adapter_tag,adapter_cancel,
  adapter_rsp_valid,adapter_rsp_tag,adapter_rsp_status,adapter_rsp_crc,adapter_rsp_beats,adapter_busy,
  stage_raddr,stage_rdata,stage_we,stage_waddr,stage_wdata,
  cmd,cmd_en,address,cmd_ready,wr_data,wr_en,wr_end,mask,wr_ready,rd_data,rd_valid,rd_end);
 // The SYS endpoint rejects overlapping host work throughout conv_busy. Thus
 // shared staging is owned from loader start through final adapter completion.
 wire stage_sys_we=conv_busy?m1_w_we:(local_running?m2_w_we:m0_w_we);
 wire[7:0]stage_sys_waddr=conv_busy?m1_w_addr:(local_running?m2_w_addr:m0_w_addr);
 wire[127:0]stage_sys_wdata=conv_busy?m1_w_data:(local_running?m2_w_data:m0_w_data);
 wire[7:0]stage_sys_raddr=conv_busy?m1_r_addr:(local_running?m2_r_addr:m0_r_addr);
 memv1_dpram #(.AW(8),.DW(128)) write_stage(sys_clk,stage_sys_we,stage_sys_waddr,stage_sys_wdata,user_clk,stage_raddr,stage_rdata);
 memv1_dpram #(.AW(8),.DW(128)) read_buffer(user_clk,stage_we,stage_waddr,stage_wdata,sys_clk,stage_sys_raddr,sys_read_data);
 assign led=~{heartbeat[23],memory_ready,ready,arm_sw};
endmodule
