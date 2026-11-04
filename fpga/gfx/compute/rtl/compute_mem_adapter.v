// Memory adapter between compute_simd and a word-addressed backend (DDR/BRAM
// controller wrapper). Offline prototype; see ../README.md "Memory adapter".
//  * region check: word address must fall in an enabled region with the needed
//    permission, otherwise the core gets rsp_error without any backend access
//  * timeout: if the backend does not answer within `timeout_cycles` (0 = off),
//    the core gets rsp_error; a request already accepted by the backend becomes
//    an "orphan" whose late response is discarded, and new requests are held off
//    until every orphan has been answered (ordering is preserved)
//  * job boundary: `flush` drops a pending response and orphans an in-flight
//    request, so a stale response can never reach the next job
// A backend that never answers an orphan blocks the adapter until reset; the
// backend must be reset together with the adapter. Hold-until-accept is kept
// on the backend side except when the timeout fires before be_ready (the dead
// backend request is then withdrawn).
`timescale 1ns/1ps
module compute_mem_adapter #(
    parameter REGIONS = 2
)(
    input wire clk, input wire reset,
    input wire flush,
    input wire [31:0] timeout_cycles,
    input wire [REGIONS*32-1:0] region_base,    // word index, inclusive
    input wire [REGIONS*32-1:0] region_limit,   // word index, exclusive
    input wire [REGIONS*2-1:0] region_perm,     // [2r]=read, [2r+1]=write
    input wire mem_valid, output wire mem_ready,
    input wire mem_write,
    input wire [31:0] mem_word_addr, input wire [31:0] mem_wdata,
    input wire [3:0] mem_wmask,
    output wire rsp_valid, input wire rsp_ready,
    output wire [31:0] rsp_data, output wire rsp_error,
    output wire be_valid, input wire be_ready,
    output wire be_write,
    output wire [31:0] be_addr, output wire [31:0] be_wdata,
    output wire [3:0] be_wmask,
    input wire be_rsp_valid, input wire [31:0] be_rsp_data, input wire be_rsp_error,
    output reg [15:0] orphans,
    output reg [31:0] violations, output reg [31:0] timeouts
);
    localparam IDLE=0, FWD=1, WAIT=2, RSP=3;
    reg [1:0] st;
    reg q_write, kill, r_err;
    reg [31:0] q_addr, q_wdata, r_data, timer;
    reg [3:0] q_wmask;
    integer r;
    reg hit, inc;
    wire dec = be_rsp_valid && orphans!=0 && st!=WAIT;
    always @* begin
        hit = 0;
        for (r=0;r<REGIONS;r=r+1)
            if (mem_word_addr >= region_base[r*32+:32] && mem_word_addr < region_limit[r*32+:32]
                && region_perm[r*2 + (mem_write ? 1 : 0)])
                hit = 1;
    end
    wire expired = timeout_cycles!=0 && timer>=timeout_cycles;
    assign mem_ready = st==IDLE && orphans==0 && !flush;
    assign be_valid = st==FWD;
    assign be_write = q_write; assign be_addr = q_addr;
    assign be_wdata = q_wdata; assign be_wmask = q_wmask;
    assign rsp_valid = st==RSP;
    assign rsp_data = r_data; assign rsp_error = r_err;

    always @(posedge clk) begin
        if (reset) begin
            st<=IDLE; q_write<=0; kill<=0; r_err<=0; q_addr<=0; q_wdata<=0; r_data<=0;
            timer<=0; q_wmask<=0; orphans<=0; violations<=0; timeouts<=0;
        end else begin
            // A backend response with no waiting request belongs to an orphan.
            inc = 1'b0;
            case (st)
                IDLE: if (mem_valid && mem_ready) begin
                    q_write<=mem_write; q_addr<=mem_word_addr; q_wdata<=mem_wdata; q_wmask<=mem_wmask;
                    timer<=0; kill<=0;
                    if (hit) st<=FWD;
                    else begin st<=RSP; r_err<=1; r_data<=0; violations<=violations+1; end
                end
                FWD: begin
                    timer<=timer+1;
                    if (be_ready) begin
                        st<=WAIT; timer<=0;
                        if (kill) begin st<=IDLE; inc = 1'b1; end
                    end else if (expired && !kill) begin
                        st<=RSP; r_err<=1; r_data<=0; timeouts<=timeouts+1;   // request withdrawn
                    end else if (expired && kill) st<=IDLE;
                    if (flush) kill<=1;
                end
                WAIT: begin
                    timer<=timer+1;
                    if (be_rsp_valid) begin
                        if (flush) st<=IDLE;
                        else begin st<=RSP; r_err<=be_rsp_error; r_data<=be_rsp_data; end
                    end else if (flush) begin st<=IDLE; inc = 1'b1; end
                    else if (expired) begin
                        st<=RSP; r_err<=1; r_data<=0; inc = 1'b1; timeouts<=timeouts+1;
                    end
                end
                RSP: if (rsp_ready || flush) st<=IDLE;
            endcase
            orphans <= orphans + {15'd0,inc} - {15'd0,dec};
        end
    end
endmodule
