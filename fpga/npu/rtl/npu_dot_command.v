// NPU-DOT-v0. Separate from GFX/MEM. One checked INT8 dot, no DDR/model graph.
module npu_dot_command(
 input wire clk,reset,start,input wire [7:0] opcode,a,b,
 output reg done,output reg [7:0] status,output reg [15:0] result);
 reg [7:0] cfg[0:20];reg [20:0] written;
 reg core_reset,pending;reg [7:0] op,sa,sw;reg [10:0] watchdog;
 wire begin_ready,sample_ready,result_valid,busy,error;
 wire [1:0] error_code;wire signed [7:0] quantized;wire signed [31:0] accumulated;
 reg job_active;reg [31:0] job_cycles,compute_cycles;
 wire begin_fire=pending && op==8'h52 && begin_ready && !error;
 wire sample_fire=pending && op==8'h53 && sample_ready && !error;
 wire result_fire=pending && op==8'h54 && result_valid && !error;
 wire [31:0] length={cfg[20],cfg[19],cfg[18],cfg[17]};
 integer i;
 int8_dot_job dot(.clk(clk),.reset(reset || core_reset),
  .begin_valid(pending && op==8'h52),.begin_ready(begin_ready),
  .bias({cfg[3],cfg[2],cfg[1],cfg[0]}),.input_zero_point({cfg[9],cfg[8]}),
  .multiplier({cfg[7],cfg[6],cfg[5],cfg[4]}),.shift(cfg[10][6:0]),
  .output_zero_point({cfg[12],cfg[11]}),.lower({cfg[14],cfg[13]}),.upper({cfg[16],cfg[15]}),
  .length(length),.sample_valid(pending && op==8'h53),.sample_ready(sample_ready),
  .activation(sa),.weight(sw),.result_valid(result_valid),.result_ready(result_fire),
  .result(quantized),.busy(busy),.error(error),.error_code(error_code),.accumulated(accumulated));
 always @(posedge clk) begin
  if(reset) begin
   done<=0;status<=0;result<=0;written<=0;core_reset<=1;pending<=0;op<=0;sa<=0;sw<=0;watchdog<=0;
   job_active<=0;job_cycles<=0;compute_cycles<=0;
   for(i=0;i<21;i=i+1)cfg[i]<=0;
  end else begin
   done<=0;core_reset<=0;
   if(job_active) begin
    if(result_valid || error)job_active<=0;
    else begin
     if(job_cycles!=32'hffffffff)job_cycles<=job_cycles+1'b1;
     // Excludes host gaps in STREAM and result-consumption wait.
     if(busy && (!sample_ready || sample_fire) && compute_cycles!=32'hffffffff)compute_cycles<=compute_cycles+1'b1;
    end
   end
   if(pending) begin
    watchdog<=watchdog+1'b1;
    if(error) begin status<=error_code==2?8'd5:8'd3;done<=1;pending<=0;end
    else if(begin_fire || sample_fire || result_fire) begin
     result<=result_fire?{{8{quantized[7]}},quantized}:16'd0;
     status<=0;done<=1;pending<=0;
     if(begin_fire)begin job_active<=1;job_cycles<=0;compute_cycles<=0;end
    end else if(watchdog==1023) begin
     status<=7;done<=1;pending<=0;core_reset<=1;written<=0;job_active<=0;
    end
   end else if(start) begin
    status<=0;result<=0;done<=1;
    case(opcode)
     8'h50: if({b,a}==0)result<=16'h4e01;else status<=3;
     8'h55: if({b,a}==0)begin core_reset<=1;written<=0;job_active<=0;job_cycles<=0;compute_cycles<=0;end else status<=3;
     8'h51: if(a>=21)status<=3;else if(busy || error)status<=4;else begin cfg[a]<=b;written[a]<=1;end
     8'h52: if({b,a}!=0 || written!=21'h1fffff || cfg[10]>62 || length>1024)status<=3;
             else if(busy || error || core_reset)status<=4;
             else begin pending<=1;op<=opcode;watchdog<=0;done<=0;end
     8'h53: if(error)status<=error_code==2?5:3;else if(!busy || result_valid)status<=4;
             else begin pending<=1;op<=opcode;sa<=a;sw<=b;watchdog<=0;done<=0;end
     8'h54: if({b,a}!=0)status<=3;else if(error)status<=error_code==2?5:3;else if(!busy)status<=4;
             else begin pending<=1;op<=opcode;watchdog<=0;done<=0;end
     8'h56,8'h57,8'h58,8'h59,8'h5a,8'h5b:
       if({b,a}!=0)status<=3;else if(error)status<=error_code==2?5:3;else if(!result_valid)status<=4;
       else case(opcode)
        8'h56:result<=job_cycles[15:0];8'h57:result<=job_cycles[31:16];
        8'h58:result<=compute_cycles[15:0];8'h59:result<=compute_cycles[31:16];
        8'h5a:result<=accumulated[15:0];8'h5b:result<=accumulated[31:16];
       endcase
     default:status<=2;
    endcase
   end
  end
 end
endmodule
