// Diagnostic 32x32 color/depth tile. Exact G0 fragment unit, one pixel in flight.
// No DDR3, no performance claim. Abort invalidates RAM until a complete clear.
module triangle_tile(
    input wire clk, reset_n, abort, start,
    input wire [7:0] opcode, a, b,
    output reg done,
    output reg [7:0] status,
    output reg [15:0] result,
    input wire [5:0] row_index,
    output wire [7:0] row_byte
);
    localparam IDLE=0, CLEAR=1, READ_WAIT=2, READ_DONE=3,
               SCAN_WAIT=4, SUBMIT=5, WAIT_RESULT=6, COMPLETE=7,
               ROW_WAIT=8, ROW_CAPTURE=9;
    reg [3:0] state;
    reg initialized, read_depth;
    reg [9:0] address;
    reg [9:0] configured;
    reg [15:0] params[0:9];
    reg [15:0] colors[0:1023], depths[0:1023];
    reg [15:0] color_q, depth_q, clear_color;
    reg [15:0] written;
    reg [15:0] row_cache[0:31];
    // Snapshot data is immutable while the link sends the response. It is not
    // exposed until all 32 synchronous RAM reads have completed.
    assign row_byte = row_index[0] ? row_cache[row_index[5:1]][15:8]
                                        : row_cache[row_index[5:1]][7:0];
    wire fragment_ready, fragment_valid, fragment_write;
    wire covered, degenerate, invalid_input, depth_pass;
    wire [15:0] new_depth, out_color;
    wire [9:0] out_x;
    wire [8:0] out_y;
    wire active = reset_n && !abort;
    triangle_fragment fragment(
        .clk(clk), .reset_n(active), .in_valid(state==SUBMIT), .in_ready(fragment_ready),
        .ax(params[0]), .ay(params[1]), .bx(params[2]), .by(params[3]),
        .cx(params[4]), .cy(params[5]), .za(params[6]), .zb(params[7]),
        .zc(params[8]), .old_depth(depth_q), .color(params[9]),
        .pixel_x({5'b0,address[4:0]}), .pixel_y({4'b0,address[9:5]}),
        .out_valid(fragment_valid), .out_ready(state==WAIT_RESULT),
        .covered(covered), .degenerate(degenerate), .invalid_input(invalid_input),
        .depth_pass(depth_pass), .write_enable(fragment_write),
        .new_depth(new_depth), .out_color(out_color), .out_x(out_x), .out_y(out_y)
    );
    // Synchronous RAM reads. No array reset, so block RAM can be inferred.
    always @(posedge clk) begin
        if(active && state==CLEAR) begin
            colors[address]<=clear_color; depths[address]<=0;
        end else if(active && state==WAIT_RESULT && fragment_write) begin
            colors[address]<=out_color; depths[address]<=new_depth;
        end
        color_q<=colors[address]; depth_q<=depths[address];
    end
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            state<=IDLE; initialized<=0; configured<=0; address<=0;
            done<=0; status<=0; result<=0; written<=0; read_depth<=0; clear_color<=0;
        end else if(abort) begin
            state<=IDLE; initialized<=0; configured<=0; address<=0;
            done<=0; status<=0; result<=0; written<=0;
        end else begin
            done<=0;
            case(state)
                IDLE: if(start) begin
                    status<=0; result<=0;
                    if(opcode>=8'h21 && opcode<=8'h2a) begin
                        params[opcode-8'h21]<={b,a};
                        configured[opcode-8'h21]<=1; result<={b,a}; done<=1;
                    end else case(opcode)
                        8'h20: begin result<=16'h2020; done<=1; end
                        8'h2b: begin address<=0; clear_color<={b,a}; written<=0; initialized<=0; state<=CLEAR; end
                        8'h2c: begin
                            if(a!=0 || b!=0) begin status<=3; done<=1; end
                            else if(!initialized || !(&configured)) begin status<=5; done<=1; end
                            else begin address<=0; written<=0; state<=SCAN_WAIT; end
                        end
                        8'h2d,8'h2e: begin
                            if(a>=32 || b>=32) begin status<=3; done<=1; end
                            else if(!initialized) begin status<=5; done<=1; end
                            else begin
                                address<={b[4:0],a[4:0]}; read_depth<=opcode==8'h2e; state<=READ_WAIT;
                            end
                        end
                        8'h2f: begin
                            if(a>=32 || b>1) begin status<=3; done<=1; end
                            else if(!initialized) begin status<=5; done<=1; end
                            else begin
                                address<={a[4:0],5'b0}; read_depth<=b[0];
                                result<={b,a}; state<=ROW_WAIT;
                            end
                        end
                        default: begin status<=2; done<=1; end
                    endcase
                end
                CLEAR: if(address==1023) begin initialized<=1; state<=COMPLETE; end
                       else address<=address+1'b1;
                READ_WAIT: state<=READ_DONE;
                READ_DONE: begin result<=read_depth ? depth_q : color_q; done<=1; state<=IDLE; end
                ROW_WAIT: state<=ROW_CAPTURE;
                ROW_CAPTURE: begin
                    row_cache[address[4:0]]<=read_depth ? depth_q : color_q;
                    if(address[4:0]==31) begin done<=1; state<=IDLE; end
                    else begin address<=address+1'b1; state<=ROW_WAIT; end
                end
                SCAN_WAIT: state<=SUBMIT;
                SUBMIT: if(fragment_ready) state<=WAIT_RESULT;
                WAIT_RESULT: if(fragment_valid) begin
                    if(invalid_input) begin status<=3; initialized<=0; state<=COMPLETE; end
                    else begin
                        if(fragment_write) written<=written+1'b1;
                        if(address==1023) state<=COMPLETE;
                        else begin address<=address+1'b1; state<=SCAN_WAIT; end
                    end
                end
                COMPLETE: begin result<=written; done<=1; state<=IDLE; end
                default: begin initialized<=0; state<=IDLE; end
            endcase
        end
    end
endmodule
