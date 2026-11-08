// CRC-32/ISO-HDLC (zlib, reflected 0xEDB88320) one-byte step on the raw (non-inverted) register.
// Caller seeds the register with ~previous_crc (all ones for a new message) and inverts the result.
module memv1_crc32b(input wire[31:0] crc,input wire[7:0] data,output reg[31:0] next);
integer k;reg[31:0] v;
always @* begin
v=crc^{24'b0,data};
for(k=0;k<8;k=k+1)v=v[0]?(v>>1)^32'hedb88320:(v>>1);
next=v;
end
endmodule

// Simple dual-port RAM, independent write/read clocks, registered read (one-cycle latency).
module memv1_dpram #(parameter AW=8,parameter DW=128)(
 input wire wclk,we,input wire[AW-1:0] waddr,input wire[DW-1:0] wdata,
 input wire rclk,input wire[AW-1:0] raddr,output reg[DW-1:0] rdata);
reg[DW-1:0] mem[0:(1<<AW)-1];
always @(posedge wclk) if(we) mem[waddr]<=wdata;
always @(posedge rclk) rdata<=mem[raddr];
endmodule
