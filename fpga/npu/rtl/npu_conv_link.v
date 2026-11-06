// Experimental NPU-CONV-v1, SYS sampled GPIO LINK. CRC-staged upload packets.
// Standard LINK v2 header, capability4e10. Separate from GFX/MEM bitstreams.
module npu_conv_link #(parameter TIMEOUT=27000000)(
 input wire clk,reset_n,arm,bus_clk,dir,input wire[7:0] data_i,
 output reg[7:0] data_o,output wire data_oe,ready);
 localparam RX=0,DISPATCH=1,CFGWAIT=2,UPADDR=3,UPWAIT=4,UPSEND=5,UPACK=6,UPCHECK=7,
  RUNWAIT=8,READREQ=9,READWAIT=10,READCRC=11,RESP=12,ABORTWAIT=13;
 reg[3:0] state;reg[2:0] cs;reg[1:0] ds;wire rise=cs[1]&&!cs[2];
 reg[7:0] header[0:5],first[0:8],reply[0:5];
 reg[12:0] index,length,tx_index,reply_bytes;reg[15:0] crc,header_crc,low_crc,reply_header_crc,reply_tail_crc;
 reg[31:0] idle;reg[7:0] packet[0:2047];reg[10:0] packet_read_address;reg[7:0] packet_q;
 reg[31:0] outmem[0:255],outq;wire[7:0] out_address=tx_index<8?0:(tx_index-8)>>2;
 reg engine_abort,load_start,upload_valid,upload_kind,engine_start,read_enable;
 reg[4:0] ic,oh,ow;reg[3:0] oc;reg[1:0] kernel,stride;reg[5:0] ih,iw;reg first_block,final_block;
 reg[14:0] upload_address;reg signed[7:0] upload_data;wire upload_ready,busy,block_done,output_valid,error;
 wire[2:0] error_code;wire[31:0] compute_cycles;reg[10:0] read_address;wire read_valid;wire signed[31:0] read_data;
 reg[15:0] upload_base,upload_count,upload_index,read_base,read_count,read_index;
 reg[1:0] settle,crc_byte_index;reg[31:0] captured_word;
 wire[7:0] op=header[1];wire[15:0] arg={header[5],header[4]};
 wire[7:0] fault_status=error_code==3?8'd5:(error_code==1?8'd3:8'd4);
 integer i;
 function[15:0] crcbyte;input[15:0] c;input[7:0] b;reg[15:0] v;integer k;
 begin v=c^{b,8'd0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crcbyte=v;end endfunction
 function[15:0] hcrc;input[7:0] status;input[15:0] value;reg[15:0] c;
 begin c=crcbyte(16'hffff,8'h5a);c=crcbyte(c,status);c=crcbyte(c,header[2]);c=crcbyte(c,8'd2);c=crcbyte(c,value[7:0]);hcrc=crcbyte(c,value[15:8]);end endfunction
 task respond;input[7:0] status;input[15:0] value;
 begin reply[0]<=8'h5a;reply[1]<=status;reply[2]<=header[2];reply[3]<=2;reply[4]<=value[7:0];reply[5]<=value[15:8];
  reply_header_crc<=hcrc(status,value);reply_tail_crc<=hcrc(status,value);reply_bytes<=0;tx_index<=0;state<=RESP;idle<=0;end endtask
 conv_tile_engine engine(.clk(clk),.reset(!reset_n||!arm),.abort(engine_abort),.load_start(load_start),
  .cfg_ic(ic),.cfg_oc(oc),.cfg_oh(oh),.cfg_ow(ow),.cfg_kernel(kernel),.cfg_stride(stride),.cfg_input_h(ih),.cfg_input_w(iw),
  .first_block(first_block),.final_block(final_block),.upload_valid(upload_valid),.upload_kind(upload_kind),.upload_address(upload_address),.upload_data(upload_data),
  .upload_ready(upload_ready),.start(engine_start),.busy(busy),.block_done(block_done),.output_valid(output_valid),.error(error),.error_code(error_code),.compute_cycles(compute_cycles),
  .read_enable(read_enable),.read_address(read_address),.read_valid(read_valid),.read_data(read_data));
 always @(posedge clk) begin
  packet_q<=packet[packet_read_address];outq<=outmem[out_address];
  if(state==RX && rise && !dir && !ds[1] && index>=11 && index<8+length && op==8'h61)packet[index-11]<=data_i;
  if(state==READWAIT && read_valid)outmem[read_index[7:0]]<=read_data;
 end
 assign ready=reset_n&&arm&&state==RESP;
 assign data_oe=ready&&dir&&ds[1];
 wire[12:0] total=8+(reply_bytes?reply_bytes+2:0);
 always @* begin
  data_o=0;
  if(tx_index<6)data_o=reply[tx_index];
  else if(tx_index==6)data_o=reply_header_crc[7:0];else if(tx_index==7)data_o=reply_header_crc[15:8];
  else if(tx_index<8+reply_bytes)data_o=outq[((tx_index-8)&3)*8+:8];
  else if(tx_index==8+reply_bytes)data_o=reply_tail_crc[7:0];else data_o=reply_tail_crc[15:8];
 end
 always @(posedge clk) begin
  if(!reset_n || !arm) begin
   state<=RX;cs<=0;ds<=0;index<=0;length<=0;tx_index<=0;reply_bytes<=0;crc<=16'hffff;header_crc<=0;low_crc<=0;reply_header_crc<=0;reply_tail_crc<=0;idle<=0;
   engine_abort<=0;load_start<=0;upload_valid<=0;engine_start<=0;read_enable<=0;packet_read_address<=0;upload_kind<=0;upload_address<=0;upload_data<=0;read_address<=0;
   ic<=0;oc<=0;oh<=0;ow<=0;kernel<=0;stride<=0;ih<=0;iw<=0;first_block<=0;final_block<=0;upload_base<=0;upload_count<=0;upload_index<=0;read_base<=0;read_count<=0;read_index<=0;settle<=0;crc_byte_index<=0;captured_word<=0;
   for(i=0;i<6;i=i+1)begin header[i]<=0;reply[i]<=0;end
   for(i=0;i<9;i=i+1)first[i]<=0;
  end else begin
   cs<={cs[1:0],bus_clk};ds<={ds[0],dir};load_start<=0;upload_valid<=0;engine_start<=0;read_enable<=0;engine_abort<=0;idle<=idle+1;
   if(idle>=TIMEOUT-1)begin state<=RX;index<=0;crc<=16'hffff;idle<=0;engine_abort<=1;end
   else case(state)
    RX: begin
     if(ds[1] && index!=0)begin index<=0;crc<=16'hffff;end
     if(rise && !dir && !ds[1])begin
      idle<=0;
      if(index<6)begin header[index]<=data_i;crc<=crcbyte(crc,data_i);end
      if(index==6)low_crc<=data_i;
      if(index==7)begin
       if(header[0]!=8'ha5 || header[3]!=2 || {data_i,low_crc[7:0]}!=crc || header[1][7])begin respond(1,0);index<=0;end
       else if(arg>2051)begin respond(3,0);index<=0;end
       else begin length<=arg;if(arg==0)state<=DISPATCH;end
      end else if(index>=8 && index<8+length)begin
       crc<=crcbyte(crc,data_i);if(index<17)first[index-8]<=data_i;
      end else if(index==8+length && index>=8)low_crc<=data_i;
      else if(index==9+length && index>=9)begin
       if({data_i,low_crc[7:0]}!=crc)respond(1,0);else state<=DISPATCH;
      end
      if(state==RX)index<=index+1'b1;
     end
    end
    DISPATCH: begin
     idle<=0;
     case(op)
      1:if(length==0)respond(0,16'h5054);else respond(3,0);
      8'h50:if(length==0)respond(0,16'h4e10);else respond(3,0);
      8'h60:if(length!=9 || first[0]<1 || first[0]>16 || first[1]<1 || first[1]>8 || first[2]<1 || first[2]>16 || first[3]<1 || first[3]>16 ||
          (first[4]!=1 && first[4]!=3) || (first[5]!=1 && first[5]!=2) || first[6]>33 || first[7]>33 || first[8]>3 || busy)respond(3,0);
       else begin ic<=first[0][4:0];oc<=first[1][3:0];oh<=first[2][4:0];ow<=first[3][4:0];kernel<=first[4][1:0];stride<=first[5][1:0];ih<=first[6][5:0];iw<=first[7][5:0];first_block<=first[8][0];final_block<=first[8][1];load_start<=1;settle<=2;state<=CFGWAIT;end
      8'h61:if(length<4 || first[0]>1 || !upload_ready || {first[2],first[1]}+{3'b0,length}-3>32768)respond(3,0);
       else begin upload_kind<=first[0][0];upload_base<={first[2],first[1]};upload_count<=length-3;upload_index<=0;packet_read_address<=0;state<=UPADDR;end
      8'h62:if(length || busy)respond(3,0);else begin engine_start<=1;state<=RUNWAIT;end
      8'h63:if(length!=4 || !output_valid || error || {first[3],first[2]}<1 || {first[3],first[2]}>256 || {1'b0,first[1],first[0]}+{1'b0,first[3],first[2]}>2048)respond(error?fault_status:8'd3,0);
       else begin read_base<={first[1],first[0]};read_count<={first[3],first[2]};read_index<=0;respond(0,{first[3],first[2]});reply_bytes<={first[3],first[2]}<<2;state<=READREQ;end
      8'h64:if(length)respond(3,0);else respond(0,{8'd0,error_code,2'd0,error,output_valid,busy});
      8'h65:if(length)respond(3,0);else respond(0,compute_cycles[15:0]);
      8'h66:if(length)respond(3,0);else respond(0,compute_cycles[31:16]);
      8'h67:if(length)respond(3,0);else begin engine_abort<=1;settle<=2;state<=ABORTWAIT;end
      default:respond(2,0);
     endcase
    end
    CFGWAIT:if(settle)settle<=settle-1'b1;else respond(error?fault_status:8'd0,0);
    UPADDR:begin packet_read_address<=upload_index[10:0];state<=UPWAIT;end
    UPWAIT:state<=UPSEND;
    UPSEND:if(error || !upload_ready)respond(error?fault_status:8'd4,0);else begin upload_address<=upload_base+upload_index;upload_data<=packet_q;upload_valid<=1;state<=UPACK;end
    UPACK:state<=UPCHECK;
    UPCHECK:if(error)respond(fault_status,0);else if(upload_index+1==upload_count)respond(0,0);else begin upload_index<=upload_index+1'b1;state<=UPADDR;end
    RUNWAIT:if(error)respond(fault_status,0);else if(block_done)respond(0,0);
    READREQ:begin read_address<=read_base+read_index;read_enable<=1;state<=READWAIT;end
    READWAIT:if(error)respond(fault_status,0);else if(read_valid)begin captured_word<=read_data;crc_byte_index<=0;state<=READCRC;end
    READCRC:begin
     reply_tail_crc<=crcbyte(reply_tail_crc,captured_word[crc_byte_index*8+:8]);
     if(crc_byte_index==3)begin if(read_index+1==read_count)begin tx_index<=0;state<=RESP;end else begin read_index<=read_index+1'b1;state<=READREQ;end end
     else crc_byte_index<=crc_byte_index+1'b1;
    end
    ABORTWAIT:if(settle)settle<=settle-1'b1;else respond(0,0);
    RESP:if(rise && dir && ds[1])begin idle<=0;if(tx_index+1==total)begin state<=RX;index<=0;crc<=16'hffff;tx_index<=0;end else tx_index<=tx_index+1'b1;end
    default:begin state<=RX;index<=0;crc<=16'hffff;engine_abort<=1;end
   endcase
  end
 end
endmodule
