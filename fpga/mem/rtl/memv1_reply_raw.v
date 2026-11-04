// MEMV1 response-only serializer. Metadata is a SYS-held bundle: the caller
// captures it, waits two SYS cycles, then raises offer (reset_n here). No
// metadata/RAM changes are allowed until done/abort returns to SYS.
// Host samples OLD data at the raw bus rising edge. The conditioned rising
// edge advances this serializer afterwards. A synchronous 128-bit RAM port
// prefetches one beat ahead, including the untagged eight-byte header case.
module memv1_reply_raw(
 input wire clk,reset_n,dir,
 input wire [47:0] header,input wire [1:0] kind,input wire [8:0] beats,
 input wire [31:0] crc32_value,input wire prefix,input wire [127:0] ram_data,
 output reg [7:0] data_o,output reg [7:0] ram_addr,
 output reg done,started,progress,error
);
reg [12:0] index;
reg [15:0] crc;
reg [127:0] current_word;
wire prefacing=prefix&&index<8;
wire [12:0] li=index-(prefix?13'd8:13'd0);
wire [12:0] pi=li-13'd8;
wire [12:0] payload_end=13'd8+{beats,4'b0};
wire payload_rd=kind==1&&li>=8&&li<payload_end;
wire payload_crc=kind==2&&li>=8&&li<12;
wire [12:0] body_size=kind==1?payload_end+13'd2:kind==2?13'd14:13'd8;
function [15:0] crc_byte;
 input [15:0] old;input [7:0] b;reg [15:0] v;integer k;
 begin v=old^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
endfunction
reg [15:0] header_crc;integer j;
always @*begin
 header_crc=16'hffff;
 for(j=0;j<6;j=j+1)header_crc=crc_byte(header_crc,header[j*8+:8]);
 data_o=0;
 if(prefacing)data_o=8'hc3;
 else if(li<6)data_o=header[li*8+:8];
 else if(li==6)data_o=header_crc[7:0];
 else if(li==7)data_o=header_crc[15:8];
 else if(payload_rd)data_o=current_word[pi[3:0]*8+:8];
 else if(payload_crc)data_o=crc32_value[(li-8)*8+:8];
 else if(li==body_size-2)data_o=crc[7:0];
 else if(li==body_size-1)data_o=crc[15:8];
end
always @(posedge clk or negedge reset_n)begin
 if(!reset_n)begin
  index<=0;crc<=16'hffff;ram_addr<=0;current_word<=0;
  done<=0;started<=0;progress<=0;error<=0;
 end else if(!dir)begin
  if(started&&!done)begin done<=1;error<=1;end
 end else if(!done)begin
  started<=1;
  // RAM word0 has had two synchronous read edges by index2.
  if(index==2)begin current_word<=ram_data;ram_addr<=1;end
  if(payload_rd&&pi[3:0]==15&&pi[11:4]!=beats-1'b1)begin
   current_word<=ram_data;
   if(pi[11:4]<254)ram_addr<=pi[11:4]+2'd2;
  end
  if(!prefacing&&li<6)crc<=crc_byte(crc,data_o);
  else if(payload_rd||payload_crc)crc<=crc_byte(crc,data_o);
  if(index[3:0]==15)progress<=~progress;
  if(!prefacing&&li==body_size-1)done<=1;
  else index<=index+1'b1;
 end
end
endmodule
