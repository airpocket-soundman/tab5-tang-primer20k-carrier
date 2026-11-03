// USER clk_out domain only. Output-only observation; never drives the controller.
module mem_deep_monitor(input wire clk,reset_n,start,busy,
 input wire [175:0] native_debug,input wire [63:0] taps,
 output wire [255:0] snapshot);
 reg [31:0] command_advances,write_advances,send_write_cycles;
 reg [2:0] previous_command;
 reg [4:0] previous_write;
 reg [255:0] last_busy,frozen;
 reg frozen_valid;
 wire [2:0] command_delta=taps[5:3]-previous_command;
 wire [4:0] write_delta=taps[20:16]-previous_write;
 wire [255:0] live={95'b0,frozen_valid,send_write_cycles,write_advances,command_advances,taps};
 assign snapshot=frozen_valid?frozen:live;
 always @(posedge clk or negedge reset_n)begin
  if(!reset_n)begin command_advances<=0;write_advances<=0;send_write_cycles<=0;
   previous_command<=0;previous_write<=0;last_busy<=0;frozen<=0;frozen_valid<=0;end
  else if(start)begin command_advances<=0;write_advances<=0;send_write_cycles<=0;
   previous_command<=taps[5:3];previous_write<=taps[20:16];last_busy<=0;frozen<=0;frozen_valid<=0;end
  else begin
   previous_command<=taps[5:3];previous_write<=taps[20:16];
   if(busy&&!frozen_valid)begin
    command_advances<=command_advances+command_delta;
    write_advances<=write_advances+write_delta;
    if(taps[11])send_write_cycles<=send_write_cycles+1'b1;
    last_busy<={95'b0,1'b1,send_write_cycles+(taps[11]?32'd1:32'd0),
      write_advances+{27'b0,write_delta},command_advances+{29'b0,command_delta},taps};
   end
   if(!busy&&native_debug[11]&&!frozen_valid)begin frozen<=last_busy;frozen_valid<=1;end
  end
 end
endmodule
