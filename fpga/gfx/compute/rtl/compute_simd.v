// Experimental, host-independent programmable SIMD core. See ../README.md.
// No transport, DDR PHY, rasterizer, or application-specific operation here.
`timescale 1ns/1ps
module compute_simd #(
    parameter LANES = 2,
    parameter PC_BITS = 8
)(
    input wire clk, input wire reset,
    input wire program_we,
    input wire [PC_BITS-1:0] program_addr,
    input wire [31:0] program_data,
    input wire start,
    input wire [15:0] entry,
    input wire [31:0] group_base,
    input wire [31:0] instruction_limit,
    output reg busy, output reg done,
    output reg [3:0] error,
    output reg [31:0] cycles, output reg [31:0] instructions,
    output wire mem_valid, input wire mem_ready,
    output wire mem_write,
    output wire [31:0] mem_word_addr, output wire [31:0] mem_wdata,
    input wire rsp_valid, output wire rsp_ready,
    input wire [31:0] rsp_data, input wire rsp_error
);
    localparam WORDS = 1 << PC_BITS;
    localparam LANE_BITS = $clog2(LANES+1);
    localparam IDLE=0, FETCH=1, EXEC=2, MEM_SELECT=3, MEM_REQ=4, MEM_RSP=5;
    localparam HALT=0, LDI=1, ADD=2, SUB=3, MUL=4, MULQ=5,
               LT=6, AND_=7, XOR_=8, SHL=9, SAR=10,
               LOAD=11, STORE=12, JMP=13, ANY=14;
    reg [2:0] state;
    reg [31:0] program_mem [0:WORDS-1];
    reg [WORDS-1:0] loaded;
    reg [31:0] regs [0:LANES*16-1];
    reg [PC_BITS:0] pc;
    reg [31:0] insn, limit;
    reg [LANES-1:0] memory_mask;
    reg [31:0] memory_addr [0:LANES-1];
    reg [31:0] memory_data [0:LANES-1];
    reg [3:0] memory_dst;
    reg memory_write;
    reg [LANE_BITS-1:0] memory_lane;
    integer i;
    wire [5:0] op = insn[31:26];
    wire predicated = insn[25];
    wire [3:0] dst=insn[24:21], srca=insn[20:17], srcb=insn[16:13];
    wire signed [31:0] immediate = {{16{insn[15]}},insn[15:0]};
    wire [LANES-1:0] enabled, branch_bits;
    wire signed [31:0] a [0:LANES-1];
    wire signed [31:0] b [0:LANES-1];
    wire signed [63:0] product [0:LANES-1];
    genvar lane;
`ifndef SYNTHESIS
    initial begin
        if (LANES<1 || LANES>4 || PC_BITS<1 || PC_BITS>16)
            $fatal(1,"unsupported compute_simd parameters");
    end
`endif
    generate for (lane=0; lane<LANES; lane=lane+1) begin: operands
        assign a[lane] = srca==0 ? 32'sd0 : regs[lane*16+srca];
        assign b[lane] = srcb==0 ? 32'sd0 : regs[lane*16+srcb];
        assign product[lane] = a[lane]*b[lane];
        assign enabled[lane] = !predicated || regs[lane*16+15]!=0;
        assign branch_bits[lane] = a[lane]!=0;
    end endgenerate
    assign mem_valid = busy && state==MEM_REQ;
    assign mem_write = memory_write;
    assign mem_word_addr = memory_addr[memory_lane];
    assign mem_wdata = memory_data[memory_lane];
    assign rsp_ready = busy && state==MEM_RSP;

    task finish;
        input [3:0] code;
        begin busy<=0; done<=1; error<=code; state<=IDLE; end
    endtask

    always @(posedge clk) begin
        if (reset) begin
            busy<=0; done<=0; error<=0; state<=IDLE;
            loaded<=0; pc<=0; insn<=0; limit<=0;
            cycles<=0; instructions<=0; memory_lane<=0;
            memory_mask<=0; memory_dst<=0; memory_write<=0;
            for (i=0;i<LANES*16;i=i+1) regs[i]<=0;
            for (i=0;i<LANES;i=i+1) begin memory_addr[i]<=0; memory_data[i]<=0; end
        end else begin
            done<=0;
            if (!busy) begin
                // Program writes and launch are mutually exclusive; writes win.
                if (program_we) begin
                    program_mem[program_addr]<=program_data;
                    loaded[program_addr]<=1;
                end else if (start) begin
                    cycles<=0; instructions<=0; error<=0;
                    if (entry>=WORDS) finish(3);
                    else if (instruction_limit==0) finish(5);
                    else begin
                        busy<=1; state<=FETCH; pc<=entry; limit<=instruction_limit;
                        for (i=0;i<LANES*16;i=i+1) regs[i]<=0;
                        for (i=0;i<LANES;i=i+1) regs[i*16+1]<=group_base+i;
                    end
                end
            end else begin
                cycles<=cycles+1;
                case (state)
                    FETCH: begin
                        if (pc>=WORDS) finish(3);
                        else if (!loaded[pc[PC_BITS-1:0]]) finish(2);
                        else if (instructions>=limit) finish(5);
                        else begin
                            insn<=program_mem[pc[PC_BITS-1:0]];
                            state<=EXEC;
                        end
                    end
                    EXEC: begin
                        instructions<=instructions+1;
                        pc<=pc+1;
                        state<=FETCH;
                        if (op==HALT) finish(predicated ? 1 : 0);
                        else if (op==JMP || op==ANY) begin
                            // Flow instructions cannot be predicated.
                            if (predicated) finish(1);
                            else if (op==JMP || |branch_bits) begin
                                if (insn[15:0]>=WORDS) finish(3);
                                else pc<=insn[15:0];
                            end
                        end else if (op==LOAD || op==STORE) begin
                            memory_lane<=0; memory_dst<=dst; memory_write<=op==STORE;
                            memory_mask<=enabled;
                            for (i=0;i<LANES;i=i+1) begin
                                memory_addr[i]<=a[i]+immediate;
                                memory_data[i]<=dst==0 ? 32'd0 : regs[i*16+dst];
                            end
                            state<=MEM_SELECT;
                        end else if (op>ANY) finish(1);
                        else begin
                            for (i=0;i<LANES;i=i+1) begin
                                if (enabled[i] && dst!=0) begin
                                    case (op)
                                        LDI: regs[i*16+dst]<=immediate;
                                        ADD: regs[i*16+dst]<=a[i]+b[i];
                                        SUB: regs[i*16+dst]<=a[i]-b[i];
                                        MUL: regs[i*16+dst]<=product[i][31:0];
                                        MULQ: regs[i*16+dst]<=product[i] >>> 12;
                                        LT: regs[i*16+dst]<=a[i]<b[i] ? 32'd1 : 32'd0;
                                        AND_: regs[i*16+dst]<=a[i]&b[i];
                                        XOR_: regs[i*16+dst]<=a[i]^b[i];
                                        SHL: regs[i*16+dst]<=a[i]<<b[i][4:0];
                                        SAR: regs[i*16+dst]<=a[i]>>>b[i][4:0];
                                        default: finish(1);
                                    endcase
                                end
                            end
                        end
                    end
                    MEM_SELECT: begin
                        if (memory_lane==LANES) state<=FETCH;
                        else if (!memory_mask[memory_lane]) memory_lane<=memory_lane+1;
                        else state<=MEM_REQ;
                    end
                    MEM_REQ: if (mem_ready) state<=MEM_RSP;
                    MEM_RSP: if (rsp_valid) begin
                        if (rsp_error) finish(4);
                        else begin
                            if (!memory_write && memory_dst!=0)
                                regs[memory_lane*16+memory_dst]<=rsp_data;
                            memory_lane<=memory_lane+1;
                            state<=MEM_SELECT;
                        end
                    end
                    default: finish(1);
                endcase
            end
        end
    end
endmodule
