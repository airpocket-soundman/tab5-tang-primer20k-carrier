// Prototype scalar requantizer. Arithmetic contract: compute_reference.requantize.
// Params are deliberately wider than valid values so invalid requests are rejected.
module int8_requantize (
    input wire clk,
    input wire reset,
    input wire input_valid,
    output wire input_ready,
    input wire signed [31:0] accumulator,
    input wire signed [31:0] multiplier,
    input wire [6:0] shift,
    input wire signed [15:0] zero_point,
    input wire signed [15:0] lower,
    input wire signed [15:0] upper,
    output reg output_valid,
    input wire output_ready,
    output reg signed [7:0] result,
    output reg error
);
    wire params_valid;
    reg signed [63:0] product;
    reg [63:0] magnitude;
    reg [63:0] rounding;
    reg signed [63:0] rounded;
    reg signed [63:0] shifted_zero;
    reg signed [7:0] quantized;

    assign input_ready = !output_valid && !error;
    assign params_valid = !multiplier[31] && shift <= 7'd62 &&
        zero_point >= -16'sd128 && zero_point <= 16'sd127 &&
        lower >= -16'sd128 && upper <= 16'sd127 && lower <= upper;

    always @* begin
        // Explicit sign extension fixes expression width independently of context.
        product = $signed({{32{accumulator[31]}}, accumulator}) *
                  $signed({{32{multiplier[31]}}, multiplier});
        magnitude = product < 0 ? $unsigned(-product) : $unsigned(product);
        rounding = 64'd0;
        if (shift > 0 && shift <= 62)
            rounding = 64'd1 << (shift - 1'b1);
        rounded = $signed((magnitude + rounding) >> shift);
        if (product < 0) rounded = -rounded;
        shifted_zero = rounded + $signed({{48{zero_point[15]}}, zero_point});
        if (shifted_zero < $signed({{48{lower[15]}}, lower}))
            quantized = lower[7:0];
        else if (shifted_zero > $signed({{48{upper[15]}}, upper}))
            quantized = upper[7:0];
        else
            quantized = shifted_zero[7:0];
    end

    always @(posedge clk) begin
        if (reset) begin
            output_valid <= 1'b0;
            result <= 8'sd0;
            error <= 1'b0;
        end else begin
            if (output_valid && output_ready) output_valid <= 1'b0;
            if (input_valid && input_ready) begin
                if (!params_valid) begin
                    error <= 1'b1;
                    // Invalid request publishes nothing and preserves prior result.
                end else begin
                    result <= quantized;
                    output_valid <= 1'b1;
                end
            end
        end
    end
endmodule
