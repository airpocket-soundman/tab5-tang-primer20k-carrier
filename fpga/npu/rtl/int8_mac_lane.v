// Proposed single-lane arithmetic primitive, not a complete accelerator.
// Synchronous active-high reset; see README.md for handshake and error rules.
module int8_mac_lane (
    input wire clk,
    input wire reset,
    input wire begin_valid,
    output wire begin_ready,
    input wire signed [31:0] bias,
    input wire mac_valid,
    output wire mac_ready,
    input wire signed [7:0] activation,
    input wire signed [7:0] zero_point,
    input wire signed [7:0] weight,
    input wire end_valid,
    output wire end_ready,
    output reg result_valid,
    input wire result_ready,
    output reg signed [31:0] result,
    output reg error,
    output reg active,
    output reg signed [31:0] accumulator
);
    wire signed [8:0] centered;
    wire signed [16:0] product;
    wire signed [32:0] sum;
    wire overflow;

    assign centered = $signed({activation[7], activation}) -
                      $signed({zero_point[7], zero_point});
    assign product = centered * weight;
    assign sum = $signed({accumulator[31], accumulator}) +
                 $signed({{16{product[16]}}, product});
    assign overflow = sum[32] != sum[31];
    assign begin_ready = !active && !result_valid && !error;
    assign mac_ready = active && !error;
    // MAC has priority if both requests are valid; end remains pending.
    assign end_ready = active && !error && !mac_valid;

    always @(posedge clk) begin
        if (reset) begin
            accumulator <= 32'sd0;
            result <= 32'sd0;
            result_valid <= 1'b0;
            error <= 1'b0;
            active <= 1'b0;
        end else begin
            if (result_valid && result_ready)
                result_valid <= 1'b0;
            if (begin_valid && begin_ready) begin
                accumulator <= bias;
                active <= 1'b1;
            end else if (mac_valid && mac_ready) begin
                if (overflow) begin
                    error <= 1'b1;
                    active <= 1'b0;
                    // Keep last valid accumulator; do not publish a result.
                end else begin
                    accumulator <= sum[31:0];
                end
            end else if (end_valid && end_ready) begin
                result <= accumulator;
                result_valid <= 1'b1;
                active <= 1'b0;
            end
        end
    end
endmodule
