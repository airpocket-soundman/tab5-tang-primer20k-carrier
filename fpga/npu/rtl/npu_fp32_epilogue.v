// Isolated FP32 epilogue. RNE, finite normal/zero profile, no FMA.
// error_code: 1 unsupported operand (subnormal/NaN/Inf), 2 overflow,
// 3 nonzero exact result below normal range. Error result is always zero.
module npu_fp32_epilogue(
 input wire clk,reset_n,abort,
 input wire in_valid,output wire in_ready,
 input wire signed [31:0] accumulator,
 input wire [31:0] row_scale,column_scale,alpha,bias,
 input wire bias_enable,
 output reg out_valid,input wire out_ready,
 output reg [31:0] result,output reg error,output reg [3:0] error_code
);
 function unsupported;input[31:0] a;begin
 unsupported=(a[30:23]==255)||(a[30:23]==0&&a[22:0]!=0);
 end endfunction
 // Pack positive integer magnitude times 2^base into a normal FP32.
 function [35:0] pack;input sign;input[63:0] mag;input integer base;
 integer i,top,ex,shift;reg[63:0] q,rem,half;begin
 pack=0;top=0;q=0;rem=0;half=0;ex=0;shift=0;
 if(mag==0)pack={4'd0,sign,31'd0};
 else begin
  for(i=0;i<64;i=i+1)if(mag[i])top=i;
  ex=top+base;
  if(ex < -126)pack={4'd3,32'd0};
  else if(ex>127)pack={4'd2,32'd0};
  else begin
   shift=top-23;
   if(shift>0)begin
    q=mag>>shift;rem=mag&((64'd1<<shift)-1);half=64'd1<<(shift-1);
    if(rem>half||(rem==half&&q[0]))q=q+1'b1;
   end else q=mag<<(-shift);
   if(q[24])begin q=q>>1;ex=ex+1;end
   if(ex>127)pack={4'd2,32'd0};
   else pack={4'd0,sign,8'd0,q[22:0]}|((ex+127)<<23);
  end
 end
 end endfunction
 function[63:0] jam;input[63:0] a;input integer shift;begin
 if(shift==0)jam=a;
 else if(shift>=64)jam={63'd0,|a};
 else jam=(a>>shift)|((a&((64'd1<<shift)-1))!=0);
 end endfunction
 function[35:0] int_float;input[31:0] a;reg[31:0] mag;begin
 mag=a[31]?(~a+1'b1):a;int_float=pack(a[31],{32'd0,mag},0);
 end endfunction
 reg[2:0] state;
 reg[31:0] a,b,af,bf,converted,scaled;
 reg use_bias;
 wire[47:0] product={1'b1,a[22:0]}*{1'b1,b[22:0]};
 reg[35:0] mul_value;
 integer mul_base;
 always @* begin
  mul_base=a[30:23]+b[30:23]-254-46;
  if(unsupported(a)||unsupported(b))mul_value={4'd1,32'd0};
  else if(a[30:0]==0||b[30:0]==0)mul_value={4'd0,(a[31]^b[31]),31'd0};
  else mul_value=pack(a[31]^b[31],{16'd0,product},mul_base);
 end
reg[63:0] add_x,add_y,add_mag;
 reg add_sign,add_sub;
 reg signed[10:0] add_base;
 reg[31:0] greater,lesser;
 integer add_delta;
 always @* begin
  if(scaled[30:0]>=bf[30:0])begin greater=scaled;lesser=bf;end
  else begin greater=bf;lesser=scaled;end
  add_delta=greater[30:23]-lesser[30:23];
 end
 assign in_ready=state==0&&!out_valid&&!abort&&reset_n;
 task publish;input[35:0] value;begin
  error_code<=value[35:32];error<=|value[35:32];
  result<=value[35:32]!=0?32'd0:value[31:0];out_valid<=1;state<=0;
 end endtask
 always @(posedge clk)begin
  if(!reset_n||abort)begin state<=0;out_valid<=0;result<=0;error<=0;error_code<=0;a<=0;b<=0;af<=0;bf<=0;converted<=0;scaled<=0;use_bias<=0;add_x<=0;add_y<=0;add_mag<=0;add_sign<=0;add_sub<=0;add_base<=0;end
  else begin
   if(out_valid&&out_ready)out_valid<=0;
   case(state)
   0:if(in_valid&&in_ready)begin
    if(unsupported(row_scale)||unsupported(column_scale)||unsupported(alpha)||(bias_enable&&unsupported(bias)))publish({4'd1,32'd0});
    else begin converted<=int_float(accumulator);a<=row_scale;b<=column_scale;af<=alpha;bf<=bias;use_bias<=bias_enable;state<=1;end
   end
   1:if(mul_value[35:32]!=0)publish(mul_value);else begin a<=converted;b<=mul_value[31:0];state<=2;end
   2:if(mul_value[35:32]!=0)publish(mul_value);else begin a<=mul_value[31:0];b<=af;state<=3;end
   3:if(mul_value[35:32]!=0)publish(mul_value);else if(!use_bias)publish(mul_value);else begin scaled<=mul_value[31:0];state<=4;end
   4:begin
    if(scaled[30:0]==0&&bf[30:0]==0)publish({4'd0,(scaled[31]&bf[31]),31'd0});
    else if(scaled[30:0]==0)publish({4'd0,bf});
    else if(bf[30:0]==0)publish({4'd0,scaled});
    else begin
     add_x<={8'd0,1'b1,greater[22:0],32'd0};
     add_y<=jam({8'd0,1'b1,lesser[22:0],32'd0},add_delta);
     add_base<=$signed({1'b0,greater[30:23]})-11'sd182;
     add_sign<=greater[31];add_sub<=greater[31]^lesser[31];state<=5;
    end
   end
   5:begin add_mag<=add_sub?add_x-add_y:add_x+add_y;state<=6;end
   6:publish(pack(add_mag==0?1'b0:add_sign,add_mag,$signed(add_base)));
   default:begin state<=0;out_valid<=0;end
   endcase
  end
 end
endmodule
