// MEMV1 SYS-domain LINK + control. 8-byte LINK frames (a5 op id 02 a b crcLo crcHi; reply 5a status id 02 r0 r1 crc),
// same slow SYS-synchronized PHY as mem_link. Legacy ops 1..4 and 0x50..0x5c behave exactly as in mem_link
// (0x50..0x5c are forwarded to mem_mailbox). Adds MEMV1 ops 0x60..0x67 (see docs/MEMV1_プロトコル仕様_v1確定案_2026-11-05.md).
// Extended requests (RD/WR/CRC32) = 8-byte header (a,b = beats) + 8-byte descriptor {addr32,arg32} (+ WR payload)
// + CRC16 trailer over header[0..5]+descriptor+payload. Extended success replies = 8-byte header + payload + CRC16
// trailer over reply[0..5]+payload (same "bound CRC" construction as TRI_TILE_READ).
module memv1_sys #(
 parameter FAST_REPLY_ENABLE=0,
 parameter TIMEOUT=2700000,         // no-strobe LINK timeout (SYS cycles)
 parameter DEADLINE=2700000,        // wait for the USER completion (SYS cycles)
 parameter [15:0] CAP_MIB=16'd128,
 parameter [31:0] CAPACITY=32'd134217728
)(
 input wire clk,reset_n,arm,bus_clk,dir,input wire[7:0] data_i,
 output reg[7:0] data_o,output wire data_oe,ready,
 // legacy diagnostic commands (mem_mailbox)
 output reg command_start,output reg[7:0] opcode,a,b,
 input wire command_done,input wire[7:0] command_status,input wire[15:0] command_result,
 // raw USER observations (synchronized here)
 input wire cal_user,user_rst_n_user,bist_busy_user,
 // held bundle to the USER bridge
 output reg req_t,cancel_t,output reg[1:0] h_op,output reg[31:0] h_addr,output reg[15:0] h_beats,
 output reg[31:0] h_arg,output reg[23:0] h_tag,
 input wire done_t,input wire[23:0] r_tag,input wire[3:0] r_status,input wire[31:0] r_crc,input wire[15:0] r_beats,
 // staging RAMs
 output reg w_we,output reg[7:0] w_addr,output reg[127:0] w_data,
 output wire[7:0] r_addr,input wire[127:0] r_data,
 output wire[15:0] generation,
 // raw diagnostic bus from the core (any domain), synchronized here: STATUS word 7
 input wire[8:0] diag,
 input wire reply_sample_clk,reply_sample_reset_n,
 output wire reply_read_clk
);
localparam [7:0] OP_CAPS=8'h60,OP_STATUS=8'h61,OP_RD=8'h62,OP_WR=8'h63,OP_FILL=8'h64,OP_COPY=8'h65,OP_CRC32=8'h66,OP_CANCEL=8'h67;
localparam [15:0] FORMAT=16'h4d31;
// ---- free-running observations / generation (no reset: counts reset events too) ----
reg[8:0] diag_s0=0,diag_s1=0,diag_p=0;reg[11:0] uclk_age=12'hfff;
reg[2:0] rst_q=3'b111;reg[1:0] cal_s=0,urn_s=0,bist_s=0,done_s=0;reg cal_p=0,urn_p=0;reg[15:0] gen=0;
always @(posedge clk)begin
 rst_q<={rst_q[1:0],reset_n&&arm};cal_s<={cal_s[0],cal_user};urn_s<={urn_s[0],user_rst_n_user};
 bist_s<={bist_s[0],bist_busy_user};done_s<={done_s[0],done_t};
 cal_p<=cal_s[1];urn_p<=urn_s[1];
 diag_s0<=diag;diag_s1<=diag_s0;diag_p<=diag_s1;
 if(diag_s1[8]!=diag_p[8])uclk_age<=0;else if(uclk_age!=12'hfff)uclk_age<=uclk_age+1'b1;
 if((rst_q[2]&&!rst_q[1])||(cal_p&&!cal_s[1])||(urn_p&&!urn_s[1]))gen<=gen+1'b1;
end
assign generation=gen;
wire user_alive=cal_s[1]&&urn_s[1];
wire gen_event=(cal_p&&!cal_s[1])||(urn_p&&!urn_s[1]);
reg[2:0] clk_sync;reg[1:0] dir_sync;wire rise=clk_sync[1]&&!clk_sync[2];
reg[7:0] request[0:6];reg[7:0] reply[0:5];
reg[12:0] rx_cnt,tx_index,tx_total;
reg valid,pending,prefix,ext_rx;reg[31:0] idle;
reg[15:0] rx_crc,tx_crc,tr_lo;
reg[31:0] pcrc,d_addr,d_arg,reply_crc32;
reg[1:0] ext_kind;reg[8:0] ext_beats;reg[7:0] x_op;reg[8:0] x_beats;reg[12:0] ext_end;
reg[127:0] acc;
reg x_pending,inflight,cancel_wait,done_seen,undef_valid;
reg[7:0] x_seq,cancel_seq;reg x_pref,cancel_pref;reg[23:0] x_tag;
reg[31:0] deadline,undef_addr;reg[15:0] undef_beats,last_status,op_count;
reg[5:0] start_guard;
reg done_ref;
integer j;reg[15:0] reply_crc;
function[15:0] crc;input[15:0] old;input[7:0] byte_value;reg[15:0] v;integer k;
begin v=old^{byte_value,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end endfunction
wire[31:0] pcrc_n;
memv1_crc32b c32(pcrc,data_i,pcrc_n);
wire [7:0] fast_data,fast_r_addr;
wire fast_done,fast_started,fast_progress,fast_error,filter_fault,clean_reply_clk;
reg fast_offer;
reg [1:0] fast_prepare;
(* ASYNC_REG="TRUE" *) reg [1:0] fast_done_sync,fast_started_sync,fast_progress_sync,fast_error_sync,filter_fault_sync;
reg fast_progress_last;
reg [47:0] fast_header;
reg [1:0] fast_kind;
reg [8:0] fast_beats;
reg [31:0] fast_crc32;
reg fast_prefix;
reg [15:0] fast_generation;
// Latch even sub-SYS lock/reset loss: never restart a partially transmitted
// response at byte0 after a pulse that SYS did not sample.
reg sampler_fault;
always @(posedge clk or negedge reset_n or negedge reply_sample_reset_n)begin
 if(!reset_n||!reply_sample_reset_n)sampler_fault<=1;
 else if(!fast_offer&&!valid)sampler_fault<=0;
end
wire sample_async_reset_n=reset_n&&arm&&reply_sample_reset_n;
(* ASYNC_REG="TRUE" *) reg [1:0] sample_release;
(* ASYNC_REG="TRUE" *) reg [1:0] reply_active_sync;
always @(posedge reply_sample_clk or negedge sample_async_reset_n)begin
 if(!sample_async_reset_n)begin sample_release<=0;reply_active_sync<=0;end
 else begin
  sample_release<={sample_release[0],1'b1};
  reply_active_sync<={reply_active_sync[0],fast_offer&&dir};
 end
end
wire filter_reset_n=sample_async_reset_n&&sample_release[1];
wire fast_reset_n=filter_reset_n&&!sampler_fault;
wire fast_valid=fast_reset_n&&fast_offer&&!fast_done&&!fast_error&&!filter_fault&&fast_generation==gen;
assign ready=reset_n&&arm&&valid&&(!FAST_REPLY_ENABLE||fast_valid);
assign data_oe=reset_n&&arm&&dir&&dir_sync[1]&&valid&&(!FAST_REPLY_ENABLE||fast_valid);
assign reply_read_clk=FAST_REPLY_ENABLE?clean_reply_clk:clk;
generate if(FAST_REPLY_ENABLE)begin: fast_reply
 reply_clock_filter conditioner(reply_sample_clk,filter_reset_n,bus_clk,reply_active_sync[1],clean_reply_clk,filter_fault);
 memv1_reply_raw serializer(clean_reply_clk,fast_reset_n&&fast_offer,dir,
  fast_header,fast_kind,fast_beats,fast_crc32,fast_prefix,r_data,
  fast_data,fast_r_addr,fast_done,fast_started,fast_progress,fast_error);
end else begin: slow_reply
 assign fast_data=0;assign fast_r_addr=0;assign fast_done=0;assign fast_started=0;
 assign fast_progress=0;assign fast_error=0;assign clean_reply_clk=0;assign filter_fault=0;
end endgenerate
wire prefacing=prefix&&tx_index<8;
wire[12:0] li=tx_index-(prefix?13'd8:13'd0);
wire[12:0] pi=li-13'd8;
assign r_addr=FAST_REPLY_ENABLE?fast_r_addr:pi[11:4];
always @*begin
 reply_crc=16'hffff;for(j=0;j<6;j=j+1)reply_crc=crc(reply_crc,reply[j]);
 data_o=8'h00;
 if(prefacing)data_o=8'hc3;
 else if(li<6)data_o=reply[li[2:0]];
 else if(li==6)data_o=reply_crc[7:0];
 else if(li==7)data_o=reply_crc[15:8];
 else if(ext_kind==2'd1)begin
  if(li<13'd8+{ext_beats,4'b0})data_o=r_data[8*pi[3:0]+:8];
  else if(li==tx_total-13'd2)data_o=tx_crc[7:0];
  else data_o=tx_crc[15:8];
 end else if(ext_kind==2'd2)begin
  case(li)
  13'd8:data_o=reply_crc32[7:0];13'd9:data_o=reply_crc32[15:8];
  13'd10:data_o=reply_crc32[23:16];13'd11:data_o=reply_crc32[31:24];
  13'd12:data_o=tx_crc[7:0];default:data_o=tx_crc[15:8];
  endcase
 end
 if(FAST_REPLY_ENABLE)data_o=fast_data;
end
wire[63:0] d_end={32'b0,d_addr}+({55'b0,x_beats}<<4);
wire range_ok=d_addr[3:0]==0&&x_beats!=0&&x_beats<=9'd256&&d_end<={32'b0,CAPACITY};
wire bist_active=bist_s[1]||start_guard!=0;
wire hdr_ok=request[0]==8'ha5&&request[3]==8'd2&&request[6]==rx_crc[7:0]&&data_i==rx_crc[15:8];
wire[7:0] opc=request[1]&8'h7f;
wire[15:0] hdr_beats={request[5],request[4]};
// ---- reply helper: sets the 8-byte header and arms the transmitter ----
task set_reply;input[7:0] status;input[15:0] r45;input[7:0] seq;input pref;input[1:0] kind;input[8:0] nbeats;
begin
 reply[0]<=8'h5a;reply[1]<=status;reply[2]<=seq;reply[3]<=8'd2;reply[4]<=r45[7:0];reply[5]<=r45[15:8];
 ext_kind<=kind;ext_beats<=nbeats;
 tx_total<=(kind==2'd1)?(13'd10+{nbeats,4'b0}):(kind==2'd2)?13'd14:13'd8;
 // A STALE reply may be created on the very edge that advances generation.
 fast_generation<=gen+(gen_event?16'd1:16'd0);
 valid<=1;tx_index<=0;prefix<=pref;
end endtask
task finish_x;input[7:0] status;
begin
 x_pending<=0;last_status<={8'b0,status};op_count<=op_count+1'b1;
 if(x_op==OP_WR&&(status==8'd8||status==8'd9||status==8'd4))begin
  undef_valid<=1;undef_addr<=h_addr;undef_beats<=(status==8'd8||status==8'd9)?r_beats:h_beats;end
 if(cancel_wait)begin
  cancel_wait<=0;
  if(status==8'd4||status==8'd10)set_reply(status,16'd0,cancel_seq,cancel_pref,2'd0,9'd0);
  else set_reply(8'd0,(status==8'd8)?16'd1:16'd2,cancel_seq,cancel_pref,2'd0,9'd0);
 end else if(status==8'd0&&x_op==OP_RD)begin
  reply_crc32<=0;set_reply(8'd0,gen,x_seq,x_pref,2'd1,h_beats[8:0]);
 end else if(status==8'd0&&x_op==OP_CRC32)begin
  reply_crc32<=r_crc;set_reply(8'd0,gen,x_seq,x_pref,2'd2,9'd0);
 end else if(status==8'd0)set_reply(8'd0,gen,x_seq,x_pref,2'd0,9'd0);
 else if(status==8'd8)set_reply(status,r_beats,x_seq,x_pref,2'd0,9'd0);
 else set_reply(status,16'd0,x_seq,x_pref,2'd0,9'd0);
end endtask
always @(posedge clk or negedge reset_n)begin
if(!reset_n)begin
 fast_offer<=0;fast_prepare<=0;fast_done_sync<=0;fast_started_sync<=0;fast_progress_sync<=0;fast_error_sync<=0;filter_fault_sync<=0;fast_progress_last<=0;
 fast_header<=0;fast_kind<=0;fast_beats<=0;fast_crc32<=0;fast_prefix<=0;fast_generation<=0;
 clk_sync<=0;dir_sync<=0;rx_cnt<=0;tx_index<=0;tx_total<=8;
 valid<=0;pending<=0;prefix<=0;ext_rx<=0;idle<=0;rx_crc<=16'hffff;tr_lo<=0;
 command_start<=0;opcode<=0;a<=0;b<=0;
 pcrc<=32'hffffffff;d_addr<=0;d_arg<=0;reply_crc32<=0;ext_kind<=0;ext_beats<=0;x_op<=0;x_beats<=0;ext_end<=0;
 acc<=0;x_pending<=0;inflight<=0;cancel_wait<=0;done_seen<=0;undef_valid<=0;
 x_seq<=0;cancel_seq<=0;x_pref<=0;cancel_pref<=0;x_tag<=0;deadline<=0;undef_addr<=0;undef_beats<=0;
 last_status<=0;op_count<=0;start_guard<=0;done_ref<=0;
 req_t<=0;cancel_t<=0;h_op<=0;h_addr<=0;h_beats<=0;h_arg<=0;h_tag<=0;
 w_we<=0;w_addr<=0;w_data<=0;
 for(j=0;j<6;j=j+1)reply[j]<=0;
end else begin
 fast_error_sync<={fast_error_sync[0],fast_error};filter_fault_sync<={filter_fault_sync[0],filter_fault};
 fast_done_sync<={fast_done_sync[0],fast_done};fast_started_sync<={fast_started_sync[0],fast_started};
 fast_progress_sync<={fast_progress_sync[0],fast_progress};fast_progress_last<=fast_progress_sync[1];
 clk_sync<={clk_sync[1:0],bus_clk};dir_sync<={dir_sync[0],dir};command_start<=0;w_we<=0;
 if(start_guard!=0)start_guard<=start_guard-1'b1;
 if(!x_pending&&!inflight)done_ref<=done_s[1];
 if(!arm||idle>=TIMEOUT-1)begin
  fast_offer<=0;fast_prepare<=0;
  rx_cnt<=0;tx_index<=0;valid<=0;pending<=0;prefix<=0;ext_rx<=0;idle<=0;rx_crc<=16'hffff;
  x_pending<=0;cancel_wait<=0;
 end else begin
  idle<=idle+1;
  if(FAST_REPLY_ENABLE)begin
   if(fast_progress_sync[1]!=fast_progress_last)idle<=0;
   if(!valid)begin fast_offer<=0;fast_prepare<=0;end
   else if(!fast_offer)begin
    if(fast_prepare==0)begin
     fast_header<={reply[5],reply[4],reply[3],reply[2],reply[1],reply[0]};
     fast_kind<=ext_kind;fast_beats<=ext_beats;fast_crc32<=reply_crc32;fast_prefix<=prefix;
     fast_prepare<=1;
    end else if(fast_prepare==1)fast_prepare<=2;
    else begin fast_offer<=1;fast_prepare<=0;end
   end else if(fast_done_sync[1]||fast_error_sync[1]||filter_fault_sync[1]||fast_generation!=gen||
               (fast_started_sync[1]&&!dir&&!dir_sync[1])||sampler_fault)begin
    fast_offer<=0;valid<=0;prefix<=0;fast_prepare<=0;
   end
  end
  // ---- legacy mailbox completion ----
  if(pending&&command_done)begin
   pending<=0;valid<=1;reply[1]<=command_status;reply[4]<=command_result[7:0];reply[5]<=command_result[15:8];
   ext_kind<=0;tx_total<=8;end
  // ---- MEMV1 completion from USER ----
  if(x_pending||inflight)begin
   if(done_s[1]!=done_ref&&!done_seen)done_seen<=1;
   else if(done_seen)begin
    done_seen<=0;done_ref<=done_s[1];
    if(r_tag==h_tag)begin inflight<=0;if(x_pending)finish_x({4'b0,r_status});end
   end
  end
  if(inflight&&urn_p&&!urn_s[1])inflight<=0;
  if(x_pending)begin
   deadline<=deadline+1;
   if(gen_event)finish_x(8'd10);
   else if(deadline>=DEADLINE-1&&!(done_s[1]!=done_ref))finish_x(8'd4);
  end
  if(dir_sync[1]&&rx_cnt!=0)begin rx_cnt<=0;ext_rx<=0;rx_crc<=16'hffff;end
  if(rise)begin
   idle<=0;
   if(!dir&&!dir_sync[1]&&!valid&&!pending)begin
    // ---------------- header bytes ----------------
    if(rx_cnt<13'd7)request[rx_cnt[2:0]]<=data_i;
    if(rx_cnt<13'd6)rx_crc<=crc(rx_crc,data_i);
    if(rx_cnt<13'd7)rx_cnt<=rx_cnt+1'b1;
    else if(rx_cnt==13'd7)begin
     if(x_pending)begin
      // only CANCEL is accepted while a MEMV1 command runs; anything else is dropped silently
      rx_cnt<=0;rx_crc<=16'hffff;
      if(hdr_ok&&opc==OP_CANCEL&&request[4]==0&&request[5]==0&&!cancel_wait)begin
       cancel_t<=~cancel_t;cancel_wait<=1;cancel_seq<=request[2];cancel_pref<=request[1][7];end
     end else begin
      rx_cnt<=0;
      if(!hdr_ok)begin rx_crc<=16'hffff;set_reply(8'd1,16'd0,request[2],1'b0,2'd0,9'd0);end
      else if(opc==OP_RD||opc==OP_WR||opc==OP_CRC32)begin
       if(hdr_beats==0||hdr_beats>16'd256)begin rx_crc<=16'hffff;set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);end
       else begin
        // header accepted: receive descriptor (+payload) and trailer; rx_crc keeps running
        ext_rx<=1;rx_cnt<=13'd8;x_op<=opc;x_beats<=hdr_beats[8:0];pcrc<=32'hffffffff;
        ext_end<=(opc==OP_WR)?(13'd16+{hdr_beats[8:0],4'b0}):13'd16;
       end
      end else begin
       rx_crc<=16'hffff;
       case(opc)
       8'd1:set_reply(8'd0,16'h5054,request[2],request[1][7],2'd0,9'd0);
       8'd2:set_reply(8'd0,{request[5],request[4]},request[2],request[1][7],2'd0,9'd0);
       8'd3:set_reply(8'd0,{~request[5],~request[4]},request[2],request[1][7],2'd0,9'd0);
       8'd4:set_reply(8'd0,16'h0108,request[2],request[1][7],2'd0,9'd0);
       8'h50,8'h51,8'h52,8'h53,8'h54,8'h55,8'h56,8'h57,8'h58,8'h59,8'h5a,8'h5b,8'h5c:begin
        if(opc==8'h57&&inflight)set_reply(8'd6,16'd0,request[2],request[1][7],2'd0,9'd0);
        else begin
         set_reply(8'd0,16'd0,request[2],request[1][7],2'd0,9'd0);
         valid<=0;opcode<=opc;a<=request[4];b<=request[5];command_start<=1;pending<=1;
         if(opc==8'h57)start_guard<=6'd63;
        end end
       OP_CAPS:begin
        if(request[5]!=0)set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);
        else case(request[4])
        8'd0:set_reply(8'd0,FORMAT,request[2],request[1][7],2'd0,9'd0);
        8'd1:set_reply(8'd0,16'h0100,request[2],request[1][7],2'd0,9'd0);
        8'd2:set_reply(8'd0,CAP_MIB,request[2],request[1][7],2'd0,9'd0);
        8'd3:set_reply(8'd0,16'd16,request[2],request[1][7],2'd0,9'd0);
        8'd4:set_reply(8'd0,16'd256,request[2],request[1][7],2'd0,9'd0);
        8'd5:set_reply(8'd0,16'h0073,request[2],request[1][7],2'd0,9'd0);
        8'd6:set_reply(8'd0,16'd1,request[2],request[1][7],2'd0,9'd0);
        8'd7:set_reply(8'd0,16'h000c,request[2],request[1][7],2'd0,9'd0);
        default:set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);
        endcase
       end
       OP_STATUS:begin
        if(request[5]!=0)set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);
        else case(request[4])
        8'd0:set_reply(8'd0,{3'b0,undef_valid,bist_active,inflight,urn_s[1],cal_s[1]},request[2],request[1][7],2'd0,9'd0);
        8'd1:set_reply(8'd0,gen,request[2],request[1][7],2'd0,9'd0);
        8'd2:set_reply(8'd0,last_status,request[2],request[1][7],2'd0,9'd0);
        8'd3:set_reply(8'd0,op_count,request[2],request[1][7],2'd0,9'd0);
        8'd4:set_reply(8'd0,undef_addr[15:0],request[2],request[1][7],2'd0,9'd0);
        8'd5:set_reply(8'd0,undef_addr[31:16],request[2],request[1][7],2'd0,9'd0);
        8'd6:set_reply(8'd0,undef_beats,request[2],request[1][7],2'd0,9'd0);
        // 7: raw signals {b8 USER clock alive, b7 recal epoch done, b6 user_abort, b5 reset_hold==0, b4 calibrated, b3 user_reset_n, b2 ip_user_reset, b1 controller_reset_n, b0 pll_lock}
        8'd7:set_reply(8'd0,{6'b0,uclk_age<12'd2048,diag_s1[7:0]},request[2],request[1][7],2'd0,9'd0);
        default:set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);
        endcase
       end
       OP_CANCEL:begin
        if(request[4]!=0||request[5]!=0)set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);
        else set_reply(8'd0,16'd0,request[2],request[1][7],2'd0,9'd0);
       end
       OP_FILL,OP_COPY:set_reply(8'd2,16'd0,request[2],request[1][7],2'd0,9'd0);
       default:set_reply(8'd2,16'd0,request[2],request[1][7],2'd0,9'd0);
       endcase
      end
     end
    end else if(ext_rx)begin
     // ---------------- descriptor / payload / trailer ----------------
     rx_cnt<=rx_cnt+1'b1;
     if(rx_cnt<ext_end)rx_crc<=crc(rx_crc,data_i);
     case(rx_cnt)
     13'd8:d_addr[7:0]<=data_i;13'd9:d_addr[15:8]<=data_i;13'd10:d_addr[23:16]<=data_i;13'd11:d_addr[31:24]<=data_i;
     13'd12:d_arg[7:0]<=data_i;13'd13:d_arg[15:8]<=data_i;13'd14:d_arg[23:16]<=data_i;13'd15:d_arg[31:24]<=data_i;
     default:;
     endcase
     if(rx_cnt>=13'd16&&rx_cnt<ext_end)begin
      pcrc<=pcrc_n;
      acc[8*(rx_cnt[3:0])+:8]<=data_i;
      if(rx_cnt[3:0]==4'd15)begin w_we<=1;w_addr<=(rx_cnt-13'd16)>>4;w_data<={data_i,acc[119:0]};end
     end
     if(rx_cnt==ext_end)tr_lo<={8'b0,data_i};
     if(rx_cnt==ext_end+13'd1)begin
      // complete frame received: decide
      rx_cnt<=0;ext_rx<=0;rx_crc<=16'hffff;
      if({data_i,tr_lo[7:0]}!=rx_crc)set_reply(8'd7,16'd0,request[2],request[1][7],2'd0,9'd0);
      else if(!range_ok||(x_op==OP_RD&&d_arg!=0))set_reply(8'd3,16'd0,request[2],request[1][7],2'd0,9'd0);
      else if(x_op==OP_WR&&~pcrc!=d_arg)set_reply(8'd7,16'd0,request[2],request[1][7],2'd0,9'd0);
      else if(!user_alive)set_reply(8'd5,16'd0,request[2],request[1][7],2'd0,9'd0);
      else if(bist_active||inflight)set_reply(8'd6,16'd0,request[2],request[1][7],2'd0,9'd0);
      else begin
       x_pending<=1;inflight<=1;deadline<=0;done_seen<=0;
       x_seq<=request[2];x_pref<=request[1][7];x_tag<={gen,request[2]};
       h_op<=(x_op==OP_RD)?2'd0:(x_op==OP_WR)?2'd1:2'd2;
       h_addr<=d_addr;h_beats<={7'b0,x_beats};h_arg<=(x_op==OP_CRC32)?d_arg:32'd0;h_tag<={gen,request[2]};
       req_t<=~req_t;
      end
     end
    end
   end else if(!FAST_REPLY_ENABLE&&dir&&dir_sync[1]&&valid)begin
    if(!prefacing)begin
     if(li==13'd7)tx_crc<=reply_crc;
     else if(li>=13'd8&&li<tx_total-13'd2)tx_crc<=crc(tx_crc,data_o);
    end
    if(!prefacing&&li==tx_total-13'd1)begin valid<=0;tx_index<=0;prefix<=0;end
    else tx_index<=tx_index+1'b1;
   end
  end
 end
end
end
endmodule
