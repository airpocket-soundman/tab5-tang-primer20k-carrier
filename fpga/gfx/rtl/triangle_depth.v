// Exact G0 depth interpolation. Unsigned 49-step restoring divider; no approximation.
module triangle_depth (
    input wire clk, reset_n, in_valid,
    output wire in_ready,
    input wire covered,
    input wire signed [63:0] area, weight_a, weight_b, weight_c,
    input wire [15:0] za, zb, zc, old_depth,
    output reg out_valid,
    input wire out_ready,
    output reg invalid_input, depth_pass,
    output reg [15:0] new_depth
);
    // Conservative geometric bound: 2 * (65535**2), fits unsigned 33 bits.
    localparam [63:0] MAX_AREA=64'd8589672450;
    wire [65:0] weight_sum={2'b0,weight_a}+{2'b0,weight_b}+{2'b0,weight_c};
    wire valid_shape=area>0 && $unsigned(area)<=MAX_AREA &&
        weight_a>=0 && weight_b>=0 && weight_c>=0 &&
        weight_sum=={2'b0,area};
    wire [48:0] product_a=weight_a[32:0]*za;
    wire [48:0] product_b=weight_b[32:0]*zb;
    wire [48:0] product_c=weight_c[32:0]*zc;
    wire [50:0] numerator={2'b0,product_a}+{2'b0,product_b}+{2'b0,product_c};
    reg busy;
    reg [32:0] divisor, remainder;
    reg [48:0] dividend, quotient;
    reg [5:0] bits_left;
    reg [15:0] saved_old_depth;
    wire [33:0] shifted_remainder={remainder,dividend[48]};
    wire subtract=shifted_remainder>={1'b0,divisor};
    wire [33:0] remainder_next=subtract ? shifted_remainder-{1'b0,divisor}:shifted_remainder;
    wire [48:0] quotient_next={quotient[47:0],subtract};
    assign in_ready=reset_n && !busy && !out_valid;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            busy<=0; out_valid<=0; invalid_input<=0; depth_pass<=0; new_depth<=0;
            divisor<=0; remainder<=0; dividend<=0; quotient<=0; bits_left<=0; saved_old_depth<=0;
        end else begin
            if(out_valid && out_ready) out_valid<=0;
            if(in_valid && in_ready) begin
                invalid_input<=!valid_shape; depth_pass<=0; new_depth<=0;
                if(!valid_shape || !covered) out_valid<=1;
                else begin
                    busy<=1; divisor<=area[32:0]; remainder<=0;
                    dividend<=numerator[48:0]; quotient<=0; bits_left<=49; saved_old_depth<=old_depth;
                end
            end
            if(busy) begin
                remainder<=remainder_next[32:0]; dividend<={dividend[47:0],1'b0}; quotient<=quotient_next;
                bits_left<=bits_left-1'b1;
                if(bits_left==1) begin
                    busy<=0; out_valid<=1; new_depth<=quotient_next[15:0];
                    invalid_input<=0; depth_pass<=quotient_next[15:0]>saved_old_depth;
                end
            end
        end
    end
endmodule
