// One immutable validated command bank. No execution before trailer CRC.
module triangle_batch #(parameter BASE_OP=8'h21, parameter DRAW_OP=8'h2c, parameter UPLOAD_MODE=0, parameter REGISTER_INPUT=0)(input wire clk,reset_n,abort,start,
 input wire [6:0] count,input wire [15:0] header_crc,
 input wire byte_valid,input wire [7:0] byte_data,
 output wire receiving,output wire busy,output reg done,
 output reg [7:0] status,output reg cmd_start,
 output wire [7:0] cmd_opcode,output wire [7:0] cmd_a,cmd_b,
 input wire cmd_done,input wire [7:0] cmd_status);
 localparam IDLE=0,RX=1,CRC_LO=2,CRC_HI=3,FETCH=4,LATCH=5,ISSUE=6,WAIT_CMD=7;
 reg [3:0] state;reg [15:0] words[0:639];
 reg [9:0] address,total_words;reg half;reg [7:0] low,crc_low;
 reg [15:0] crc,ram_q,command_word;reg [3:0] field;
 // Optional SYS-domain byte capture. Both CRC and RAM consume the same
 // registered byte on the following clock; the package-pad path never feeds
 // the high-byte RAM input directly in this mode. This is a timing candidate,
 // not proof of signal integrity or a substitute for CRC/physical validation.
 wire input_valid;
 wire [7:0] input_data;
 generate if(REGISTER_INPUT) begin: registered_input
  reg captured_valid;
  reg [7:0] captured_data;
  always @(posedge clk or negedge reset_n) begin
   if(!reset_n) begin captured_valid<=0;captured_data<=0;end
   else if(abort) begin captured_valid<=0;captured_data<=0;end
   else begin
    captured_valid<=byte_valid;
    if(byte_valid) captured_data<=byte_data;
   end
  end
  assign input_valid=captured_valid;
  assign input_data=captured_data;
 end else begin: direct_input
  assign input_valid=byte_valid;
  assign input_data=byte_data;
 end endgenerate
 assign receiving=state==RX || state==CRC_LO || state==CRC_HI;
 assign busy=state!=IDLE;
 assign cmd_opcode=field==10 ? DRAW_OP : (UPLOAD_MODE?BASE_OP:BASE_OP+field);
 assign cmd_a=field==10 ? 0:command_word[7:0];
 assign cmd_b=field==10 ? 0:command_word[15:8];
 function [15:0] crc_byte;
 input [15:0] c;input [7:0] b;reg [15:0] v;integer k;
 begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
 endfunction
 // Unreset synchronous single-port RAM, write only complete staged words.
 always @(posedge clk) begin
  if(state==RX && input_valid && half) words[address]<={input_data,low};
  else ram_q<=words[address];
 end
 always @(posedge clk or negedge reset_n) begin
  if(!reset_n) begin state<=IDLE;done<=0;cmd_start<=0;status<=0;address<=0;total_words<=0;half<=0;low<=0;crc_low<=0;crc<=0;field<=0;command_word<=0;end
  else begin
   done<=0;cmd_start<=0;
   if(abort) begin state<=IDLE;half<=0;address<=0;end
   else case(state)
    IDLE: if(start) begin state<=RX;total_words<=count*10;address<=0;half<=0;crc<=header_crc;status<=0;end
    RX: if(input_valid) begin
      crc<=crc_byte(crc,input_data);half<=!half;
      if(!half) low<=input_data;
      else if(address+1==total_words) state<=CRC_LO;
      else address<=address+1'b1;
    end
    CRC_LO: if(input_valid) begin crc_low<=input_data;state<=CRC_HI;end
    CRC_HI: if(input_valid) begin
      if({input_data,crc_low}!=crc) begin status<=1;done<=1;state<=IDLE;end
      else begin address<=0;field<=0;state<=FETCH;end
    end
    FETCH:state<=LATCH;
    LATCH:begin command_word<=ram_q;state<=ISSUE;end
    ISSUE:begin cmd_start<=1;state<=WAIT_CMD;end
    WAIT_CMD:if(cmd_done) begin
      if(cmd_status!=0) begin status<=cmd_status;done<=1;state<=IDLE;end
      else if(field==10) begin
       if(address+1==total_words) begin status<=0;done<=1;state<=IDLE;end
       else begin address<=address+1'b1;field<=0;state<=FETCH;end
      end else if(field==9) begin field<=10;state<=ISSUE;end
      else begin address<=address+1'b1;field<=field+1'b1;state<=FETCH;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
