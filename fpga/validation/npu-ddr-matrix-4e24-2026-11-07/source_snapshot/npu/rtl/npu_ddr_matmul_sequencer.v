// Standalone SYS-domain INT8 DDR matrix -> existing Conv tile descriptors.
// No host command/DDR port: a single exclusively-owned loader is required.
module npu_ddr_matmul_sequencer #(
 parameter [31:0] CAPACITY=32'd134217728,
 parameter [31:0] TILE_TIMEOUT=32'd27000000,DRAIN_TIMEOUT=32'd2700000
)(
 input wire clk,reset_n,abort,clear,memory_ready,
 input wire job_valid,output wire job_ready,
 input wire[31:0] job_m,job_k,job_n,
 input wire[31:0] job_a_base,job_a_pitch,job_b_base,job_b_pitch,job_c_base,job_c_pitch,
 output reg busy,out_valid,input wire out_ready,
 output reg result_valid,error,quarantined,output reg[3:0] error_code,
 output reg[31:0] accepted_tiles,completed_tiles,expected_tiles,
 output wire descriptor_valid,input wire descriptor_ready,
 output wire[4:0] cfg_ic,cfg_oh,cfg_ow,output wire[3:0] cfg_oc,
 output wire[1:0] cfg_kernel,cfg_stride,output wire first_block,final_block,
 output wire[15:0] input_full_h,input_full_w,
 output wire signed[31:0] input_origin_y,input_origin_x,
 output wire[31:0] input_base,input_row_pitch,input_channel_pitch,
 output wire[31:0] weight_base,weight_oc_stride,
 output wire[31:0] output_base,output_row_pitch,output_channel_pitch,
 output wire output_tail_owned,
 input wire tile_busy,tile_done,tile_error,tile_quarantined,tile_result_valid,
 output reg tile_abort
);
 localparam IDLE=0,MSTART=1,MWAIT=2,CHECK=3,ISSUE=4,WAIT_TILE=5,DRAIN=6;
 reg[2:0] state;reg[2:0] mul_job;
 reg[31:0] m,k,n,ab,ap,bb,bp,cb,cp,mb,nb,kb;
 reg[31:0] current_a,current_b,n_b,n_c;
 reg[63:0] a_span,b_span,c_span,tile_mn,count64;
 reg[31:0] deadline;reg outstanding;
 wire[31:0] m_pad=(m+15)&32'hfffffff0,k_pad=(k+15)&32'hfffffff0;
 wire[31:0] m_tiles=(m+255)>>8,n_tiles=(n+7)>>3,k_tiles=(k+15)>>4;
 reg[31:0] mul_a,mul_b;wire mul_done;wire[63:0] mul_result;
 always @* begin
  mul_a=0;mul_b=0;
  case(mul_job)
   0:begin mul_a=ap;mul_b=k;end
   1:begin mul_a=bp;mul_b=n;end
   2:begin mul_a=cp;mul_b=n;end
   3:begin mul_a=m_tiles;mul_b=n_tiles;end
   4:begin mul_a=tile_mn[31:0];mul_b=k_tiles;end
  endcase
 end
 npu_mm_seq_u32mul multiply(clk,!reset_n||abort||state==IDLE||state==DRAIN,state==MSTART,mul_a,mul_b,mul_done,mul_result);
 wire[63:0] a_end={32'd0,ab}+a_span,b_end={32'd0,bb}+b_span,c_end={32'd0,cb}+c_span;
 function overlap;input[31:0] a,b;input[63:0] ae,be;begin overlap=({32'd0,a}<be)&&({32'd0,b}<ae);end endfunction
 assign job_ready=state==IDLE&&!busy&&!out_valid&&!error&&!quarantined&&!abort&&reset_n&&memory_ready&&!tile_busy&&!tile_error&&!tile_quarantined;
 assign cfg_ic=k-kb>=16?5'd16:(k-kb);
 assign cfg_oc=n-nb>=8?4'd8:(n-nb);
 assign cfg_oh=m-mb>=256?5'd16:((m-mb+15)>>4);
 assign cfg_ow=16;assign cfg_kernel=1;assign cfg_stride=1;
 assign first_block=kb==0;assign final_block=k-kb<=16;
 assign input_full_h=(m+15)>>4;assign input_full_w=16;
 assign input_origin_y=mb>>4;assign input_origin_x=0;
 assign input_base=current_a;assign input_row_pitch=16;assign input_channel_pitch=ap;
 assign weight_base=current_b;assign weight_oc_stride=bp;
 assign output_base=n_c+(mb<<2);assign output_row_pitch=64;assign output_channel_pitch=cp;
 assign output_tail_owned=1;
 assign descriptor_valid=state==ISSUE&&!tile_done&&!tile_busy&&!tile_error&&!tile_quarantined&&!abort&&memory_ready;
 task fail;input[3:0] code;begin
  error<=1;error_code<=code;result_valid<=0;tile_abort<=1;deadline<=0;
  if(outstanding||tile_busy)state<=DRAIN;
  else begin state<=IDLE;busy<=0;out_valid<=1;end
 end endtask
 always @(posedge clk)begin
  if(!reset_n)begin
   state<=IDLE;mul_job<=0;m<=0;k<=0;n<=0;ab<=0;ap<=0;bb<=0;bp<=0;cb<=0;cp<=0;mb<=0;nb<=0;kb<=0;
   current_a<=0;current_b<=0;n_b<=0;n_c<=0;a_span<=0;b_span<=0;c_span<=0;tile_mn<=0;count64<=0;deadline<=0;outstanding<=0;
   busy<=0;out_valid<=0;result_valid<=0;error<=0;quarantined<=0;error_code<=0;accepted_tiles<=0;completed_tiles<=0;expected_tiles<=0;tile_abort<=0;
  end else begin
   if(out_valid&&out_ready)out_valid<=0;
   if(clear&&state==IDLE&&!busy&&!outstanding&&!tile_busy&&!tile_quarantined&&!quarantined&&!tile_error&&!tile_done&&!abort)begin
    error<=0;error_code<=0;result_valid<=0;out_valid<=0;tile_abort<=0;
   end
   if(state!=IDLE&&state!=DRAIN&&(abort||!memory_ready||tile_quarantined||tile_error))begin
    if(tile_quarantined)quarantined<=1;
    fail(abort?4'd5:!memory_ready?4'd7:tile_quarantined?4'd8:4'd4);
   end else case(state)
   IDLE:begin
    if((!memory_ready||tile_quarantined)&&result_valid)begin
     result_valid<=0;error<=1;error_code<=!memory_ready?4'd7:4'd8;out_valid<=1;tile_abort<=1;
     if(tile_quarantined)quarantined<=1;
    end else if(abort)begin result_valid<=0;out_valid<=0;tile_abort<=1;end
    else if(job_valid&&job_ready)begin
     m<=job_m;k<=job_k;n<=job_n;ab<=job_a_base;ap<=job_a_pitch;bb<=job_b_base;bp<=job_b_pitch;cb<=job_c_base;cp<=job_c_pitch;
     mb<=0;nb<=0;kb<=0;current_a<=job_a_base;current_b<=job_b_base;n_b<=job_b_base;n_c<=job_c_base;
     busy<=1;result_valid<=0;error<=0;error_code<=0;accepted_tiles<=0;completed_tiles<=0;expected_tiles<=0;tile_abort<=0;outstanding<=0;
     mul_job<=0;state<=MSTART;
    end
   end
   MSTART:state<=MWAIT;
   MWAIT:if(mul_done)begin
    case(mul_job)
     0:a_span<=mul_result;
     1:b_span<=mul_result;
     2:c_span<=mul_result;
     3:tile_mn<=mul_result;
     4:count64<=mul_result;
    endcase
    if(mul_job==4)state<=CHECK;else begin mul_job<=mul_job+1'b1;state<=MSTART;end
   end
   CHECK:begin
    if(m==0||m>65535||k==0||k>65535||n==0||n>65535)fail(1);
    else if(ab[3:0]!=0||bb[3:0]!=0||cb[3:0]!=0||ap[3:0]!=0||bp[3:0]!=0||cp[3:0]!=0||ap<m_pad||bp<k_pad||cp<(m_pad<<2))fail(2);
    else if(a_end>{32'd0,CAPACITY}||b_end>{32'd0,CAPACITY}||c_end>{32'd0,CAPACITY}||a_span==0||b_span==0||c_span==0||count64==0||count64>64'hffffffff)fail(2);
    else if(overlap(ab,bb,a_end,b_end)||overlap(ab,cb,a_end,c_end)||overlap(bb,cb,b_end,c_end))fail(3);
    else begin expected_tiles<=count64[31:0];deadline<=0;state<=ISSUE;end
   end
   ISSUE:begin
    if(deadline>=TILE_TIMEOUT-1)fail(6);
    else if(descriptor_valid&&descriptor_ready)begin accepted_tiles<=accepted_tiles+1'b1;outstanding<=1;deadline<=0;state<=WAIT_TILE;end
    else deadline<=deadline+1'b1;
   end
   WAIT_TILE:begin
    if(tile_done&&!tile_busy)begin
     outstanding<=0;
     if(final_block&&!tile_result_valid)fail(9);
     else begin
      completed_tiles<=completed_tiles+1'b1;deadline<=0;
      if(!final_block)begin kb<=kb+16;current_a<=current_a+(ap<<4);current_b<=current_b+16;state<=ISSUE;end
      else if(m-mb>256)begin mb<=mb+256;kb<=0;current_a<=ab;current_b<=n_b;state<=ISSUE;end
      else if(n-nb>8)begin nb<=nb+8;mb<=0;kb<=0;current_a<=ab;n_b<=n_b+(bp<<3);current_b<=n_b+(bp<<3);n_c<=n_c+(cp<<3);state<=ISSUE;end
      else if(completed_tiles+1!=expected_tiles||accepted_tiles!=expected_tiles)fail(9);
      else begin result_valid<=1;out_valid<=1;busy<=0;state<=IDLE;end
     end
    end else if(deadline>=TILE_TIMEOUT-1)fail(6);else deadline<=deadline+1'b1;
   end
   DRAIN:begin
    tile_abort<=1;
    if(tile_quarantined)quarantined<=1;
    if(!tile_busy)begin outstanding<=0;state<=IDLE;busy<=0;out_valid<=1;end
    else if(deadline>=DRAIN_TIMEOUT-1)begin quarantined<=1;busy<=0;out_valid<=1;state<=IDLE;end
    else deadline<=deadline+1'b1;
   end
   default:fail(9);
   endcase
  end
 end
endmodule

// Shared sequential range/count multiplier: no DSP/BSRAM, fixed32 iterations.
module npu_mm_seq_u32mul(input wire clk,reset,start,input wire[31:0] a,b,
 output reg done,output reg[63:0] result);
 reg running;reg[5:0] count;reg[63:0] partial,shifted;reg[31:0] factor;
 wire[63:0] next_partial=partial+(factor[0]?shifted:64'd0);
 always @(posedge clk)begin
  if(reset)begin running<=0;done<=0;result<=0;count<=0;partial<=0;shifted<=0;factor<=0;end
  else begin done<=0;
   if(start&&!running)begin running<=1;count<=0;partial<=0;shifted<={32'd0,a};factor<=b;end
   else if(running)begin partial<=next_partial;shifted<=shifted<<1;factor<=factor>>1;count<=count+1'b1;
    if(count==31)begin result<=next_partial;running<=0;done<=1;end
   end
  end
 end
endmodule
