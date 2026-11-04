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
    input wire [31:0] element_count,   // 0: one group, all lanes valid (legacy)
    input wire [31:0] instruction_limit,
    output reg busy, output reg done,
    output reg [3:0] error,
    output reg [31:0] cycles, output reg [31:0] instructions,
    output reg [31:0] groups,
    output wire mem_valid, input wire mem_ready,
    output wire mem_write,
    output wire [31:0] mem_word_addr, output wire [31:0] mem_wdata,
    output wire [3:0] mem_wmask,
    input wire rsp_valid, output wire rsp_ready,
    input wire [31:0] rsp_data, input wire rsp_error
);
    localparam WORDS = 1 << PC_BITS;
    localparam LANE_BITS = $clog2(LANES+1);
    localparam IDLE=0, FETCH=1, EXEC=2, MEM_SELECT=3, MEM_REQ=4, MEM_RSP=5,
               DIV_SEL=6, DIV_RUN=7;
    localparam HALT=0, LDI=1, ADD=2, SUB=3, MUL=4, MULQ=5,
               LT=6, AND_=7, XOR_=8, SHL=9, SAR=10,
               LOAD=11, STORE=12, JMP=13, ANY=14,
               MIN=15, MAX=16, ABS=17, SAT8=18, PK565=19, UP565=20,
               LDB=21, LDBS=22, LDH=23, LDHS=24, STB=25, STH=26,
               ADDI=27, MULI=28, LTI=29, ANDI=30, SHLI=31, SARI=32, SHRI=33, LUI=34,
               SHR=35, LTU=36, EQ=37, NE=38, OR_=39, SEL=40, MULSH=41,
               DIV=42, REM=43, ATOMADD=44, LDU=45;
    localparam [LANES-1:0] LANE0 = 1;
    reg [2:0] state;
    reg [31:0] program_mem [0:WORDS-1];
    reg [WORDS-1:0] loaded;
    reg [31:0] regs [0:LANES*16-1];
    reg [PC_BITS:0] pc;
    reg [31:0] insn, limit, entry_r, base_r, count_r, remaining;
    reg [LANES-1:0] memory_mask, uni_mask;
    reg [3:0] memory_mask_bytes [0:LANES-1];
    reg [31:0] memory_addr [0:LANES-1];
    reg [31:0] memory_data [0:LANES-1];
    reg [3:0] memory_dst;
    reg memory_write, memory_atom, memory_uni;
    reg [1:0] memory_size;   // 0 word, 1 byte, 2 halfword
    reg memory_sext;
    reg [1:0] memory_off [0:LANES-1];
    reg [LANE_BITS-1:0] memory_lane;
    // serial restoring divider (one lane at a time)
    reg [LANES-1:0] div_mask;
    reg [LANE_BITS-1:0] div_lane;
    reg [5:0] div_cnt;
    reg [32:0] div_rem;
    reg [31:0] div_quo, div_den;
    reg div_neg_q, div_neg_r, div_is_rem;
    reg [32:0] t_rem;
    reg [31:0] t_quo, t_res;
    integer i;
    wire [5:0] op = insn[31:26];
    wire predicated = insn[25];
    wire [3:0] dst=insn[24:21], srca=insn[20:17], srcb=insn[16:13];
    wire signed [31:0] immediate = {{16{insn[15]}},insn[15:0]};
    wire [LANES-1:0] valid, enabled, branch_bits, misaligned;
    wire [31:0] ea [0:LANES-1];
    wire is_half = op==LDH || op==LDHS || op==STH;
    wire word_op = op==LOAD || op==STORE || op==ATOMADD || op==LDU;
    wire is_mem = word_op || (op>=LDB && op<=STH);
    wire is_store = op==STORE || op==STB || op==STH;
    reg [31:0] load_shift;
    reg [31:0] load_value;
    wire signed [31:0] a [0:LANES-1];
    wire signed [31:0] b [0:LANES-1];
    wire signed [31:0] bsel [0:LANES-1];
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
        assign bsel[lane] = op==MULI ? immediate : b[lane];
        assign product[lane] = a[lane]*bsel[lane];
        assign valid[lane] = count_r==0 || remaining > lane;
        assign enabled[lane] = valid[lane] && (!predicated || regs[lane*16+15]!=0);
        assign branch_bits[lane] = valid[lane] && a[lane]!=0;
        assign ea[lane] = a[lane]+immediate;
        assign misaligned[lane] = enabled[lane] && is_half && ea[lane][0];
    end endgenerate
    assign mem_valid = busy && state==MEM_REQ;
    assign mem_write = memory_write;
    assign mem_word_addr = memory_addr[memory_lane];
    assign mem_wmask = memory_write ? memory_mask_bytes[memory_lane] : 4'd0;
    assign mem_wdata = memory_data[memory_lane];
    assign rsp_ready = busy && state==MEM_RSP;

    always @* begin
        load_shift = rsp_data >> {memory_off[memory_lane],3'b000};
        case (memory_size)
            2'd1: load_value = memory_sext ? {{24{load_shift[7]}},load_shift[7:0]} : {24'd0,load_shift[7:0]};
            2'd2: load_value = memory_sext ? {{16{load_shift[15]}},load_shift[15:0]} : {16'd0,load_shift[15:0]};
            default: load_value = rsp_data;
        endcase
    end

    task finish;
        input [3:0] code;
        begin busy<=0; done<=1; error<=code; state<=IDLE; end
    endtask

    // Begin a group at `base`: registers cleared, r1 = base+lane.
    task begin_group;
        input [31:0] base;
        begin
            for (i=0;i<LANES*16;i=i+1) regs[i]<=0;
            for (i=0;i<LANES;i=i+1) regs[i*16+1]<=base+i;
        end
    endtask

    always @(posedge clk) begin
        if (reset) begin
            busy<=0; done<=0; error<=0; state<=IDLE;
            loaded<=0; pc<=0; insn<=0; limit<=0; entry_r<=0; base_r<=0;
            count_r<=0; remaining<=0; groups<=0;
            cycles<=0; instructions<=0; memory_lane<=0;
            memory_mask<=0; uni_mask<=0; memory_dst<=0; memory_write<=0;
            memory_atom<=0; memory_uni<=0;
            div_mask<=0; div_lane<=0; div_cnt<=0; div_rem<=0; div_quo<=0; div_den<=0;
            div_neg_q<=0; div_neg_r<=0; div_is_rem<=0;
            for (i=0;i<LANES*16;i=i+1) regs[i]<=0;
            for (i=0;i<LANES;i=i+1) begin memory_addr[i]<=0; memory_data[i]<=0; memory_mask_bytes[i]<=0; memory_off[i]<=0; end
            memory_size<=0; memory_sext<=0;
        end else begin
            done<=0;
            if (!busy) begin
                // Program writes and launch are mutually exclusive; writes win.
                if (program_we) begin
                    program_mem[program_addr]<=program_data;
                    loaded[program_addr]<=1;
                end else if (start) begin
                    cycles<=0; instructions<=0; error<=0; groups<=0;
                    if (entry>=WORDS) finish(3);
                    else if (instruction_limit==0) finish(5);
                    else begin
                        busy<=1; state<=FETCH; pc<=entry; limit<=instruction_limit;
                        entry_r<=entry; base_r<=group_base;
                        count_r<=element_count; remaining<=element_count;
                        begin_group(group_base);
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
                        if (op==HALT) begin
                            if (predicated) finish(1);
                            else begin
                                groups<=groups+1;
                                if (count_r!=0 && remaining>LANES) begin
                                    remaining<=remaining-LANES;
                                    base_r<=base_r+LANES;
                                    pc<=entry_r[PC_BITS-1:0];
                                    begin_group(base_r+LANES);
                                end else finish(0);
                            end
                        end else if (op==JMP || op==ANY) begin
                            // Flow instructions cannot be predicated.
                            if (predicated) finish(1);
                            else if (op==JMP || |branch_bits) begin
                                if (insn[15:0]>=WORDS) finish(3);
                                else pc<=insn[15:0];
                            end
                        end else if (is_mem) begin
                            if (|misaligned) finish(6);
                            else begin
                                memory_lane<=0; memory_dst<=dst; memory_write<=is_store;
                                memory_atom<=op==ATOMADD;
                                memory_uni<=op==LDU;
                                uni_mask<=enabled;
                                memory_mask<= op==LDU ? ((|enabled) ? LANE0 : {LANES{1'b0}}) : enabled;
                                memory_size<=(op==LDB||op==LDBS||op==STB) ? 2'd1 :
                                             is_half ? 2'd2 : 2'd0;
                                memory_sext<=(op==LDBS||op==LDHS);
                                for (i=0;i<LANES;i=i+1) begin
                                    memory_addr[i]<=(op==LDU && i!=0) ? ea[0] :
                                                    (word_op ? ea[i] : {2'b00,ea[i][31:2]});
                                    memory_off[i]<=word_op ? 2'd0 : ea[i][1:0];
                                    if (op==STB) begin
                                        memory_data[i]<={4{regs[i*16+dst][7:0]}};
                                        memory_mask_bytes[i]<=4'b0001<<ea[i][1:0];
                                    end else if (op==STH) begin
                                        memory_data[i]<={2{regs[i*16+dst][15:0]}};
                                        memory_mask_bytes[i]<=ea[i][1] ? 4'b1100 : 4'b0011;
                                    end else begin
                                        memory_data[i]<=dst==0 ? 32'd0 : regs[i*16+dst];
                                        memory_mask_bytes[i]<=4'b1111;
                                    end
                                end
                                state<=MEM_SELECT;
                            end
                        end else if (op==DIV || op==REM) begin
                            div_mask<= dst==0 ? {LANES{1'b0}} : enabled;
                            div_lane<=0; div_is_rem<=op==REM;
                            state<=DIV_SEL;
                        end else if (op>LDU) finish(1);
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
                                        MIN: regs[i*16+dst]<=a[i]<b[i] ? a[i] : b[i];
                                        MAX: regs[i*16+dst]<=a[i]<b[i] ? b[i] : a[i];
                                        ABS: regs[i*16+dst]<=a[i]<0 ? -a[i] : a[i];
                                        SAT8: regs[i*16+dst]<=a[i]<0 ? 32'd0 : a[i]>255 ? 32'd255 : a[i];
                                        PK565: regs[i*16+dst]<={16'd0,a[i][23:19],a[i][15:10],a[i][7:3]};
                                        UP565: regs[i*16+dst]<={8'd0,a[i][15:11],a[i][15:13],
                                                                a[i][10:5],a[i][10:9],a[i][4:0],a[i][4:2]};
                                        ADDI: regs[i*16+dst]<=a[i]+immediate;
                                        MULI: regs[i*16+dst]<=product[i][31:0];
                                        LTI: regs[i*16+dst]<=a[i]<immediate ? 32'd1 : 32'd0;
                                        ANDI: regs[i*16+dst]<=a[i]&{16'd0,insn[15:0]};
                                        SHLI: regs[i*16+dst]<=a[i]<<insn[4:0];
                                        SARI: regs[i*16+dst]<=a[i]>>>insn[4:0];
                                        SHRI: regs[i*16+dst]<=$unsigned(a[i])>>insn[4:0];
                                        LUI: regs[i*16+dst]<={insn[15:0],16'd0};
                                        SHR: regs[i*16+dst]<=$unsigned(a[i])>>b[i][4:0];
                                        LTU: regs[i*16+dst]<=$unsigned(a[i])<$unsigned(b[i]) ? 32'd1 : 32'd0;
                                        EQ: regs[i*16+dst]<=a[i]==b[i] ? 32'd1 : 32'd0;
                                        NE: regs[i*16+dst]<=a[i]!=b[i] ? 32'd1 : 32'd0;
                                        OR_: regs[i*16+dst]<=a[i]|b[i];
                                        SEL: regs[i*16+dst]<=regs[i*16+dst]!=0 ? a[i] : b[i];
                                        MULSH: regs[i*16+dst]<=product[i] >>> insn[5:0];
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
                        else if (memory_atom && !memory_write) begin
                            // read phase of ATOMADD: write back old+r[d] as the second request
                            memory_data[memory_lane]<=rsp_data+memory_data[memory_lane];
                            memory_write<=1;
                            state<=MEM_REQ;
                        end else begin
                            if (!memory_write && !memory_atom && memory_dst!=0) begin
                                if (memory_uni) begin
                                    for (i=0;i<LANES;i=i+1)
                                        if (uni_mask[i]) regs[i*16+memory_dst]<=load_value;
                                end else regs[memory_lane*16+memory_dst]<=load_value;
                            end
                            if (memory_atom) memory_write<=0;
                            memory_lane<=memory_lane+1;
                            state<=MEM_SELECT;
                        end
                    end
                    DIV_SEL: begin
                        if (div_lane==LANES) state<=FETCH;
                        else if (!div_mask[div_lane]) div_lane<=div_lane+1;
                        else if (b[div_lane]==0) begin
                            regs[div_lane*16+dst]<=div_is_rem ? a[div_lane] : 32'hffffffff;
                            div_lane<=div_lane+1;
                        end else begin
                            div_quo<= a[div_lane]<0 ? -a[div_lane] : a[div_lane];
                            div_den<= b[div_lane]<0 ? -b[div_lane] : b[div_lane];
                            div_neg_q<= a[div_lane][31]^b[div_lane][31];
                            div_neg_r<= a[div_lane][31];
                            div_rem<=0; div_cnt<=0;
                            state<=DIV_RUN;
                        end
                    end
                    DIV_RUN: begin
                        t_rem = {div_rem[31:0],div_quo[31]};
                        t_quo = {div_quo[30:0],1'b0};
                        if (t_rem >= {1'b0,div_den}) begin
                            t_rem = t_rem - {1'b0,div_den};
                            t_quo[0] = 1'b1;
                        end
                        div_rem<=t_rem; div_quo<=t_quo; div_cnt<=div_cnt+1;
                        if (div_cnt==31) begin
                            t_res = div_is_rem ? (div_neg_r ? -t_rem[31:0] : t_rem[31:0])
                                               : (div_neg_q ? -t_quo : t_quo);
                            regs[div_lane*16+dst]<=t_res;
                            div_lane<=div_lane+1;
                            state<=DIV_SEL;
                        end
                    end
                    default: finish(1);
                endcase
            end
        end
    end
endmodule
