// Resident triangle model: LOAD (vertices + indexed triangles), POSE (integer
// transform + perspective projection of every vertex), DRAW (replay one 32x32
// tile through the unchanged triangle engine command port).
// Bit-exact oracle: fpga/reference/triangle_model.py. No DDR, one multiplier,
// one bit-serial divider. Nothing executes before the trailer CRC is valid.
module triangle_model(input wire clk,reset_n,abort,
 input wire start_load,start_pose,start_draw,
 input wire [7:0] arg_a,arg_b,input wire [15:0] header_crc,
 input wire byte_valid,input wire [7:0] byte_data,
 output wire receiving,output wire busy,output reg done,
 output reg [7:0] status,result_a,result_b,
 output reg cmd_start,output wire [7:0] cmd_opcode,cmd_a,cmd_b,
 input wire cmd_done,input wire [7:0] cmd_status);
 localparam IDLE=0,RX_LOAD=1,RX_POSE=2,CRC_LO=3,CRC_HI=4,
  PS_FETCH=5,PS_WAIT=6,PS_LATCH=7,PS_MUL=8,PS_ACC=9,PS_CAM=10,PS_PROJ=11,
  PS_DIV=12,PS_DIVDONE=13,PS_STORE=14,
  D_TFETCH=15,D_TWAIT=16,D_TLATCH=17,D_SFETCH=18,D_SWAIT=19,D_SLATCH=20,
  D_EVAL0=21,D_EVAL1=22,D_ISSUE=23,D_WAIT=24;
 localparam ST_OK=0,ST_CRC=1,ST_ARG=3,ST_NOTREADY=5;
 reg [4:0] state;
 reg is_load,loaded,posed,bad;
 reg [6:0] nv;reg [7:0] nt;
 reg [9:0] total,count;reg [2:0] lane;reg [47:0] acc48;
 reg [7:0] item,titem;
 reg [15:0] crc;reg [7:0] crc_lo_byte;
 // Memories: written only by the owning state, synchronous read.
 (* ram_style="block" *) reg [47:0] vram[0:63];
 (* ram_style="block" *) reg [39:0] tram[0:127];
 (* ram_style="block" *) reg [51:0] sram[0:63];
 reg [47:0] vq;reg [39:0] tq;reg [51:0] sq;
 reg [5:0] vraddr,vwaddr,sraddr,swaddr;reg [6:0] traddr,twaddr;
 reg vwe,twe,swe;reg [47:0] vwdata;reg [39:0] twdata;reg [51:0] swdata;
 always @(posedge clk) begin if(vwe) vram[vwaddr]<=vwdata;vq<=vram[vraddr];end
 always @(posedge clk) begin if(twe) tram[twaddr]<=twdata;tq<=tram[traddr];end
 always @(posedge clk) begin if(swe) sram[swaddr]<=swdata;sq<=sram[sraddr];end
 // Pose parameters: nine rotation, three translation, focal, cx, cy, depth shift.
 reg [15:0] stg[0:15];reg [3:0] stg_index;reg stg_half;reg [7:0] stg_low;
 // Transform datapath.
 reg [5:0] vidx;reg [1:0] r,j;reg signed [15:0] m0,m1,m2;
 reg signed [39:0] prod,pacc;reg signed [23:0] cam0,cam1,cam2;
 reg [7:0] valid_count;
 reg which_y,proj_valid,dsign;reg signed [15:0] sx_r,sy_r;
 reg [39:0] nreg,qreg;reg [25:0] rem;reg [5:0] dcnt;
 // Draw datapath.
 reg [7:0] tile_x,tile_y,drawn,skipped,i0,i1,i2;reg [15:0] tcolor;reg [1:0] sload;
 reg [51:0] s0,s1,s2;reg [3:0] field;
 reg signed [23:0] lx0,ly0,lx1,ly1,lx2,ly2;
 reg [15:0] words[0:9];
 assign receiving=state==RX_LOAD||state==RX_POSE||state==CRC_LO||state==CRC_HI;
 assign busy=state!=IDLE;
 assign cmd_opcode=field==10 ? 8'h2c : 8'h21+field;
 assign cmd_a=field>=10 ? 8'h00 : words[field][7:0];
 assign cmd_b=field>=10 ? 8'h00 : words[field][15:8];
 function [15:0] crc_byte;
  input [15:0] c;input [7:0] b;reg [15:0] v;integer k;
  begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
 endfunction
 function fits16;input signed [23:0] v;begin fits16=(v>=-24'sd32768)&&(v<=24'sd32767);end endfunction
 wire signed [23:0] ox=$signed({7'b0,tile_x,9'b0});
 wire signed [23:0] oy=$signed({7'b0,tile_y,9'b0});
 wire [3:0] ridx=r*3+j;
 wire signed [15:0] rot=$signed(stg[ridx]);
 wire signed [15:0] trn=$signed(stg[9+r]);
 wire signed [15:0] focal=$signed(stg[12]);
 wire signed [15:0] mx=j==0?m0:(j==1?m1:m2);
 wire signed [39:0] sacc=pacc>>>14;
 wire signed [39:0] numx=focal*cam0;
 wire signed [39:0] numy=focal*cam1;
 wire signed [39:0] num=which_y?numy:numx;
 wire [25:0] divisor={2'b0,cam2};
 wire [25:0] rem_next={rem[24:0],nreg[39]};
 wire signed [41:0] qsigned=dsign ? -$signed({2'b0,qreg}) : $signed({2'b0,qreg});
 wire signed [41:0] sfull_x=$signed({{26{stg[13][15]}},stg[13]})+qsigned;
 wire signed [41:0] sfull_y=$signed({{26{stg[14][15]}},stg[14]})+qsigned;
 wire signed [23:0] zdepth=cam2>>>stg[15][3:0];
 wire [15:0] depth_w=zdepth>24'sd65535 ? 16'hffff : zdepth[15:0];
 always @(posedge clk or negedge reset_n) begin
  if(!reset_n) begin
   state<=IDLE;done<=0;status<=0;result_a<=0;result_b<=0;cmd_start<=0;loaded<=0;posed<=0;
   vwe<=0;twe<=0;swe<=0;crc<=0;bad<=0;total<=0;count<=0;lane<=0;item<=0;titem<=0;
   field<=0;nv<=0;nt<=0;is_load<=0;
  end else begin
   done<=0;cmd_start<=0;vwe<=0;twe<=0;swe<=0;
   if(abort) state<=IDLE;
   else case(state)
    IDLE: if(start_load) begin
      is_load<=1;loaded<=0;posed<=0;nv<=arg_a[6:0];nt<=arg_b;
      total<=arg_a[6:0]*3'd6+arg_b*3'd6;count<=0;lane<=0;item<=0;titem<=0;
      crc<=header_crc;bad<=0;state<=RX_LOAD;
     end else if(start_pose) begin
      is_load<=0;posed<=0;stg_index<=0;stg_half<=0;crc<=header_crc;state<=RX_POSE;
     end else if(start_draw) begin
      tile_x<=arg_a;tile_y<=arg_b;
      if(!loaded||!posed) begin status<=ST_NOTREADY;result_a<=0;result_b<=0;done<=1; end
      else begin drawn<=0;skipped<=0;titem<=0;state<=D_TFETCH;end
     end
    RX_LOAD: if(byte_valid) begin
      crc<=crc_byte(crc,byte_data);
      count<=count+1'b1;
      acc48[lane*8+:8]<=byte_data;
      if(lane==5) begin
       lane<=0;
       if(item<nv) begin
        vwe<=1;vwaddr<=item[5:0];vwdata<={byte_data,acc48[39:0]};
       end else begin
        // acc48: i0,i1,i2,reserved,color_lo; this byte is color_hi.
        twe<=1;twaddr<=titem[6:0];twdata<={byte_data,acc48[39:32],acc48[23:0]};
        if(acc48[7:0]>={1'b0,nv}||acc48[15:8]>={1'b0,nv}||acc48[23:16]>={1'b0,nv}||acc48[31:24]!=0) bad<=1;
        titem<=titem+1'b1;
       end
       item<=item+1'b1;
      end else lane<=lane+1'b1;
      if(count+1'b1==total) state<=CRC_LO;
     end
    RX_POSE: if(byte_valid) begin
      crc<=crc_byte(crc,byte_data);
      if(!stg_half) begin stg_low<=byte_data;stg_half<=1;end
      else begin stg[stg_index]<={byte_data,stg_low};stg_half<=0;stg_index<=stg_index+1'b1;
       if(stg_index==15) state<=CRC_LO;end
     end
    CRC_LO: if(byte_valid) begin crc_lo_byte<=byte_data;state<=CRC_HI;end
    CRC_HI: if(byte_valid) begin
      if({byte_data,crc_lo_byte}!=crc) begin status<=ST_CRC;result_a<=0;result_b<=0;done<=1;state<=IDLE;end
      else if(is_load) begin
       if(bad) begin status<=ST_ARG;result_a<=0;result_b<=0;done<=1;state<=IDLE;end
       else begin loaded<=1;status<=ST_OK;result_a<={1'b0,nv};result_b<=nt;done<=1;state<=IDLE;end
      end else begin
       if(!loaded) begin status<=ST_NOTREADY;result_a<=0;result_b<=0;done<=1;state<=IDLE;end
       else if(stg[15]>15) begin status<=ST_ARG;result_a<=0;result_b<=0;done<=1;state<=IDLE;end
       else begin vidx<=0;valid_count<=0;state<=PS_FETCH;end
      end
     end
    PS_FETCH: begin vraddr<=vidx;state<=PS_WAIT;end
    PS_WAIT: state<=PS_LATCH;
    PS_LATCH: begin m0<=vq[15:0];m1<=vq[31:16];m2<=vq[47:32];r<=0;j<=0;pacc<=0;state<=PS_MUL;end
    PS_MUL: begin prod<=rot*mx;state<=PS_ACC;end
    PS_ACC: begin pacc<=pacc+prod;
      if(j==2) state<=PS_CAM; else begin j<=j+1'b1;state<=PS_MUL;end end
    PS_CAM: begin
      case(r)
       0:cam0<=$signed(sacc[23:0])+trn;
       1:cam1<=$signed(sacc[23:0])+trn;
       default:cam2<=$signed(sacc[23:0])+trn;
      endcase
      pacc<=0;j<=0;
      if(r==2) begin which_y<=0;state<=PS_PROJ;end else begin r<=r+1'b1;state<=PS_MUL;end
     end
    PS_PROJ: begin
      if(cam2<1) begin proj_valid<=0;state<=PS_STORE;end
      else begin
       dsign<=num<0;nreg<=num<0 ? -num : num;
       qreg<=0;rem<=0;dcnt<=0;proj_valid<=1;state<=PS_DIV;
      end
     end
    PS_DIV: begin
      nreg<={nreg[38:0],1'b0};
      if(rem_next>=divisor) begin rem<=rem_next-divisor;qreg<={qreg[38:0],1'b1};end
      else begin rem<=rem_next;qreg<={qreg[38:0],1'b0};end
      dcnt<=dcnt+1'b1;
      if(dcnt==39) state<=PS_DIVDONE;
     end
    PS_DIVDONE: begin
      if(!which_y) begin
       if(sfull_x<-42'sd32768||sfull_x>42'sd32767) begin proj_valid<=0;state<=PS_STORE;end
       else begin sx_r<=sfull_x[15:0];which_y<=1;state<=PS_PROJ;end
      end else begin
       if(sfull_y<-42'sd32768||sfull_y>42'sd32767) proj_valid<=0;
       else sy_r<=sfull_y[15:0];
       state<=PS_STORE;
      end
     end
    PS_STORE: begin
      swe<=1;swaddr<=vidx;
      swdata<=proj_valid ? {1'b1,3'b000,depth_w,sy_r,sx_r} : 52'd0;
      if(proj_valid) valid_count<=valid_count+1'b1;
      if(vidx+1'b1==nv) begin
       posed<=1;status<=ST_OK;result_a<=valid_count+(proj_valid?8'd1:8'd0);result_b<={1'b0,nv};done<=1;state<=IDLE;
      end else begin vidx<=vidx+1'b1;state<=PS_FETCH;end
     end
    D_TFETCH: begin traddr<=titem[6:0];state<=D_TWAIT;end
    D_TWAIT: state<=D_TLATCH;
    D_TLATCH: begin i0<=tq[7:0];i1<=tq[15:8];i2<=tq[23:16];tcolor<=tq[39:24];sload<=0;state<=D_SFETCH;end
    D_SFETCH: begin sraddr<=sload==0?i0[5:0]:(sload==1?i1[5:0]:i2[5:0]);state<=D_SWAIT;end
    D_SWAIT: state<=D_SLATCH;
    D_SLATCH: begin
      case(sload) 0:s0<=sq; 1:s1<=sq; default:s2<=sq; endcase
      if(sload==2) state<=D_EVAL0; else begin sload<=sload+1'b1;state<=D_SFETCH;end
     end
    D_EVAL0: begin
      lx0<=$signed(s0[15:0])-ox;ly0<=$signed(s0[31:16])-oy;
      lx1<=$signed(s1[15:0])-ox;ly1<=$signed(s1[31:16])-oy;
      lx2<=$signed(s2[15:0])-ox;ly2<=$signed(s2[31:16])-oy;
      state<=D_EVAL1;
     end
    D_EVAL1: begin
      // field 11 marks "no engine commands for this triangle".
      field<=11;state<=D_ISSUE;
      if(!(s0[51]&&s1[51]&&s2[51])) skipped<=skipped+1'b1;
      else if(!(fits16(lx0)&&fits16(ly0)&&fits16(lx1)&&fits16(ly1)&&fits16(lx2)&&fits16(ly2)))
       skipped<=skipped+1'b1;
      else if((lx0<0&&lx1<0&&lx2<0)||(lx0>511&&lx1>511&&lx2>511)||
              (ly0<0&&ly1<0&&ly2<0)||(ly0>511&&ly1>511&&ly2>511)) ;
      else begin
       words[0]<=lx0[15:0];words[1]<=ly0[15:0];words[2]<=lx1[15:0];words[3]<=ly1[15:0];
       words[4]<=lx2[15:0];words[5]<=ly2[15:0];words[6]<=s0[47:32];words[7]<=s1[47:32];
       words[8]<=s2[47:32];words[9]<=tcolor;
       field<=0;
      end
     end
    D_ISSUE: begin
      if(field==11) begin
       if(titem+1'b1==nt) begin status<=ST_OK;result_a<=drawn;result_b<=skipped;done<=1;state<=IDLE;end
       else begin titem<=titem+1'b1;state<=D_TFETCH;end
      end else begin cmd_start<=1;state<=D_WAIT;end
     end
    D_WAIT: if(cmd_done) begin
      if(cmd_status!=0) begin status<=cmd_status;result_a<=drawn;result_b<=skipped;done<=1;state<=IDLE;end
      else if(field==10) begin
       drawn<=drawn+1'b1;
       if(titem+1'b1==nt) begin status<=ST_OK;result_a<=drawn+1'b1;result_b<=skipped;done<=1;state<=IDLE;end
       else begin titem<=titem+1'b1;state<=D_TFETCH;end
      end else begin field<=field+1'b1;state<=D_ISSUE;end
     end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
