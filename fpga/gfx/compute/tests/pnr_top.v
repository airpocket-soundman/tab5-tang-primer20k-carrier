// Place-and-route harness ONLY (not a hardware design). The core has ~300 port
// bits, more than the GW2A-18 PG256 can expose, so inputs arrive through one
// serial shift register and all outputs are reduced to one parity bit.
// Registering both sides adds ~600 FFs not present in a real integration.
`timescale 1ns/1ps
module pnr_top #(parameter LANES = 2, parameter PC_BITS = 8)(
    input wire clk, input wire si, output wire so
);
    localparam O_RST=0, O_WE=1, O_PA=2, O_PD=O_PA+PC_BITS, O_ST=O_PD+32, O_EN=O_ST+1,
               O_GB=O_EN+16, O_CNT=O_GB+32, O_LIM=O_CNT+32, O_RDY=O_LIM+32, O_RV=O_RDY+1,
               O_RD=O_RV+1, O_RE=O_RD+32, IN_BITS=O_RE+1;
    reg [IN_BITS-1:0] in_sr = 0;
    always @(posedge clk) in_sr <= {in_sr[IN_BITS-2:0], si};
    wire [IN_BITS-1:0] v = in_sr;
    wire busy, done, mem_valid, mem_write, rsp_ready;
    wire [3:0] error, mem_wmask;
    wire [31:0] cycles, instructions, groups, mem_word_addr, mem_wdata;
    compute_simd #(.LANES(LANES), .PC_BITS(PC_BITS)) dut(
        .clk(clk), .reset(v[O_RST]), .program_we(v[O_WE]), .program_addr(v[O_PA+:PC_BITS]),
        .program_data(v[O_PD+:32]), .start(v[O_ST]), .entry(v[O_EN+:16]),
        .group_base(v[O_GB+:32]), .element_count(v[O_CNT+:32]), .instruction_limit(v[O_LIM+:32]),
        .busy(busy), .done(done), .error(error), .cycles(cycles), .instructions(instructions), .groups(groups),
        .mem_valid(mem_valid), .mem_ready(v[O_RDY]), .mem_write(mem_write),
        .mem_word_addr(mem_word_addr), .mem_wdata(mem_wdata), .mem_wmask(mem_wmask),
        .rsp_valid(v[O_RV]), .rsp_ready(rsp_ready),
        .rsp_data(v[O_RD+:32]), .rsp_error(v[O_RE]));
    reg [172:0] out_r = 0;
    always @(posedge clk)
        out_r <= {busy, done, error, cycles, instructions, groups, mem_valid, mem_write, rsp_ready,
                  mem_word_addr, mem_wdata, mem_wmask};
    assign so = ^out_r;
endmodule
