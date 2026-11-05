// Fire integer_g0 v1. Shared numerical contract: fpga/host/fire_fixed.h.
// A tile is 32x32. No frame RAM, host pixel upload, or floating-point fallback.
// Arithmetic stages reuse one hash datapath across all four noise corners.
module fire_tile(
 input wire clk,reset_n,abort,start,
 input wire [15:0] origin_x,origin_y,width,height,
 input wire [31:0] frame,input wire [1:0] load,
 output wire busy,output reg done,
 output wire write_enable,output wire [9:0] write_address,
 output reg [15:0] write_color
);
 localparam IDLE=0,PIXEL=1,NORM=2,OCTAVE=3,SMOOTH_X=4,SMOOTH_Y=5,
            HASH_A=6,HASH_B=7,HASH_C=8,INTERP_X=9,INTERP_Y=10,
            ACCUMULATE=11,HEAT=12,PALETTE=13,WRITE=14,INTERP_BOTTOM=15,HASH_SUM=16;
 reg [4:0] state;
 reg [15:0] ox,oy,w,h,phase;
 reg [1:0] selected_load;
 reg [9:0] address;
 reg [12:0] inverse_width;
 reg [13:0] inverse_height;
 reg [16:0] px,py;
 reg signed [10:0] nx;
 reg [8:0] altitude;
 reg [2:0] octave;
 reg [8:0] turbulence;
 reg signed [31:0] u,v;
 reg [8:0] fx,fy;
 reg [1:0] corner;
 reg [15:0] hash_value;
 reg [15:0] hash_x,hash_y,hash_seed;
 reg [7:0] samples[0:3];
 reg [7:0] top,bottom,sample;
 reg signed [15:0] heat_value;
 wire valid_dimensions=(width==640 && height==360) ||
                       (width==320 && height==180) || (width==160 && height==96);
 wire signed [31:0] ix=u>>>8,iy=v>>>8;
 wire [15:0] corner_x=ix[15:0]+{15'd0,corner[0]};
 wire [15:0] corner_y=iy[15:0]+{15'd0,corner[1]};
 wire [31:0] normalized_x=px*inverse_width;
 wire [31:0] normalized_y=(h-1'b1-py)*inverse_height;
 // Hash multipliers are constant shift/add modulo2^16, not DSP lanes.
 wire [15:0] seed_hash=octave==0?16'd60667:octave==1?16'd21830:
                        octave==2?16'd48529:octave==3?16'd9692:
                        octave==4?16'd36391:16'd63090;
 wire [15:0] x_pair0=(corner_x<<10)+(corner_x<<9);
 wire [15:0] x_pair1=(corner_x<<8)+(corner_x<<7);
 wire [15:0] x_pair2=(corner_x<<5)+(corner_x<<4);
 wire [15:0] x_pair3=(corner_x<<2)+corner_x;
 wire [15:0] x_hash=(x_pair0+x_pair1)+(x_pair2+x_pair3);
 wire [15:0] y_pair0=(corner_y<<13)+(corner_y<<10);
 wire [15:0] y_pair1=(corner_y<<5)+(corner_y<<4);
 wire [15:0] y_pair2=(corner_y<<3)+(corner_y<<2);
 wire [15:0] y_hash=(y_pair0+y_pair1)+(y_pair2+corner_y);
 wire [15:0] hash_fold=hash_value^(hash_value>>7);
 wire [15:0] hash_pair0=(hash_fold<<14)+(hash_fold<<13);
 wire [15:0] hash_pair1=(hash_fold<<9)+(hash_fold<<6);
 wire [15:0] hash_pair2=(hash_fold<<4)+(hash_fold<<2);
 wire [15:0] hash_product=(hash_pair0+hash_pair1)+(hash_pair2+hash_fold);
 // One signed lerp multiplier, reused for top row, bottom row and vertical.
 wire [7:0] lerp_a=state==INTERP_X?samples[0]:state==INTERP_BOTTOM?samples[2]:top;
 wire [7:0] lerp_b=state==INTERP_X?samples[1]:state==INTERP_BOTTOM?samples[3]:bottom;
 wire [8:0] lerp_fraction=state==INTERP_Y?fy:fx;
 wire signed [9:0] lerp_delta=$signed({1'b0,lerp_b})-$signed({1'b0,lerp_a});
 wire signed [19:0] lerp_product=lerp_delta*$signed({1'b0,lerp_fraction});
 wire signed [19:0] lerp_result=$signed({1'b0,lerp_a})+(lerp_product>>>8);
 wire [10:0] abs_nx=nx<0?-nx:nx;
 wire [31:0] horizontal_cooling=abs_nx*(9'd128+altitude);
 wire [31:0] turbulence_wide={23'd0,turbulence};
 wire [31:0] noise_heat=(turbulence_wide<<7)+(turbulence_wide<<6)+
                       (turbulence_wide<<4)+(turbulence_wide<<3)+(turbulence_wide<<1);
 wire signed [31:0] temperature=$signed((32'd256-altitude)*3/2)-
                               $signed(horizontal_cooling>>8)+$signed(noise_heat>>8)-32'sd179;
 function [8:0] smooth;
  input [7:0] f;reg [31:0] square,product;
  begin square=f*f;product=square*(32'd768-2*f);smooth=product>>16;end
 endfunction
 function [8:0] clamp;
  input signed [31:0] value;
  begin clamp=value<0?0:value>256?256:value[8:0];end
 endfunction
 wire [8:0] r_level=clamp($signed(heat_value)*3);
 wire [8:0] g_level=clamp($signed(heat_value)*3-32'sd205);
 wire [8:0] b_level=clamp($signed(heat_value)*4-32'sd640);
 wire [16:0] red=({8'd0,r_level}<<8)-r_level;
 wire [16:0] green=({8'd0,g_level}<<8)-({8'd0,g_level}<<4);
 wire [16:0] blue=({8'd0,b_level}<<7)+({8'd0,b_level}<<5);
 wire [8:0] smoothed=smooth(state==SMOOTH_X?u[7:0]:v[7:0]);
 wire [31:0] base_u=($signed(nx)+32'sd256)*3;
 wire [31:0] base_v=altitude*3;
 wire [31:0] phase_wide={16'd0,phase};
 wire [31:0] speed_phase=octave==0?((phase_wide<<3)+(phase_wide<<2)):
                        octave==1?((phase_wide<<3)+(phase_wide<<2)+(phase_wide<<1)):
                        octave==2?(phase_wide<<4):
                        octave==3?((phase_wide<<4)+(phase_wide<<1)):
                        octave==4?((phase_wide<<4)+(phase_wide<<2)):
                        ((phase_wide<<4)+(phase_wide<<2)+(phase_wide<<1));
 assign busy=state!=IDLE;
 assign write_enable=state==WRITE && reset_n && !abort;
 assign write_address=address;
 always @(posedge clk or negedge reset_n) begin
  if(!reset_n) begin
   state<=IDLE;done<=0;address<=0;write_color<=0;
   ox<=0;oy<=0;w<=0;h<=0;phase<=0;selected_load<=0;
   inverse_width<=0;inverse_height<=0;px<=0;py<=0;nx<=0;altitude<=0;
   octave<=0;turbulence<=0;u<=0;v<=0;fx<=0;fy<=0;corner<=0;hash_value<=0;hash_x<=0;hash_y<=0;hash_seed<=0;
   top<=0;bottom<=0;sample<=0;heat_value<=0;
  end else begin
   done<=0;
   if(abort) begin state<=IDLE;address<=0;end
   else case(state)
    IDLE:if(start) begin
     if(!valid_dimensions || load==3) done<=1;
     else begin
      ox<=origin_x;oy<=origin_y;w<=width;h<=height;phase<=frame[15:0];selected_load<=load;
      inverse_width<=width==640?13'd1638:width==320?13'd3276:13'd6553;
      inverse_height<=height==360?14'd2912:height==180?14'd5825:14'd10922;
      address<=0;state<=PIXEL;
     end
    end
    PIXEL:begin
     px<={1'b0,ox}+{12'd0,address[4:0]};py<={1'b0,oy}+{12'd0,address[9:5]};state<=NORM;
    end
    NORM:begin
     if(px>=w || py>=h) begin write_color<=0;state<=WRITE;end
     else begin
      nx<=$signed(normalized_x>>11)-32'sd256;altitude<=normalized_y>>12;
      octave<=0;turbulence<=0;state<=OCTAVE;
     end
    end
    OCTAVE:begin
     u<=((base_u<<octave)>>1)+32'd3072;
     v<=(base_v<<octave)-speed_phase;
     state<=SMOOTH_X;
    end
    SMOOTH_X:begin fx<=smoothed;state<=SMOOTH_Y;end
    SMOOTH_Y:begin fy<=smoothed;corner<=0;state<=HASH_A;end
    HASH_A:begin hash_x<=x_hash;hash_y<=y_hash;hash_seed<=seed_hash;state<=HASH_SUM;end
    HASH_SUM:begin hash_value<=hash_x+hash_y+hash_seed;state<=HASH_B;end
    HASH_B:begin hash_value<=hash_product[15:0];state<=HASH_C;end
    HASH_C:begin
     samples[corner]<=hash_value[7:0]^hash_value[15:8];
     if(corner==3) state<=INTERP_X;
     else begin corner<=corner+1'b1;state<=HASH_A;end
    end
    INTERP_X:begin top<=lerp_result[7:0];state<=INTERP_BOTTOM;end
    INTERP_BOTTOM:begin bottom<=lerp_result[7:0];state<=INTERP_Y;end
    INTERP_Y:begin sample<=lerp_result[7:0];state<=ACCUMULATE;end
    ACCUMULATE:begin
     turbulence<=turbulence+(sample>>(octave+1));
     if(octave+1==2+2*selected_load) state<=HEAT;
     else begin octave<=octave+1'b1;state<=OCTAVE;end
    end
    HEAT:begin heat_value<=temperature[15:0];state<=PALETTE;end
    PALETTE:begin write_color<={red[15:11],green[15:10],blue[15:11]};state<=WRITE;end
    WRITE:begin
     if(address==1023) begin done<=1;state<=IDLE;end
     else begin address<=address+1'b1;state<=PIXEL;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
