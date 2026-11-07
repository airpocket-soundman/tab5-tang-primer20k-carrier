// Experimental SYS-domain controller only. Not a wire ABI or deployed capability.
// Job u32 words: IC,OC,OH,OW,k,stride,IH,IW,originY,originX,
// A,Arow,Achannel,B,Boc,C,Crow,Cchannel. Signed origins; other words unsigned.
// C owns all OC*Cchannel bytes, including aligned row/channel padding.
module npu_ddr_conv_strip_sequencer #(
 parameter [31:0] CAPACITY=134217728,
 parameter [31:0] TILE_TIMEOUT=27000000,DRAIN_TIMEOUT=2700000
)(
 input wire clk,reset_n,abort,clear,memory_ready,
 input wire job_valid,output wire job_ready,input wire[575:0] job,
 output reg busy,output wire out_valid,input wire out_ready,
 output wire result_valid,output reg error,quarantined,output reg[3:0] error_code,
 output reg[31:0] accepted_tiles,completed_tiles,expected_tiles,
 output wire descriptor_valid,input wire descriptor_ready,
 output reg[415:0] descriptor,
 input wire tile_busy,tile_done,tile_error,tile_quarantined,tile_result_valid,
 output reg tile_abort
);
 localparam IDLE=0,MSTART=1,MWAIT=2,CHECK=3,ISSUE=4,WAIT_TILE=5,DRAIN=6;
 reg out_valid_q,result_valid_q;
 assign out_valid=out_valid_q&&!abort&&memory_ready&&reset_n;
 assign result_valid=result_valid_q&&!abort&&memory_ready&&reset_n;
 reg[2:0] state,mul_job;reg[31:0] j[0:17];
 reg[31:0] xb,ib,current_a,current_b,deadline;reg outstanding;
 reg[63:0] a_span,b_span,c_span,row_span,weight_span,out_span,count64;
 reg[31:0] mul_a,mul_b;wire[63:0] product;wire mul_done;
 wire[31:0] ic=j[0],oc=j[1],oh=j[2],ow=j[3],kernel=j[4],stride=j[5];
 wire[31:0] ih=j[6],iw=j[7],ab=j[10],arp=j[11],acp=j[12];
 wire[31:0] bb=j[13],bp=j[14],cb=j[15],crp=j[16],ccp=j[17];
 wire[31:0] x_tiles=(ow>>4)+(|ow[3:0]);
 wire[31:0] i_tiles=(ic>>4)+(|ic[3:0]);
 wire[63:0] a_end={32'd0,ab}+a_span,b_end={32'd0,bb}+b_span,c_end={32'd0,cb}+c_span;
 wire signed[63:0] origin_y={{32{j[8][31]}},j[8]};
 wire signed[63:0] origin_x={{32{j[9][31]}},j[9]};
 wire signed[63:0] end_y=origin_y+(stride==2?($signed({32'd0,oh-32'd1})<<<1):$signed({32'd0,oh-32'd1}));
 wire signed[63:0] end_x=origin_x+(stride==2?($signed({32'd0,ow-32'd1})<<<1):$signed({32'd0,ow-32'd1}));
 wire[31:0] now_ic=ic-ib>=16?16:ic-ib,now_ow=ow-xb>=16?16:ow-xb;
 wire final_block=ic-ib<=16;
 integer z;
 always @* begin
  mul_a=0;mul_b=0;
  case(mul_job)
   0:begin mul_a=acp;mul_b=ic;end
   1:begin mul_a=bp;mul_b=oc;end
   2:begin mul_a=ccp;mul_b=oc;end
   3:begin mul_a=arp;mul_b=ih;end
   4:begin mul_a=ic;mul_b=kernel==3?9:1;end
   5:begin mul_a=crp;mul_b=oh;end
   6:begin mul_a=x_tiles;mul_b=i_tiles;end
  endcase
 end
 npu_convstrip_u32mul multiply(clk,!reset_n||abort||state==IDLE||state==DRAIN,state==MSTART,mul_a,mul_b,mul_done,product);
 function overlap;input[31:0] a,b;input[63:0] ae,be;begin overlap=({32'd0,a}<be)&&({32'd0,b}<ae);end endfunction
 assign job_ready=state==IDLE&&!busy&&!out_valid&&!error&&!quarantined&&!abort&&reset_n&&memory_ready&&!tile_busy&&!tile_error&&!tile_quarantined;
 assign descriptor_valid=state==ISSUE&&!tile_done&&!tile_busy&&!tile_error&&!tile_quarantined&&!abort&&memory_ready;
 always @* begin
  descriptor=0;
  descriptor[0+:8]=now_ic[7:0];descriptor[8+:8]=oc[7:0];
  descriptor[16+:8]=oh[7:0];descriptor[24+:8]=now_ow[7:0];
  descriptor[32+:8]=kernel[7:0];descriptor[40+:8]=stride[7:0];
  descriptor[48+:8]={5'd0,1'b1,final_block,ib==0};
  descriptor[64+:16]=ih[15:0];descriptor[80+:16]=iw[15:0];
  descriptor[96+:32]=j[8];descriptor[128+:32]=j[9]+(stride==2?(xb<<1):xb);
  descriptor[160+:32]=current_a;descriptor[192+:32]=arp;descriptor[224+:32]=acp;
  descriptor[256+:32]=current_b;descriptor[288+:32]=bp;
  descriptor[320+:32]=cb+(xb<<2);descriptor[352+:32]=crp;descriptor[384+:32]=ccp;
 end
 task fail;input[3:0] code;begin
  error<=1;error_code<=code;result_valid_q<=0;tile_abort<=1;deadline<=0;
  if(outstanding||tile_busy)state<=DRAIN;
  else begin state<=IDLE;busy<=0;out_valid_q<=1;end
 end endtask
 always @(posedge clk)begin
  if(!reset_n)begin
   state<=IDLE;mul_job<=0;for(z=0;z<18;z=z+1)j[z]<=0;
   xb<=0;ib<=0;current_a<=0;current_b<=0;deadline<=0;outstanding<=0;
   a_span<=0;b_span<=0;c_span<=0;row_span<=0;weight_span<=0;out_span<=0;count64<=0;
   busy<=0;out_valid_q<=0;result_valid_q<=0;error<=0;quarantined<=0;error_code<=0;
   accepted_tiles<=0;completed_tiles<=0;expected_tiles<=0;tile_abort<=0;
  end else begin
   if(out_valid&&out_ready)out_valid_q<=0;
   if(clear&&state==IDLE&&!busy&&!outstanding&&!tile_busy&&!tile_quarantined&&!quarantined&&!tile_error&&!tile_done&&!abort)begin
    error<=0;error_code<=0;result_valid_q<=0;out_valid_q<=0;tile_abort<=0;
   end
   if(state!=IDLE&&state!=DRAIN&&(abort||!memory_ready||tile_quarantined||tile_error))begin
    if(tile_quarantined)quarantined<=1;
    fail(abort?5:!memory_ready?7:tile_quarantined?8:4);
   end else case(state)
    IDLE:begin
     if((!memory_ready||tile_quarantined)&&result_valid_q)begin
      result_valid_q<=0;error<=1;error_code<=!memory_ready?7:8;out_valid_q<=1;tile_abort<=1;
      if(tile_quarantined)quarantined<=1;
     end else if(abort)begin result_valid_q<=0;out_valid_q<=0;tile_abort<=1;end
     else if(job_valid&&job_ready)begin
      for(z=0;z<18;z=z+1)j[z]<=job[z*32+:32];
      xb<=0;ib<=0;current_a<=job[320+:32];current_b<=job[416+:32];
      busy<=1;result_valid_q<=0;error<=0;error_code<=0;accepted_tiles<=0;completed_tiles<=0;expected_tiles<=0;
      tile_abort<=0;outstanding<=0;mul_job<=0;deadline<=0;state<=MSTART;
     end
    end
    MSTART:state<=MWAIT;
    MWAIT:if(mul_done)begin
     case(mul_job)
      0:a_span<=product;1:b_span<=product;2:c_span<=product;
      3:row_span<=product;4:weight_span<=product;5:out_span<=product;6:count64<=product;
     endcase
     if(mul_job==6)state<=CHECK;else begin mul_job<=mul_job+1'b1;state<=MSTART;end
    end
    CHECK:begin
     if(ic==0||ic>65535||oc==0||oc>8||oh==0||oh>16||ow==0||ow>65535||ih==0||ih>65535||iw==0||iw>65535||
        (kernel!=1&&kernel!=3)||(stride!=1&&stride!=2))fail(1);
     else if(ab[3:0]||arp[3:0]||acp[3:0]||bb[3:0]||bp[3:0]||cb[3:0]||crp[3:0]||ccp[3:0]||
       {32'd0,arp}<(({32'd0,iw}+15)&64'hfffffffffffffff0)||
       {32'd0,acp}<row_span||{32'd0,bp}<((weight_span+15)&64'hfffffffffffffff0)||
       {32'd0,crp}<((({32'd0,ow}<<2)+15)&64'hfffffffffffffff0)||{32'd0,ccp}<out_span||
       a_end>{32'd0,CAPACITY}||b_end>{32'd0,CAPACITY}||c_end>{32'd0,CAPACITY}||
       a_span==0||b_span==0||c_span==0||count64==0||count64>64'hffffffff||
       end_x>64'sh7fffffff||end_y>64'sh7fffffff)fail(2);
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
       if(!final_block)begin ib<=ib+16;current_a<=current_a+(acp<<4);current_b<=current_b+(kernel==3?144:16);state<=ISSUE;end
       else if(ow-xb>16)begin xb<=xb+16;ib<=0;current_a<=ab;current_b<=bb;state<=ISSUE;end
       else if(completed_tiles+1!=expected_tiles||accepted_tiles!=expected_tiles)fail(9);
       else begin result_valid_q<=1;out_valid_q<=1;busy<=0;state<=IDLE;end
      end
     end else if(deadline>=TILE_TIMEOUT-1)fail(6);else deadline<=deadline+1'b1;
    end
    DRAIN:begin
     tile_abort<=1;if(tile_quarantined)quarantined<=1;
     if(!tile_busy)begin outstanding<=0;state<=IDLE;busy<=0;out_valid_q<=1;end
     else if(deadline>=DRAIN_TIMEOUT-1)begin quarantined<=1;busy<=0;out_valid_q<=1;state<=IDLE;end
     else deadline<=deadline+1'b1;
    end
    default:fail(9);
   endcase
  end
 end
endmodule

module npu_convstrip_u32mul(input wire clk,reset,start,input wire[31:0] a,b,
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
