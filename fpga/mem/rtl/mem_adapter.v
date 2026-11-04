// MEMV1 memory adapter, USER clock domain (one outstanding command).
// Native Gowin 1:4/BL8 interface: one 128-bit beat per command, same address mapping, paired write issue
// and registered-want enable structure as mem_bist PIPELINE=4 (the structure proven on hardware).
// cmd_op: 0 READ (into the read buffer), 1 WRITE (from the write staging buffer), 2 CRC32 over a range.
// Byte k of a beat is bits [8k+:8]; byte address = base + 16*beat + k.
// Status (rsp_status, same numbering as the LINK reply status): 0 ok, 3 invalid range, 4 no-progress timeout,
// 5 not ready (uncalibrated / not settled), 8 cancelled, 9 fault (calibration lost / read ordering).
// A WRITE reported with status 8/9/4 may have written an unknown prefix of its beats (rsp_done_beats complete
// beats are certain); nothing is rolled back.
module mem_adapter #(
 parameter APP_ROW_PAD=1,
 parameter TIMEOUT_CYCLES=8100000,
 parameter SETTLE_CYCLES=256,
 parameter [31:0] CAPACITY=32'd134217728,
 parameter MAX_BEATS=256
)(
 input wire clk,reset_n,calibrated,
 input wire cmd_valid,output wire cmd_ready,
 input wire[1:0] cmd_op,input wire[31:0] cmd_addr,input wire[15:0] cmd_beats,input wire[31:0] cmd_arg,input wire[23:0] cmd_tag,
 input wire cancel,
 output reg rsp_valid,output reg[23:0] rsp_tag,output reg[3:0] rsp_status,output reg[31:0] rsp_crc,output reg[15:0] rsp_done_beats,
 output wire busy,
 output reg[7:0] stage_raddr,input wire[127:0] stage_rdata,
 output reg stage_we,output reg[7:0] stage_waddr,output reg[127:0] stage_wdata,
 output wire[2:0] app_cmd,output wire app_cmd_en,output wire[26:0] app_addr,input wire app_cmd_ready,
 output wire[127:0] app_write_data,output wire app_write_en,app_write_end,output wire[15:0] app_write_mask,input wire app_write_ready,
 input wire[127:0] app_read_data,input wire app_read_valid,app_read_end
);
localparam S_IDLE=4'd0,S_CHECK=4'd1,S_FETCH0=4'd2,S_FETCH1=4'd3,S_FETCH2=4'd4,S_ISSUE=4'd5,
           S_GAP=4'd6,S_RWAIT=4'd7,S_CRC=4'd8,S_FINISH=4'd9;
reg[3:0] state;
reg[1:0] op;reg[31:0] base,arg;reg[15:0] beats;reg[23:0] tag;
reg[15:0] index;reg[31:0] wait_cycles;reg[3:0] byte_count;
reg command_sent,data_sent,read_pending,range_ok_q;
reg want_cmd_q,want_wr_q,cmdfire_q,datafire_q;
reg[127:0] data_q;reg[31:0] crc;reg[3:0] finish_status;
reg cal_q;reg[15:0] settle_count;
wire settled=settle_count>=SETTLE_CYCLES;
always @(posedge clk or negedge reset_n)begin
 if(!reset_n)begin cal_q<=0;settle_count<=0;end
 else begin cal_q<=calibrated;
  if(!cal_q)settle_count<=0;else if(!settled)settle_count<=settle_count+1'b1;end end
assign cmd_ready=(state==S_IDLE)&&!rsp_valid;
assign busy=(state!=S_IDLE)||rsp_valid;
// Request range check, registered once in S_CHECK: 16B aligned, 1..MAX_BEATS beats, inside CAPACITY, no wrap.
wire[63:0] request_end={32'b0,base}+({48'b0,beats}<<4);
wire range_ok=base[3:0]==0&&beats!=0&&beats<=MAX_BEATS&&request_end<={32'b0,CAPACITY};
wire writing=op==2'd1;
wire[31:0] byte_address=base+({16'b0,index}<<4);
wire[25:0] linear_word=byte_address[26:1];
assign app_addr=APP_ROW_PAD?{linear_word[12:10],1'b0,linear_word[25:13],linear_word[9:0]}:
                            {1'b0,linear_word[12:10],linear_word[25:13],linear_word[9:0]};
assign app_cmd=writing?3'b000:3'b001;
assign app_write_data=data_q;assign app_write_mask=16'h0000;
wire issuing=state==S_ISSUE;
wire want_cmd_c=issuing&&((writing&&!command_sent)||(!writing&&!read_pending));
wire want_wr_c=issuing&&writing&&!data_sent;
assign app_cmd_en=app_cmd_ready&&want_cmd_q&&!cmdfire_q&&!cancel&&(!writing||app_write_ready);
assign app_write_en=app_write_ready&&want_wr_q&&!datafire_q&&!cancel&&app_cmd_ready;
assign app_write_end=app_write_en;
wire command_fire=app_cmd_en&&app_cmd_ready;
wire data_fire=app_write_en&&app_write_ready;
wire progress=command_fire||data_fire||(app_read_valid&&read_pending);
wire[7:0] crc_byte=data_q[8*byte_count+:8];
wire[31:0] crc_next;
memv1_crc32b crc_step(crc,crc_byte,crc_next);
task finish;input[3:0] code;begin state<=S_FINISH;finish_status<=code;end endtask
always @(posedge clk or negedge reset_n)begin
 if(!reset_n)begin
  state<=S_IDLE;op<=0;base<=0;arg<=0;beats<=0;tag<=0;index<=0;wait_cycles<=0;byte_count<=0;
  command_sent<=0;data_sent<=0;read_pending<=0;range_ok_q<=0;
  want_cmd_q<=0;want_wr_q<=0;cmdfire_q<=0;datafire_q<=0;data_q<=0;crc<=0;finish_status<=0;
  rsp_valid<=0;rsp_tag<=0;rsp_status<=0;rsp_crc<=0;rsp_done_beats<=0;
  stage_raddr<=0;stage_we<=0;stage_waddr<=0;stage_wdata<=0;
 end else begin
  want_cmd_q<=want_cmd_c;want_wr_q<=want_wr_c;cmdfire_q<=command_fire;datafire_q<=data_fire;
  stage_we<=0;rsp_valid<=0;
  case(state)
  S_IDLE:if(cmd_valid&&cmd_ready)begin
   op<=cmd_op;base<=cmd_addr;beats<=cmd_beats;arg<=cmd_arg;tag<=cmd_tag;index<=0;
   command_sent<=0;data_sent<=0;read_pending<=0;wait_cycles<=0;byte_count<=0;
   crc<=~cmd_arg;state<=S_CHECK;end
  S_CHECK:begin range_ok_q<=range_ok;state<=S_FETCH0;end
  S_FETCH0:begin
   if(!range_ok_q)finish(4'd3);
   else if(!calibrated||!settled)finish(4'd5);
   else if(cancel)finish(4'd8);
   else if(writing)begin stage_raddr<=index[7:0];state<=S_FETCH1;end
   else begin state<=S_ISSUE;wait_cycles<=0;end end
  S_FETCH1:state<=S_FETCH2;
  S_FETCH2:begin data_q<=stage_rdata;state<=S_ISSUE;wait_cycles<=0;end
  S_ISSUE:begin
   if(!calibrated)finish(4'd9);
   else if(cancel)finish(4'd8);
   else if(app_read_valid)finish(4'd9);
   else if(wait_cycles>=TIMEOUT_CYCLES-1&&!progress)finish(4'd4);
   else begin
    wait_cycles<=progress?32'd0:wait_cycles+1'b1;
    if(writing)begin
     if(command_fire&&data_fire)begin state<=S_GAP;index<=index+1'b1;end
    end else if(command_fire)begin read_pending<=1;state<=S_RWAIT;end
   end end
  S_GAP:begin
   if(!calibrated)finish(4'd9);
   else if(index==beats)finish(4'd0);
   else if(cancel)finish(4'd8);
   else begin
    wait_cycles<=0;
    if(writing)begin stage_raddr<=index[7:0];state<=S_FETCH1;end
    else state<=S_ISSUE;
   end end
  S_RWAIT:begin
   if(!calibrated)finish(4'd9);
   else if(app_read_valid&&(!read_pending||!app_read_end))finish(4'd9);
   else if(app_read_valid)begin
    read_pending<=0;
    if(op==2'd0)begin stage_we<=1;stage_waddr<=index[7:0];stage_wdata<=app_read_data;index<=index+1'b1;state<=S_GAP;end
    else begin data_q<=app_read_data;byte_count<=0;state<=S_CRC;end
   end else if(wait_cycles>=TIMEOUT_CYCLES-1)finish(4'd4);
   else wait_cycles<=wait_cycles+1'b1;
   end
  S_CRC:begin
   crc<=crc_next;byte_count<=byte_count+1'b1;
   if(byte_count==4'd15)begin index<=index+1'b1;state<=S_GAP;end
   end
  S_FINISH:begin
   rsp_valid<=1;rsp_tag<=tag;rsp_status<=finish_status;rsp_crc<=~crc;rsp_done_beats<=index;
   state<=S_IDLE;end
  default:state<=S_IDLE;
  endcase
 end
end
endmodule
