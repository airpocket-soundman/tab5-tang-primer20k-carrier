// Standalone MEM image uses the established slow, SYS-synchronized LINK PHY.
// Initial physical validation must use <=500kHz, not the GFX raw-clock ceiling.
module mem_link #(parameter TIMEOUT=2700000,parameter BW_ENABLE=0)(
 input wire clk,reset_n,arm,bus_clk,dir,input wire[7:0] data_i,
 output reg[7:0] data_o,output wire data_oe,ready,
 output reg command_start,output reg[7:0] opcode,a,b,
 input wire command_done,input wire[7:0] command_status,input wire[15:0] command_result
);
reg[2:0] clk_sync;reg[1:0] dir_sync;wire rise=clk_sync[1]&&!clk_sync[2];
reg[7:0] request[0:6];reg[7:0] reply[0:5];reg[2:0] rx_index;
reg[4:0] tx_index;reg valid,pending,prefix;reg[31:0] idle;
reg[15:0] rx_crc,reply_crc;integer j;
wire prefacing=prefix&&tx_index<8;wire[4:0] logical_index=tx_index-(prefix?8:0);
function[15:0] crc;input[15:0] old;input[7:0] byte_value;reg[15:0] v;integer k;
begin v=old^{byte_value,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end endfunction
assign ready=reset_n&&arm&&valid;
assign data_oe=reset_n&&arm&&dir&&dir_sync[1]&&valid;
always @*begin
reply_crc=16'hffff;for(j=0;j<6;j=j+1)reply_crc=crc(reply_crc,reply[j]);
if(prefacing)data_o=8'hc3;
else if(logical_index<6)data_o=reply[logical_index];
else if(logical_index==6)data_o=reply_crc[7:0];else data_o=reply_crc[15:8];
end
always @(posedge clk or negedge reset_n)begin
if(!reset_n)begin clk_sync<=0;dir_sync<=0;rx_index<=0;tx_index<=0;
valid<=0;pending<=0;prefix<=0;idle<=0;rx_crc<=16'hffff;
command_start<=0;opcode<=0;a<=0;b<=0;end
else begin
clk_sync<={clk_sync[1:0],bus_clk};dir_sync<={dir_sync[0],dir};command_start<=0;
if(!arm||idle>=TIMEOUT-1)begin rx_index<=0;tx_index<=0;valid<=0;pending<=0;
prefix<=0;idle<=0;rx_crc<=16'hffff;end
else begin
idle<=idle+1;
if(pending&&command_done)begin
pending<=0;valid<=1;reply[1]<=command_status;reply[4]<=command_result[7:0];reply[5]<=command_result[15:8];end
if(dir_sync[1]&&rx_index!=0)begin rx_index<=0;rx_crc<=16'hffff;end
if(rise)begin
idle<=0;
if(!dir&&!dir_sync[1]&&!valid&&!pending)begin
if(rx_index<7)request[rx_index]<=data_i;
if(rx_index<6)rx_crc<=crc(rx_crc,data_i);
if(rx_index==7)begin
rx_index<=0;rx_crc<=16'hffff;valid<=1;tx_index<=0;
reply[0]<=8'h5a;reply[1]<=0;reply[2]<=request[2];reply[3]<=2;reply[4]<=0;reply[5]<=0;
prefix<=request[1][7]&&request[0]==8'ha5&&request[3]==2&&request[6]==rx_crc[7:0]&&data_i==rx_crc[15:8];
if(request[0]!=8'ha5||request[3]!=2||request[6]!=rx_crc[7:0]||data_i!=rx_crc[15:8])reply[1]<=1;
else case(request[1]&8'h7f)
1:begin reply[4]<=8'h54;reply[5]<=8'h50;end
2:begin reply[4]<=request[4];reply[5]<=request[5];end
3:begin reply[4]<=~request[4];reply[5]<=~request[5];end
4:begin reply[4]<=8;reply[5]<=1;end
8'h50,8'h51,8'h52,8'h53,8'h54,8'h55,8'h56,8'h57,8'h58,8'h59,8'h5a,8'h5b,8'h5c:begin
opcode<=request[1]&8'h7f;a<=request[4];b<=request[5];command_start<=1;pending<=1;valid<=0;end
default:if(BW_ENABLE!=0&&(request[1]&8'h70)==8'h60)begin
// 0x60..0x6F: DDR3 bandwidth engine (mem_bw_port); only dispatched when the image contains it
opcode<=request[1]&8'h7f;a<=request[4];b<=request[5];command_start<=1;pending<=1;valid<=0;end
else reply[1]<=2;
endcase
end else rx_index<=rx_index+1;
end else if(dir&&dir_sync[1]&&valid)begin
if(!prefacing&&logical_index==7)begin valid<=0;tx_index<=0;prefix<=0;end
else tx_index<=tx_index+1;
end end end end end
endmodule
