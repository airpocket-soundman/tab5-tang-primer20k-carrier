// Isolated official-Gowin candidate. No array reset; one-clock registered reads.
// Normal mode00 preserves A output during writes. Renderer cannot consume a
// write-cycle A read, and cannot enable B while A is writing (asserted below).
module tile_dpram_vendor(input wire clk_a,write_a,input wire [9:0]address_a,
    input wire [15:0]data_a,output wire [15:0]q_a,
    input wire clk_b,read_b,input wire [9:0]address_b,output wire [15:0]q_b);
    wire [15:0]unused;
    DPB #(.BIT_WIDTH_0(16),.BIT_WIDTH_1(16),.READ_MODE0(1'b0),.READ_MODE1(1'b0),
        .WRITE_MODE0(2'b00),.WRITE_MODE1(2'b00),.BLK_SEL_0(3'b000),.BLK_SEL_1(3'b000),.RESET_MODE("ASYNC")) memory(
        .DOA(q_a),.DOB(q_b),.DIA(data_a),.DIB(16'b0),.BLKSELA(3'b000),.BLKSELB(3'b000),
        .ADA({address_a,2'b00,2'b11}),.ADB({address_b,4'b0000}),
        .WREA(write_a),.WREB(1'b0),.CLKA(clk_a),.CLKB(clk_b),.CEA(1'b1),.CEB(read_b),
        .OCEA(1'b1),.OCEB(1'b1),.RESETA(1'b0),.RESETB(1'b0));
`ifndef SYNTHESIS
    always @(posedge clk_a)if(write_a && read_b)$fatal(1,"SYS write raced RAW read ownership");
    always @(posedge clk_b)if(read_b && write_a)$fatal(1,"RAW read raced SYS write ownership");
`endif
endmodule
