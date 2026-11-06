// DDR-backed bounded Conv tile scheduler, SYS clock. No physical DDR pins.
// Reuses memv1 held-bundle req/done and dual-clock 128-bit staging interfaces.
// Tensor rows/pitches and failure/publication contract: DDR_TILE_LOADER.md.
module npu_ddr_tile_loader_8oc #(
 parameter [31:0] CAPACITY=32'd134217728,
 parameter MEMORY_TIMEOUT=2700000,DRAIN_TIMEOUT=2700000,ENGINE_TIMEOUT=1000000
)(
 input wire clk,reset_n,memory_ready,start,abort,clear,
 output wire start_ready,busy,
 input wire [4:0] cfg_ic,cfg_oh,cfg_ow,input wire [3:0] cfg_oc,
 input wire [1:0] cfg_kernel,cfg_stride,input wire first_block,final_block,
 input wire [15:0] input_full_h,input_full_w,
 input wire signed [31:0] input_origin_y,input_origin_x,
 input wire [31:0] input_base,input_row_pitch,input_channel_pitch,
 input wire [31:0] weight_base,weight_oc_stride,
 input wire [31:0] output_base,output_row_pitch,output_channel_pitch,
 input wire output_tail_owned,
 output reg block_done,result_valid,error,quarantined,
 output reg [3:0] error_code,mem_status,
 output reg [31:0] total_cycles,ddr_wait_cycles,read_beats,write_beats,
 output wire [31:0] kernel_cycles,
 output reg req_t,cancel_t,
 output reg [1:0] h_op,output reg [31:0] h_addr,output reg [15:0] h_beats,
 output reg [31:0] h_arg,output reg [23:0] h_tag,
 input wire done_t,input wire [23:0] r_tag,input wire [3:0] r_status,input wire [15:0] r_beats,
 output wire w_we,output wire [7:0] w_addr,output wire [127:0] w_data,
 output reg [7:0] r_addr,input wire [127:0] r_data
);
 localparam IDLE=0,CONFIG=1,CONFIG_WAIT=2,IROW=3,IREQ=4,IBEAT_ADDR=5,IBEAT_WAIT=6,IBEAT_CAPTURE=7,IFEED=8,
  WROW=9,WREQ=10,WBEAT_ADDR=11,WBEAT_WAIT=12,WBEAT_CAPTURE=13,WFEED=14,RUN_START=15,RUN_WAIT=16,
  OINIT=17,OREAD=18,OWAIT=19,OSTAGE=20,OREQ=21,OADV=22,MEM_ISSUE=23,MEM_WAIT=24,MEM_CAPTURE=25,DRAIN=26,DRAIN_CAPTURE=27,FAULT=28,MUL_START=29,MUL_WAIT=30,VALIDATE=31;
 reg [4:0] state,mem_return;
 reg [1:0] done_sync;reg done_ref,outstanding,cancel_sent;
 reg [23:0] next_tag;
 reg [31:0] wait_count,engine_wait;
 reg [2:0] mul_job;
 reg [63:0] input_plane_bytes_q,output_plane_bytes_q,input_channels_offset,weight_channels_offset,output_channels_offset,input_firstrow_offset,input_row_address;
 reg [31:0] input_channel_address,output_row_bytes_q;
 reg [4:0] nic,oh,ow;reg [3:0] noc;reg [1:0] kernel,stride;
 reg [5:0] ih,iw,left_pad,copy_width,in_row,in_col;
 reg [15:0] full_h,full_w,source_x;
 reg signed [31:0] origin_y,origin_x;
 reg [31:0] ibase,ipitch,icpitch,wbase,wstride,obase,opitch,ocpitch;
 reg saved_first,saved_final,saved_tail,partial_good;
 reg [31:0] next_input_base,next_weight_base;
 reg [4:0] in_channel;reg [3:0] weight_oc,out_oc;
 reg [4:0] out_row,row_word;
 reg [7:0] weight_span,weight_col,stage_index;
 reg [3:0] stage_byte;reg [1:0] pack_slot;
 reg [14:0] input_index;reg [10:0] weight_index,output_index;
 reg row_has_copy;reg [31:0] read_source,weight_row_addr,output_ch_addr,output_row_addr;
 reg [15:0] request_beats;reg [127:0] beat_data,pack;
 wire signed [63:0] source_y=$signed({{32{origin_y[31]}},origin_y})+$signed({58'd0,in_row});
 wire [63:0] input_address64=input_row_address+{48'd0,source_x};
 wire [31:0] halo_h=cfg_stride==2 ? (({27'd0,cfg_oh}-1)<<1)+{30'd0,cfg_kernel} : ({27'd0,cfg_oh}-1)+{30'd0,cfg_kernel};
 wire [31:0] halo_w=cfg_stride==2 ? (({27'd0,cfg_ow}-1)<<1)+{30'd0,cfg_kernel} : ({27'd0,cfg_ow}-1)+{30'd0,cfg_kernel};
 wire [31:0] weight_row_bytes=cfg_kernel==3?{27'd0,cfg_ic}+({27'd0,cfg_ic}<<3):{27'd0,cfg_ic};
 wire [31:0] output_row_bytes=({27'd0,cfg_ow}+3)>>2<<4;
 wire [63:0] input_end={32'd0,ibase}+input_channels_offset+input_plane_bytes_q-{32'd0,ipitch}+{48'd0,full_w};
 wire [63:0] weight_end={32'd0,wbase}+weight_channels_offset+{56'd0,weight_span};
 wire [63:0] output_end={32'd0,obase}+output_channels_offset+output_plane_bytes_q-{32'd0,opitch}+{32'd0,output_row_bytes_q};
 wire overlap_input=({32'd0,obase}<input_end && {32'd0,ibase}<output_end);
 wire overlap_weights=({32'd0,obase}<weight_end && {32'd0,wbase}<output_end);
 wire shape_valid=cfg_ic>=1 && cfg_ic<=16 && cfg_oc>=1 && cfg_oc<=8 && cfg_oh>=1 && cfg_oh<=16 && cfg_ow>=1 && cfg_ow<=16 &&
  (cfg_kernel==1 || cfg_kernel==3) && (cfg_stride==1 || cfg_stride==2) && input_full_h!=0 && input_full_w!=0;
 wire descriptor_fields_valid=shape_valid && input_row_pitch<=CAPACITY && input_channel_pitch<=CAPACITY && weight_oc_stride<=CAPACITY && output_row_pitch<=CAPACITY && output_channel_pitch<=CAPACITY &&
  input_row_pitch>=input_full_w && weight_oc_stride>=weight_row_bytes && output_base[3:0]==0 && output_row_pitch[3:0]==0 && output_channel_pitch[3:0]==0 &&
  output_row_pitch>=output_row_bytes && (cfg_ow[1:0]==0 || output_tail_owned);
 wire descriptor_range_valid={32'd0,icpitch}>=input_plane_bytes_q && {32'd0,ocpitch}>=output_plane_bytes_q &&
  input_end<={32'd0,CAPACITY} && weight_end<={32'd0,CAPACITY} && output_end<={32'd0,CAPACITY} && !overlap_input && !overlap_weights;
 wire continuation_valid=partial_good && cfg_oc==noc && cfg_oh==oh && cfg_ow==ow && cfg_kernel==kernel && cfg_stride==stride &&
  input_full_h==full_h && input_full_w==full_w && input_origin_y==origin_y && input_origin_x==origin_x &&
  input_base==next_input_base && input_row_pitch==ipitch && input_channel_pitch==icpitch && weight_base==next_weight_base && weight_oc_stride==wstride &&
  output_base==obase && output_row_pitch==opitch && output_channel_pitch==ocpitch && output_tail_owned==saved_tail;
 wire signed [63:0] incoming_x=$signed({{32{input_origin_x[31]}},input_origin_x});
 wire [63:0] incoming_left=incoming_x<0 ? -incoming_x : 64'd0;
 wire [63:0] incoming_xstart=incoming_x<0 ? 64'd0 : incoming_x;
 wire [63:0] clamped_left=incoming_left>{32'd0,halo_w}?{32'd0,halo_w}:incoming_left;
 wire [63:0] remaining_width={32'd0,halo_w}-clamped_left;
 wire [63:0] available_width=incoming_xstart>={48'd0,input_full_w}?64'd0:{48'd0,input_full_w}-incoming_xstart;
 wire [63:0] incoming_copy=remaining_width<available_width?remaining_width:available_width;
 wire [31:0] mul_operand=mul_job==0?ipitch:mul_job==1?opitch:mul_job==2?icpitch:mul_job==3?wstride:mul_job==4?ocpitch:ipitch;
 wire [15:0] mul_factor=mul_job==0?full_h:mul_job==1?{11'd0,oh}:mul_job==2?{11'd0,nic}-16'd1:
  mul_job==3 || mul_job==4?{12'd0,noc}-16'd1:(origin_y>=0 && origin_y<$signed({16'd0,full_h})?origin_y[15:0]:16'd0);
 reg engine_abort;
 wire mul_done;wire [63:0] mul_result;
 npu_ddr_u32x16 multiplier(.clk(clk),.reset(!reset_n||engine_abort),.start(state==MUL_START),.a(mul_operand),.b(mul_factor),.done(mul_done),.result(mul_result));
 wire engine_busy,engine_done,engine_output_valid,engine_error,upload_ready,engine_read_valid;
 wire [2:0] engine_code;wire signed [31:0] engine_read_data;
 wire engine_reset=!reset_n;
 wire engine_load=state==CONFIG;wire engine_start=state==RUN_START;
 wire engine_upload=state==IFEED || state==WFEED;
 wire copying=row_has_copy && in_col>=left_pad && {1'b0,in_col}<{1'b0,left_pad}+{1'b0,copy_width};
 wire [7:0] feed_byte=state==WFEED || copying ? beat_data[stage_byte*8+:8] : 8'd0;
 assign busy=state!=IDLE && state!=FAULT;
 assign start_ready=state==IDLE && !error && !quarantined && !outstanding && memory_ready;
 assign w_we=state==OSTAGE;assign w_addr=stage_index;assign w_data=pack;
 conv_tile_engine_8oc engine(.clk(clk),.reset(engine_reset),.abort(engine_abort),.load_start(engine_load),
  .cfg_ic(nic),.cfg_oc(noc),.cfg_oh(oh),.cfg_ow(ow),.cfg_kernel(kernel),.cfg_stride(stride),.cfg_input_h(ih),.cfg_input_w(iw),
  .first_block(saved_first),.final_block(saved_final),.upload_valid(engine_upload),.upload_kind(state==WFEED),
  .upload_address(state==WFEED?{4'd0,weight_index}:input_index),.upload_data(feed_byte),.upload_ready(upload_ready),.start(engine_start),
  .busy(engine_busy),.block_done(engine_done),.output_valid(engine_output_valid),.error(engine_error),.error_code(engine_code),.compute_cycles(kernel_cycles),
  .read_enable(state==OREAD),.read_address(output_index),.read_valid(engine_read_valid),.read_data(engine_read_data));
 function [31:0] satadd;input [31:0] a;input [15:0] b;reg[32:0]t;
 begin t={1'b0,a}+{17'd0,b};satadd=t[32]?32'hffffffff:t[31:0];end endfunction
 task fault;input[3:0] code;
 begin error<=1;error_code<=code;result_valid<=0;partial_good<=0;engine_abort<=1;
  if(outstanding)begin if(!cancel_sent)begin cancel_t<=~cancel_t;cancel_sent<=1;end wait_count<=0;state<=DRAIN;end
  else state<=FAULT;
 end endtask
 task request;input[1:0] op;input[31:0] address;input[15:0] beats;input[4:0] return_state;
 begin h_op<=op;h_addr<=address;h_beats<=beats;h_arg<=0;h_tag<=next_tag;next_tag<=next_tag+1'b1;mem_return<=return_state;state<=MEM_ISSUE;end endtask
 always @(posedge clk)begin
  done_sync<={done_sync[0],done_t};
  if(!reset_n)begin
   state<=IDLE;mem_return<=IDLE;done_sync<=0;done_ref<=done_t;outstanding<=0;cancel_sent<=0;next_tag<=1;req_t<=0;cancel_t<=0;
   h_op<=0;h_addr<=0;h_beats<=0;h_arg<=0;h_tag<=0;r_addr<=0;
   wait_count<=0;engine_wait<=0;mul_job<=0;input_plane_bytes_q<=0;output_plane_bytes_q<=0;input_channels_offset<=0;weight_channels_offset<=0;output_channels_offset<=0;input_firstrow_offset<=0;input_row_address<=0;input_channel_address<=0;output_row_bytes_q<=0;engine_abort<=1;block_done<=0;result_valid<=0;error<=0;error_code<=0;quarantined<=0;mem_status<=0;
   total_cycles<=0;ddr_wait_cycles<=0;read_beats<=0;write_beats<=0;
   nic<=0;noc<=0;oh<=0;ow<=0;kernel<=0;stride<=0;ih<=0;iw<=0;left_pad<=0;copy_width<=0;in_row<=0;in_col<=0;
   full_h<=0;full_w<=0;source_x<=0;origin_y<=0;origin_x<=0;ibase<=0;ipitch<=0;icpitch<=0;wbase<=0;wstride<=0;obase<=0;opitch<=0;ocpitch<=0;
   saved_first<=0;saved_final<=0;saved_tail<=0;partial_good<=0;next_input_base<=0;next_weight_base<=0;
   in_channel<=0;weight_oc<=0;out_oc<=0;out_row<=0;row_word<=0;weight_span<=0;weight_col<=0;stage_index<=0;stage_byte<=0;pack_slot<=0;
   input_index<=0;weight_index<=0;output_index<=0;row_has_copy<=0;read_source<=0;weight_row_addr<=0;output_ch_addr<=0;output_row_addr<=0;request_beats<=0;beat_data<=0;pack<=0;
  end else begin
   block_done<=0;engine_abort<=0;
   if(busy && total_cycles!=32'hffffffff)total_cycles<=total_cycles+1'b1;
   if((state==MEM_WAIT || state==MEM_CAPTURE || state==DRAIN || state==DRAIN_CAPTURE) && ddr_wait_cycles!=32'hffffffff)ddr_wait_cycles<=ddr_wait_cycles+1'b1;
   if(abort && state!=DRAIN && state!=DRAIN_CAPTURE && state!=MEM_CAPTURE && state!=FAULT)fault(8);
   else if(!memory_ready && state!=IDLE && state!=FAULT && state!=DRAIN && state!=DRAIN_CAPTURE && state!=MEM_CAPTURE)fault(9);
   else if(engine_error && state!=FAULT && state!=DRAIN && state!=DRAIN_CAPTURE && state!=MEM_CAPTURE)fault(engine_code==3?4'd3:4'd2);
   else case(state)
    IDLE:begin
     done_ref<=done_sync[1];
     if(!memory_ready)begin result_valid<=0;partial_good<=0;engine_abort<=1;end
     if(clear)begin engine_abort<=1;error<=0;error_code<=0;partial_good<=0;result_valid<=0;mem_status<=0;end
     else if(start)begin
      result_valid<=0;
      if(!memory_ready)fault(5);
      else if(!descriptor_fields_valid || (!first_block && !continuation_valid))fault(1);
      else begin
       nic<=cfg_ic;noc<=cfg_oc;oh<=cfg_oh;ow<=cfg_ow;kernel<=cfg_kernel;stride<=cfg_stride;ih<=halo_h[5:0];iw<=halo_w[5:0];
       full_h<=input_full_h;full_w<=input_full_w;origin_y<=input_origin_y;origin_x<=input_origin_x;source_x<=incoming_xstart[15:0];
       left_pad<=clamped_left[5:0];copy_width<=incoming_copy[5:0];ibase<=input_base;ipitch<=input_row_pitch;icpitch<=input_channel_pitch;
       wbase<=weight_base;wstride<=weight_oc_stride;obase<=output_base;opitch<=output_row_pitch;ocpitch<=output_channel_pitch;output_row_bytes_q<=output_row_bytes;input_channel_address<=input_base;
       saved_first<=first_block;saved_final<=final_block;saved_tail<=output_tail_owned;
       weight_span<=weight_row_bytes[7:0];in_channel<=0;in_row<=0;in_col<=0;input_index<=0;weight_index<=0;weight_oc<=0;weight_col<=0;
       weight_row_addr<=weight_base;output_ch_addr<=output_base;output_row_addr<=output_base;output_index<=0;out_oc<=0;out_row<=0;
       total_cycles<=0;ddr_wait_cycles<=0;read_beats<=0;write_beats<=0;mem_status<=0;engine_wait<=0;mul_job<=0;state<=MUL_START;
       if(first_block)partial_good<=0;
      end
     end
    end
    MUL_START:state<=MUL_WAIT;
    MUL_WAIT:if(mul_done)begin
     case(mul_job)
      0:input_plane_bytes_q<=mul_result;1:output_plane_bytes_q<=mul_result;2:input_channels_offset<=mul_result;
      3:weight_channels_offset<=mul_result;4:output_channels_offset<=mul_result;5:input_firstrow_offset<=mul_result;
     endcase
     if(mul_job==5)state<=VALIDATE;else begin mul_job<=mul_job+1'b1;state<=MUL_START;end
    end
    VALIDATE:if(!descriptor_range_valid)fault(1);else begin input_row_address<={32'd0,ibase}+input_firstrow_offset;state<=CONFIG;end
    CONFIG:state<=CONFIG_WAIT;
    CONFIG_WAIT:state<=IROW;
    IROW:begin
     in_col<=0;stage_index<=0;
     if(source_y<0 || source_y>=$signed({48'd0,full_h}) || copy_width==0)begin row_has_copy<=0;state<=IFEED;end
     else begin row_has_copy<=1;stage_byte<=input_address64[3:0];read_source<={input_address64[31:4],4'd0};request_beats<=({12'd0,input_address64[3:0]}+{10'd0,copy_width}+15)>>4;state<=IREQ;end
    end
    IREQ:request(0,read_source,request_beats,IBEAT_ADDR);
    IBEAT_ADDR:begin r_addr<=stage_index;state<=IBEAT_WAIT;end
    IBEAT_WAIT:state<=IBEAT_CAPTURE;
    IBEAT_CAPTURE:begin beat_data<=r_data;state<=IFEED;end
    IFEED:if(upload_ready)begin
     input_index<=input_index+1'b1;
     if(copying)stage_byte<=stage_byte+1'b1;
     if(in_col+1==iw)begin in_col<=0;if(in_row+1==ih)begin in_row<=0;if(in_channel+1==nic)state<=WROW;
      else begin in_channel<=in_channel+1'b1;input_channel_address<=input_channel_address+icpitch;input_row_address<={32'd0,input_channel_address}+{32'd0,icpitch}+input_firstrow_offset;state<=IROW;end end
      else begin in_row<=in_row+1'b1;if(source_y>=0 && source_y<$signed({48'd0,full_h}))input_row_address<=input_row_address+{32'd0,ipitch};state<=IROW;end end
     else begin in_col<=in_col+1'b1;if(copying && stage_byte==15 && {1'b0,in_col}+1<{1'b0,left_pad}+{1'b0,copy_width})begin stage_index<=stage_index+1'b1;state<=IBEAT_ADDR;end end
    end
    WROW:begin stage_index<=0;stage_byte<=weight_row_addr[3:0];weight_col<=0;read_source<={weight_row_addr[31:4],4'd0};request_beats<=({12'd0,weight_row_addr[3:0]}+{8'd0,weight_span}+15)>>4;state<=WREQ;end
    WREQ:request(0,read_source,request_beats,WBEAT_ADDR);
    WBEAT_ADDR:begin r_addr<=stage_index;state<=WBEAT_WAIT;end
    WBEAT_WAIT:state<=WBEAT_CAPTURE;
    WBEAT_CAPTURE:begin beat_data<=r_data;state<=WFEED;end
    WFEED:if(upload_ready)begin
     weight_index<=weight_index+1'b1;stage_byte<=stage_byte+1'b1;
     if(weight_col+1==weight_span)begin if(weight_oc+1==noc)state<=RUN_START;else begin weight_oc<=weight_oc+1'b1;weight_row_addr<=weight_row_addr+wstride;state<=WROW;end end
     else begin weight_col<=weight_col+1'b1;if(stage_byte==15)begin stage_index<=stage_index+1'b1;state<=WBEAT_ADDR;end end
    end
    RUN_START:begin engine_wait<=0;state<=RUN_WAIT;end
    RUN_WAIT:if(engine_done)begin
     if(saved_final)begin if(!engine_output_valid)fault(2);else state<=OINIT;end
     else begin partial_good<=1;next_input_base<=input_channel_address+icpitch;next_weight_base<=wbase+weight_span;block_done<=1;state<=IDLE;end
    end else if(engine_wait>=ENGINE_TIMEOUT-1)fault(7);else engine_wait<=engine_wait+1'b1;
    OINIT:begin row_word<=0;stage_index<=0;pack_slot<=0;pack<=0;state<=OREAD;end
    OREAD:state<=OWAIT;
    OWAIT:if(engine_read_valid)begin
     pack[pack_slot*32+:32]<=engine_read_data;output_index<=output_index+1'b1;row_word<=row_word+1'b1;
     if(pack_slot==3 || row_word+1==ow)state<=OSTAGE;else begin pack_slot<=pack_slot+1'b1;state<=OREAD;end
    end
    OSTAGE:if(row_word==ow)state<=OREQ;else begin stage_index<=stage_index+1'b1;pack_slot<=0;pack<=0;state<=OREAD;end
    OREQ:request(1,output_row_addr,({11'd0,ow}+3)>>2,OADV);
    OADV:if(out_row+1==oh)begin
     if(out_oc+1==noc)begin partial_good<=0;result_valid<=1;block_done<=1;state<=IDLE;end
     else begin out_row<=0;out_oc<=out_oc+1'b1;output_ch_addr<=output_ch_addr+ocpitch;output_row_addr<=output_ch_addr+ocpitch;state<=OINIT;end
    end else begin out_row<=out_row+1'b1;output_row_addr<=output_row_addr+opitch;state<=OINIT;end
    MEM_ISSUE:begin req_t<=~req_t;outstanding<=1;cancel_sent<=0;wait_count<=0;state<=MEM_WAIT;end
    MEM_WAIT:if(done_sync[1]!=done_ref)begin done_ref<=done_sync[1];state<=MEM_CAPTURE;end
     else if(wait_count>=MEMORY_TIMEOUT-1)fault(7);else wait_count<=wait_count+1'b1;
    MEM_CAPTURE:begin
     mem_status<=r_status;
     if(r_tag!=h_tag)fault(9);
     else begin
      outstanding<=0;
      if(h_op==0)read_beats<=satadd(read_beats,r_beats);else write_beats<=satadd(write_beats,r_beats);
      if(abort)begin error<=1;error_code<=8;result_valid<=0;partial_good<=0;engine_abort<=1;state<=FAULT;end
      else if(!memory_ready || r_beats>h_beats)begin error<=1;error_code<=9;result_valid<=0;partial_good<=0;engine_abort<=1;state<=FAULT;end
      else if(r_status!=0 || r_beats!=h_beats)begin error<=1;error_code<=6;result_valid<=0;partial_good<=0;engine_abort<=1;state<=FAULT;end
      else state<=mem_return;
     end
    end
    DRAIN:if(wait_count>=DRAIN_TIMEOUT-1)begin quarantined<=1;state<=FAULT;end
     else begin wait_count<=wait_count+1'b1;if(done_sync[1]!=done_ref)begin done_ref<=done_sync[1];state<=DRAIN_CAPTURE;end end
    DRAIN_CAPTURE:if(wait_count>=DRAIN_TIMEOUT-1)begin quarantined<=1;state<=FAULT;end
     else begin wait_count<=wait_count+1'b1;mem_status<=r_status;if(r_tag==h_tag)begin outstanding<=0;state<=FAULT;end else state<=DRAIN;end
    FAULT:if(clear && !outstanding && !quarantined)begin error<=0;error_code<=0;mem_status<=0;partial_good<=0;result_valid<=0;engine_abort<=1;state<=IDLE;done_ref<=done_sync[1];end
    default:fault(4);
   endcase
  end
 end
endmodule

// Fixed16-cycle unsigned address product. No DSP or combinational wide multiply.
module npu_ddr_u32x16(input wire clk,reset,start,input wire [31:0] a,input wire [15:0] b,
 output reg done,output reg [63:0] result);
 reg running;reg [3:0] count;reg [63:0] shifted,product;reg [15:0] factor;
 wire [63:0] added=product+(factor[0]?shifted:64'd0);
 always @(posedge clk)begin
  if(reset)begin running<=0;done<=0;result<=0;count<=0;shifted<=0;product<=0;factor<=0;end
  else begin done<=0;
   if(start && !running)begin running<=1;count<=0;shifted<={32'd0,a};product<=0;factor<=b;end
   else if(running)begin product<=added;shifted<=shifted<<1;factor<=factor>>1;count<=count+1'b1;
    if(count==15)begin result<=added;done<=1;running<=0;end
   end
  end
 end
endmodule
