// One candidate in flight. No DDR, scissor, bounding-box traversal or framebuffer.
module triangle_fragment (
    input wire clk, reset_n, in_valid,
    output wire in_ready,
    input wire signed [15:0] ax,ay,bx,by,cx,cy,
    input wire [15:0] za,zb,zc,old_depth,color,
    input wire [9:0] pixel_x,
    input wire [8:0] pixel_y,
    output wire out_valid,
    input wire out_ready,
    output reg covered,degenerate,invalid_input,depth_pass,
    output wire write_enable,
    output reg [15:0] new_depth,out_color,
    output reg [9:0] out_x,
    output reg [8:0] out_y
);
    localparam IDLE=3'd0, WAIT_COVERAGE=3'd1, SEND_DEPTH=3'd2,
               WAIT_DEPTH=3'd3, HOLD_RESULT=3'd4;
    reg [2:0] state;
    reg [15:0] saved_za,saved_zb,saved_zc,saved_old;
    reg signed [63:0] saved_area,saved_wa,saved_wb,saved_wc;
    wire cov_valid,cov_covered,cov_degenerate,cov_swapped;
    wire signed [63:0] cov_area,cov_wa,cov_wb,cov_wc;
    wire depth_ready,depth_valid,depth_invalid,depth_passed;
    wire [15:0] depth_value;
    wire accept=in_valid && in_ready;
    assign in_ready=reset_n && state==IDLE;
    assign out_valid=reset_n && state==HOLD_RESULT;
    // A write occurs only on a consumed valid, covered, depth-passing result.
    assign write_enable=out_valid && out_ready && covered && !degenerate && !invalid_input && depth_pass;
    triangle_coverage coverage_unit (
        .clk(clk),.reset_n(reset_n),.in_valid(accept),
        .ax(ax),.ay(ay),.bx(bx),.by(by),.cx(cx),.cy(cy),
        .pixel_x(pixel_x),.pixel_y(pixel_y),.out_valid(cov_valid),
        .covered(cov_covered),.degenerate(cov_degenerate),.winding_swapped(cov_swapped),
        .area(cov_area),.weight_a(cov_wa),.weight_b(cov_wb),.weight_c(cov_wc)
    );
    triangle_depth depth_unit (
        .clk(clk),.reset_n(reset_n),.in_valid(state==SEND_DEPTH),.in_ready(depth_ready),
        .covered(1'b1),.area(saved_area),.weight_a(saved_wa),.weight_b(saved_wb),.weight_c(saved_wc),
        .za(saved_za),.zb(saved_zb),.zc(saved_zc),.old_depth(saved_old),
        .out_valid(depth_valid),.out_ready(state==WAIT_DEPTH),
        .invalid_input(depth_invalid),.depth_pass(depth_passed),.new_depth(depth_value)
    );
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            state<=IDLE; saved_za<=0; saved_zb<=0; saved_zc<=0; saved_old<=0;
            saved_area<=0; saved_wa<=0; saved_wb<=0; saved_wc<=0;
            covered<=0; degenerate<=0; invalid_input<=0; depth_pass<=0;
            new_depth<=0; out_color<=0; out_x<=0; out_y<=0;
        end else case(state)
            IDLE: if(accept) begin
                saved_za<=za; saved_zb<=zb; saved_zc<=zc; saved_old<=old_depth;
                out_x<=pixel_x; out_y<=pixel_y; out_color<=color;
                state<=WAIT_COVERAGE;
            end
            WAIT_COVERAGE: if(cov_valid) begin
                covered<=cov_covered; degenerate<=cov_degenerate;
                invalid_input<=0; depth_pass<=0; new_depth<=0;
                if(!cov_covered || cov_degenerate) state<=HOLD_RESULT;
                else begin
                    saved_area<=cov_area; saved_wa<=cov_wa; saved_wb<=cov_wb; saved_wc<=cov_wc;
                    state<=SEND_DEPTH;
                end
            end
            SEND_DEPTH: if(depth_ready) state<=WAIT_DEPTH;
            WAIT_DEPTH: if(depth_valid) begin
                invalid_input<=depth_invalid; depth_pass<=depth_passed; new_depth<=depth_value;
                state<=HOLD_RESULT;
            end
            HOLD_RESULT: if(out_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
