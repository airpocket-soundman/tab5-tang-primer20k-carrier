// Experimental autonomous4E30 endpoint; existing4E24 endpoint is unchanged.
module npu_ddr_sys_autonomous #(parameter TIMEOUT=27000000,parameter REQUEST_DATA_PIPELINE=0,parameter INCLUDE_MATRIX=0)(
 input wire clk,reset_n,arm,bus_clk,dir,input wire[7:0] data_i,
 output reg[7:0] data_o,output wire data_oe,ready,
 input wire memory_ready,input wire[15:0] generation,input wire arbiter_fault,input wire arbiter_active,
 output reg conv_start,conv_abort,conv_clear,output reg[415:0] descriptor,
 input wire conv_start_ready,conv_busy,conv_done,conv_error,conv_quarantined,input wire[3:0] conv_error_code,
 input wire[31:0] kernel_cycles,ddr_wait_cycles,total_cycles,
 output reg req_t,cancel_t,output reg[1:0] h_op,output reg[31:0] h_addr,h_arg,output reg[15:0] h_beats,output reg[23:0] h_tag,
 input wire done_t,input wire[23:0] r_tag,input wire[3:0] r_status,input wire[15:0] r_beats,
 output reg w_we,output reg[7:0] w_addr,output reg[127:0] w_data,output wire[7:0] r_addr,input wire[127:0] r_data,
 output reg matrix_start,output reg[287:0] matrix_job,
 input wire matrix_start_ready,matrix_busy,matrix_done,matrix_error,matrix_quarantined,matrix_result_valid,
 input wire[3:0] matrix_error_code,input wire matrix_progress,
 input wire[31:0] matrix_accepted,matrix_completed,
 output wire matrix_done_ack,
 output reg local_start,local_abort,local_clear,
 input wire local_start_ready,local_running,input wire[15:0] local_status,
 output wire[5:0] monitor_index,input wire[31:0] monitor_data);
 localparam RX=0,DISPATCH=1,WADDR=2,WWAIT=3,WPACK=4,WACK=5,MEMWAIT=6,MEMCAPTURE=7,RADDR=8,RWAIT=9,RCRC=10,CONVWAIT=11,RESP=12,CLEARWAIT=13,MATRIXWAIT=14;
 // Optional bundled DATA/CLK alignment, matching the existing GFX receiver.
 // Default0 retains the raw-data4E21 path. Positive launch requires DATA setup.
 reg[7:0] data_meta,data_capture;
 wire[7:0] request_byte=REQUEST_DATA_PIPELINE?data_capture:data_i;
 reg[3:0] state;reg[2:0] cs;reg[1:0] ds,done_sync;wire rise=cs[1]&&!cs[2];
 reg[7:0] header[0:5],first[0:51],reply[0:5];reg[7:0] packet[0:2047],packet_q;reg[10:0] packet_address;
 reg[12:0] index,length,tx_index,reply_bytes;reg[15:0] crc,low_crc,reply_header_crc,reply_tail_crc,saved_generation;
 reg[31:0] idle;reg[15:0] count,word_index,byte_index;reg[3:0] pack_slot,scan_slot;reg[127:0] pack;reg[7:0] scan_address;reg[1:0] settle;
 reg bound;reg[31:0] session_token;reg last_ready;
 reg done_ref;reg[23:0] next_tag;reg[7:0] current_op;integer i;
 wire[7:0] op=header[1];wire[15:0] arg={header[5],header[4]};
 wire[31:0] address={first[3],first[2],first[1],first[0]};wire[15:0] bytes_arg={first[5],first[4]};
 wire[63:0] mem_end={32'd0,address}+{48'd0,bytes_arg};
 function[15:0] crcbyte;input[15:0] c;input[7:0] b;reg[15:0] v;integer k;begin v=c^{b,8'd0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crcbyte=v;end endfunction
 function[15:0] hcrc;input[7:0] status;input[15:0] value;reg[15:0] c;begin c=crcbyte(16'hffff,8'h5a);c=crcbyte(c,status);c=crcbyte(c,header[2]);c=crcbyte(c,2);c=crcbyte(c,value[7:0]);hcrc=crcbyte(c,value[15:8]);end endfunction
 task respond;input[7:0] status;input[15:0] value;begin reply[0]<=8'h5a;reply[1]<=status;reply[2]<=header[2];reply[3]<=2;reply[4]<=value[7:0];reply[5]<=value[15:8];reply_header_crc<=hcrc(status,value);reply_tail_crc<=hcrc(status,value);reply_bytes<=0;tx_index<=0;state<=RESP;idle<=0;end endtask
 task issue;input[1:0] operation;begin h_op<=operation;h_addr<=address;h_beats<=bytes_arg>>4;h_arg<=0;h_tag<=next_tag;next_tag<=next_tag+1'b1;req_t<=~req_t;done_ref<=done_sync[1];saved_generation<=generation;state<=MEMWAIT;idle<=0;end endtask
 // Empty RX is a quiescent session, not an incomplete transfer. In-flight
 // loader/arbiter work must retain the ordinary timeout/cancel protection.
 wire healthy_idle=state==RX&&index==0&&(local_running||(!conv_busy&&!arbiter_active));
 assign monitor_index=address[6:1];
 assign matrix_done_ack=state==MATRIXWAIT&&matrix_done;
 wire[12:0] payload_index=tx_index-8;
 assign r_addr=state==RESP?(tx_index<8?8'd0:payload_index[11:4]):scan_address;
 assign ready=reset_n&&arm&&state==RESP;
 assign data_oe=ready&&dir&&ds[1];
 wire[12:0] total=8+(reply_bytes?reply_bytes+2:0);
 always @*begin
  data_o=0;if(tx_index<6)data_o=reply[tx_index];else if(tx_index==6)data_o=reply_header_crc[7:0];else if(tx_index==7)data_o=reply_header_crc[15:8];
  else if(tx_index<8+reply_bytes)data_o=r_data[payload_index[3:0]*8+:8];else if(tx_index==8+reply_bytes)data_o=reply_tail_crc[7:0];else data_o=reply_tail_crc[15:8];
 end
 always @(posedge clk)begin
  packet_q<=packet[packet_address];
  if(state==RX && rise && !dir && !ds[1] && index>=16 && index<8+length && op==8'h71)packet[index-16]<=request_byte;
 end
 always @(posedge clk)begin
  if(!reset_n || !arm)begin
   state<=RX;local_start<=0;local_abort<=0;local_clear<=0;matrix_start<=0;matrix_job<=0;data_meta<=0;data_capture<=0;cs<=0;ds<=0;done_sync<=0;index<=0;length<=0;tx_index<=0;reply_bytes<=0;crc<=16'hffff;low_crc<=0;reply_header_crc<=0;reply_tail_crc<=0;idle<=0;count<=0;word_index<=0;byte_index<=0;pack_slot<=0;scan_slot<=0;pack<=0;scan_address<=0;packet_address<=0;settle<=0;done_ref<=0;next_tag<=24'h800001;current_op<=0;saved_generation<=0;bound<=0;session_token<=0;last_ready<=0;
   conv_start<=0;matrix_start<=0;conv_abort<=0;conv_clear<=0;descriptor<=0;req_t<=0;cancel_t<=0;h_op<=0;h_addr<=0;h_beats<=0;h_arg<=0;h_tag<=0;w_we<=0;w_addr<=0;w_data<=0;
   for(i=0;i<6;i=i+1)begin header[i]<=0;reply[i]<=0;end
   for(i=0;i<52;i=i+1)first[i]<=0;
  end else begin
   last_ready<=memory_ready;if(last_ready&&!memory_ready)begin bound<=0;session_token<=0;end
   data_meta<=data_i;data_capture<=data_meta;cs<={cs[1:0],bus_clk};ds<={ds[0],dir};done_sync<={done_sync[0],done_t};local_start<=0;local_abort<=0;local_clear<=0;conv_start<=0;matrix_start<=0;conv_abort<=0;conv_clear<=0;w_we<=0;if(healthy_idle||(state==MATRIXWAIT&&matrix_progress))idle<=0;else idle<=idle+1'b1;
   if(idle>=TIMEOUT-1&&!healthy_idle&&!(state==MATRIXWAIT&&matrix_progress))begin state<=RX;index<=0;crc<=16'hffff;idle<=0;if(!local_running)begin conv_abort<=1;cancel_t<=~cancel_t;end end
   else case(state)
    RX:begin
     if(ds[1]&&index!=0)begin index<=0;crc<=16'hffff;end
     if(rise&&!dir&&!ds[1])begin
      idle<=0;if(index<6)begin header[index]<=request_byte;crc<=crcbyte(crc,request_byte);end
      if(index==6)low_crc<=request_byte;
      if(index==7)begin
       if(header[0]!=8'ha5||header[3]!=2||{request_byte,low_crc[7:0]}!=crc||header[1][7])respond(1,0);
       else if(arg>2051)respond(3,0);else begin length<=arg;if(arg==0)state<=DISPATCH;end
      end else if(index>=8 && index<8+length)begin crc<=crcbyte(crc,request_byte);if(index<60)first[index-8]<=request_byte;end
      else if(index==8+length&&index>=8)low_crc<=request_byte;
      else if(index==9+length&&index>=9)begin if({request_byte,low_crc[7:0]}!=crc)respond(1,0);else state<=DISPATCH;end
      index<=index+1'b1;
     end
    end
    DISPATCH:begin
     idle<=0;current_op<=op;
     case(op)
      1:if(length)respond(3,0);else respond(0,16'h5054);
      8'h50:if(length)respond(3,0);else respond(0,16'h4e30);
      8'h64:if(length)respond(3,0);else respond(0,{bound,6'd0,arbiter_fault,conv_error_code,conv_quarantined,conv_error,conv_busy,memory_ready});
      8'h65:if(length)respond(3,0);else respond(0,kernel_cycles[15:0]);
      8'h66:if(length)respond(3,0);else respond(0,kernel_cycles[31:16]);
      8'h69:if(length)respond(3,0);else respond(0,ddr_wait_cycles[15:0]);
      8'h6a:if(length)respond(3,0);else respond(0,ddr_wait_cycles[31:16]);
      8'h6b:if(length)respond(3,0);else respond(0,total_cycles[15:0]);
      8'h6c:if(length)respond(3,0);else respond(0,total_cycles[31:16]);
      8'h75:if(local_running)respond(4,0);else if(length!=4 || !memory_ready || arbiter_fault || arbiter_active || conv_busy)respond(3,0);else begin bound<=1;session_token<=address;respond(0,0);end
      8'h76:if(length)respond(3,0);else respond(0,session_token[15:0]);
      8'h77:if(length)respond(3,0);else respond(0,session_token[31:16]);
      8'h74:if(length)respond(3,0);else respond(0,generation);
      8'h67:if(local_running)respond(4,0);else if(length)respond(3,0);else if(matrix_error||matrix_quarantined)respond(7,0);else begin conv_abort<=1;settle<=3;state<=CLEARWAIT;end
      8'h68:if(local_running)respond(4,0);else if(length!=52 || first[0]<1||first[0]>16||first[1]<1||first[1]>8||first[2]<1||first[2]>16||first[3]<1||first[3]>16 || (first[4]!=1&&first[4]!=3)||(first[5]!=1&&first[5]!=2)||first[6]>7||first[7]!=0)respond(3,0);
       else if(!bound)respond(9,0);else if(!memory_ready||arbiter_fault||arbiter_active||!conv_start_ready)respond(4,0);
       else begin for(i=0;i<52;i=i+1)descriptor[i*8+:8]<=first[i];conv_start<=1;saved_generation<=generation;state<=CONVWAIT;end
      8'h78:if(local_running)respond(4,0);else if(!INCLUDE_MATRIX)respond(2,0);else if(length!=36)respond(3,0);
       else if(!bound)respond(9,0);else if(!memory_ready||arbiter_fault||arbiter_active||conv_busy||!matrix_start_ready)respond(4,0);
       else begin for(i=0;i<36;i=i+1)matrix_job[i*8+:8]<=first[i];matrix_start<=1;saved_generation<=generation;state<=MATRIXWAIT;end
      8'h79:if(!INCLUDE_MATRIX)respond(2,0);else if(length)respond(3,0);else respond(0,{4'd0,matrix_error_code,3'd0,matrix_result_valid,matrix_quarantined,matrix_error,matrix_busy,matrix_start_ready});
      8'h7a:if(!INCLUDE_MATRIX)respond(2,0);else if(length)respond(3,0);else respond(0,matrix_accepted[15:0]);
      8'h7b:if(!INCLUDE_MATRIX)respond(2,0);else if(length)respond(3,0);else respond(0,matrix_accepted[31:16]);
      8'h7c:if(!INCLUDE_MATRIX)respond(2,0);else if(length)respond(3,0);else respond(0,matrix_completed[15:0]);
      8'h7d:if(!INCLUDE_MATRIX)respond(2,0);else if(length)respond(3,0);else respond(0,matrix_completed[31:16]);
      8'h7e:if(length!=8)respond(3,0);
       else if(address==0)begin if({first[7],first[6],first[5],first[4]}!=0)respond(3,0);else respond(0,local_status);end
       else if(!bound||{first[7],first[6],first[5],first[4]}!=session_token)respond(9,0);
       else case(address)
        1:if(!memory_ready||arbiter_fault||arbiter_active||!local_start_ready)respond(4,0);else begin local_start<=1;respond(0,0);end
        2:begin local_abort<=1;respond(0,local_status);end
        3:if(local_running||arbiter_active||conv_busy||matrix_busy)respond(4,0);else begin local_clear<=1;respond(0,0);end
        default:respond(3,0);
       endcase
      8'h7f:if(length!=4||address>127)respond(3,0);else respond(0,address[0]?monitor_data[31:16]:monitor_data[15:0]);
      8'h70,8'h71:if(local_running)respond(4,0);else if((op==8'h70&&length!=8)||(op==8'h71&&length!=8+bytes_arg)||bytes_arg<16||bytes_arg[3:0]!=0||address[3:0]!=0||mem_end>64'd134217728||first[6]!=0||first[7]!=0||(op==8'h70&&bytes_arg>1024)||(op==8'h71&&bytes_arg>2032))respond(3,0);
       else if(!bound)respond(9,0);else if(!memory_ready||arbiter_fault||arbiter_active||conv_busy)respond(4,0);
       else begin count<=bytes_arg;word_index<=0;byte_index<=0;pack_slot<=0;pack<=0;scan_address<=0;if(op==8'h70)issue(0);else begin packet_address<=0;state<=WADDR;end end
      default:respond(2,0);
     endcase
    end
    WADDR:begin packet_address<=byte_index[10:0];state<=WWAIT;end
    WWAIT:state<=WPACK;
    WPACK:begin pack[pack_slot*8+:8]<=packet_q;if(pack_slot==15)begin w_we<=1;w_addr<=word_index[7:0];w_data<={packet_q,pack[119:0]};word_index<=word_index+1'b1;pack_slot<=0;end else pack_slot<=pack_slot+1'b1;state<=WACK;end
    WACK:if(byte_index+1==count)issue(1);else begin byte_index<=byte_index+1'b1;state<=WADDR;end
    MEMWAIT:if(!memory_ready||generation!=saved_generation)respond(8,0);else if(arbiter_fault)respond(7,0);else if(done_sync[1]!=done_ref)begin done_ref<=done_sync[1];state<=MEMCAPTURE;end
    MEMCAPTURE:if(!memory_ready||generation!=saved_generation)respond(8,0);else if(r_tag!=h_tag||r_status!=0||r_beats!=h_beats)respond(7,0);
     else if(current_op==8'h71)respond(0,0);else begin respond(0,count);reply_bytes<=count;word_index<=0;scan_address<=0;settle<=2;scan_slot<=0;state<=RWAIT;end
    RADDR:begin scan_address<=word_index[7:0];settle<=2;state<=RWAIT;end
    RWAIT:if(settle)settle<=settle-1'b1;else begin scan_slot<=0;state<=RCRC;end
    RCRC:begin reply_tail_crc<=crcbyte(reply_tail_crc,r_data[scan_slot*8+:8]);if(scan_slot==15)begin if((word_index+1)*16==count)begin state<=RESP;tx_index<=0;end else begin word_index<=word_index+1'b1;state<=RADDR;end end else scan_slot<=scan_slot+1'b1;end
    CONVWAIT:if(!memory_ready||generation!=saved_generation)begin conv_abort<=1;respond(8,0);end else if(arbiter_fault||conv_quarantined)respond(7,0);else if(conv_error)respond(5,0);else if(conv_done)respond(0,0);
    MATRIXWAIT:if(!memory_ready||generation!=saved_generation)begin conv_abort<=1;respond(8,0);end
     else if(arbiter_fault||matrix_quarantined)begin conv_abort<=1;respond(7,0);end
     else if(matrix_done)begin if(matrix_error)respond(5,{12'd0,matrix_error_code});else if(!matrix_result_valid)respond(5,16'd9);else respond(0,0);end
    CLEARWAIT:if(settle)settle<=settle-1'b1;else if(conv_quarantined||arbiter_fault)respond(7,0);else if(!conv_busy)begin conv_clear<=1;respond(0,0);end
    RESP:if(rise&&dir&&ds[1])begin idle<=0;if(tx_index+1==total)begin state<=RX;index<=0;crc<=16'hffff;tx_index<=0;end else tx_index<=tx_index+1'b1;end
    default:begin state<=RX;index<=0;crc<=16'hffff;conv_abort<=1;cancel_t<=~cancel_t;end
   endcase
  end
 end
endmodule
