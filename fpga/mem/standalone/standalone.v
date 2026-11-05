module ddr_bw_top(input wire sys_clk,reset_n,output wire uart_tx,
 output wire [12:0] ddr_addr,output wire [2:0] ddr_bank,output wire ddr_cs,ddr_ras,ddr_cas,ddr_we,ddr_ck,ddr_ck_n,ddr_cke,ddr_odt,ddr_reset_n,
 output wire [1:0] ddr_dm,inout wire [15:0] ddr_dq,inout wire [1:0] ddr_dqs,ddr_dqs_n);
wire memory_clk,pll_lock,user_clk,calibrated,ip_reset;
mem_pll frequency(sys_clk,!reset_n,memory_clk,pll_lock);
reg [15:0] hold=16'hffff;
always @(posedge sys_clk or negedge reset_n) if(!reset_n) hold<=16'hffff; else if(!pll_lock) hold<=16'd27000; else if(hold!=0) hold<=hold-1'b1;
wire ctrl_reset_n=reset_n&&pll_lock&&(hold==0);
reg [2:0] sync;
always @(posedge user_clk or negedge ctrl_reset_n) if(!ctrl_reset_n) sync<=0; else sync<={sync[1:0],1'b1};
wire user_reset_n=sync[2];
wire [5:0] burst;wire [2:0] cmd;wire cmd_en,cmd_ready,wr_en,wr_end,wr_ready,rd_valid,rd_end;wire [26:0] addr;wire [127:0] wr_data,rd_data;wire [15:0] mask;
wire [13:0] sample_addr;wire unused_cs;
assign ddr_addr=sample_addr[12:0];assign ddr_cs=1'b0;
DDR3_Memory_Interface_Top controller(.clk(sys_clk),.memory_clk(memory_clk),.pll_lock(pll_lock),.rst_n(ctrl_reset_n),
.app_burst_number(burst),.cmd(cmd),.cmd_en(cmd_en),.addr({1'b0,addr}),.cmd_ready(cmd_ready),.wr_data(wr_data),.wr_data_en(wr_en),.wr_data_end(wr_end),.wr_data_mask(mask),.wr_data_rdy(wr_ready),
.rd_data(rd_data),.rd_data_valid(rd_valid),.rd_data_end(rd_end),.sr_req(1'b0),.ref_req(1'b0),.burst(1'b1),.clk_out(user_clk),.ddr_rst(ip_reset),.init_calib_complete(calibrated),.sr_ack(),.ref_ack(),
.O_ddr_addr(sample_addr),.O_ddr_ba(ddr_bank),.O_ddr_cs_n(unused_cs),.O_ddr_ras_n(ddr_ras),.O_ddr_cas_n(ddr_cas),.O_ddr_we_n(ddr_we),.O_ddr_clk(ddr_ck),.O_ddr_clk_n(ddr_ck_n),.O_ddr_cke(ddr_cke),.O_ddr_odt(ddr_odt),.O_ddr_reset_n(ddr_reset_n),.O_ddr_dqm(ddr_dm),.IO_ddr_dq(ddr_dq),.IO_ddr_dqs(ddr_dqs),.IO_ddr_dqs_n(ddr_dqs_n));
ddr_bw_runner runner(.clk(user_clk),.reset_n(user_reset_n),.calibrated(calibrated),.uart_tx(uart_tx),.burst(burst),.cmd(cmd),.cmd_en(cmd_en),.addr(addr),.cmd_ready(cmd_ready),.wr_data(wr_data),.wr_en(wr_en),.wr_end(wr_end),.mask(mask),.wr_ready(wr_ready),.rd_data(rd_data),.rd_valid(rd_valid),.rd_end(rd_end));
endmodule

module ddr_bw_runner #(parameter BEATS=65536, CAL_TIMEOUT=199125000, UART_DIV=864)(input wire clk,reset_n,calibrated,output wire uart_tx,
output wire [5:0] burst,output wire [2:0] cmd,output wire cmd_en,output wire [26:0] addr,input wire cmd_ready,output wire [127:0] wr_data,output wire wr_en,wr_end,output wire [15:0] mask,input wire wr_ready,input wire [127:0] rd_data,input wire rd_valid,rd_end);
reg start;reg [7:0] job;reg [2:0] bl;reg mode;reg [2:0] phase;reg [31:0] cal_count;reg [3:0] settle;reg [3:0] state;reg [9:0] cal_stable;
wire busy,done,faulted,wm,rm;wire [7:0] error;wire [63:0] cyc,commands,wb,rb,cs,ws;wire [127:0] cw,cr,ce;
wire [31:0] SEED=32'h12345678 ^ {25'd0,job[7:1]};
mem_bw #(.APP_ROW_PAD(1),.EN_PIPE(1),.SEED_ONE_LANE(1),.TOTAL_TIMEOUT_CYCLES(64'd199125000)) engine(.clk(clk),.reset_n(reset_n),.calibrated(calibrated),.start(start),.cancel(1'b0),.mode({1'b0,mode}),.pattern(3'd0),.region_log2(5'd16),.mix_w(8'd1),.mix_r(8'd1),.base_byte(32'd0),.beat_count(BEATS),.seed(SEED),.job_id({24'd0,job}),.burst_log2(bl),.run_len(16'd1),.stride(24'd1),.busy(busy),.done(done),.faulted(faulted),.error_code(error),.accepted_job_id(),.cnt_cycles(cyc),.cnt_cmds(commands),.cnt_wbeats(wb),.cnt_rbeats(rb),.cnt_cmd_stall(cs),.cnt_wd_stall(ws),.lat_sum(),.lat_samples(),.lat_max(),.ck_wr(cw),.ck_rd(cr),.ck_exp(ce),.ck_wr_match(wm),.ck_rd_match(rm),.app_burst_number(burst),.app_cmd(cmd),.app_cmd_en(cmd_en),.app_addr(addr),.app_cmd_ready(cmd_ready),.app_write_data(wr_data),.app_write_en(wr_en),.app_write_end(wr_end),.app_write_mask(mask),.app_write_ready(wr_ready),.app_read_data(rd_data),.app_read_valid(rd_valid),.app_read_end(rd_end),.gate_wc_d(),.gate_rc_d(),.gate_wb_d());
// 109 payload bytes, little-endian fields, followed by CRC16-CCITT little endian.
reg [871:0] frame;reg [7:0] index;reg [15:0] crc;reg [9:0] shift;reg [15:0] div;reg [3:0] bits;reg tx;assign uart_tx=tx;
reg failed;reg [7:0] result_error;
function [15:0] crc_byte;input [15:0] c;input [7:0] d;reg [15:0] v;integer i;begin v=c^{d,8'b0};for(i=0;i<8;i=i+1) v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end endfunction
always @(posedge clk or negedge reset_n) begin
if(!reset_n) begin state<=0;start<=0;job<=0;bl<=0;mode<=0;phase<=0;cal_count<=0;cal_stable<=0;settle<=0;frame<=0;index<=0;crc<=16'hffff;shift<=0;div<=0;bits<=0;tx<=1;failed<=0;result_error<=0;end
else begin
start<=0;
case(state)
0: begin
 if(!calibrated) cal_stable<=0; else if(cal_stable<512) cal_stable<=cal_stable+1'b1;
 if(cal_stable>=512) state<=1; else if(cal_count>=CAL_TIMEOUT) begin failed<=1;result_error<=8'h80;state<=4; end else cal_count<=cal_count+1'b1;
 end
1: begin start<=1;state<=2;end
2: if(busy) state<=8; else if(done && error!=0 && !start) begin settle<=0;state<=3;end
8: if(done) begin settle<=0;state<=3;end
3: if(settle==8) begin failed<=faulted || error!=0 || (mode?!rm:!wm);result_error<=error;state<=4;end else settle<=settle+1'b1;
4: begin frame<={ce,cr,cw,ws,cs,rb,wb,commands,cyc,SEED,result_error,{5'b0,failed,rm,wm},{5'b0,bl},{7'b0,mode},job,32'h31574244};index<=0;crc<=16'hffff;bits<=0;tx<=1;state<=5;end
5: begin
 if(bits!=0) begin if(div==0) begin tx<=shift[0];shift<={1'b1,shift[9:1]};div<=UART_DIV-1;bits<=bits-1'b1;end else div<=div-1'b1;end
 else if(div!=0) div<=div-1'b1;
 else if(index<111) begin
   if(index<109) begin shift<={1'b1,frame[7:0],1'b0};crc<=crc_byte(crc,frame[7:0]);frame<=frame>>8;end
   else if(index==109) shift<={1'b1,crc[7:0],1'b0}; else shift<={1'b1,crc[15:8],1'b0};
   bits<=10;index<=index+1'b1;
 end else state<=6;
end
6: if(failed || job==25) state<=7; else begin
 job<=job+1'b1;
 if(job==0) begin mode<=1;bl<=0;end
 else if(job==1) begin phase<=0;mode<=0;bl<=1;end
 else case(phase)
 0: begin phase<=1;mode<=1;bl<=0;end
 1: begin phase<=2;mode<=0;bl<=0;end
 2: begin phase<=3;mode<=1;bl<=((job-2)>>2)+1;end
 3: begin phase<=0;mode<=0;bl<=((job-2)>>2)+2;end
 endcase
 state<=1;
end
7: ;
endcase
end end
endmodule
