// One serial dot-product job. Existing MAC/requantizer interfaces are unchanged.
module int8_dot_job (
    input wire clk, input wire reset,
    input wire begin_valid, output wire begin_ready,
    input wire signed [31:0] bias,
    input wire signed [15:0] input_zero_point,
    input wire signed [31:0] multiplier,
    input wire [6:0] shift,
    input wire signed [15:0] output_zero_point,
    input wire signed [15:0] lower, input wire signed [15:0] upper,
    input wire [31:0] length,
    input wire sample_valid, output wire sample_ready,
    input wire signed [7:0] activation, input wire signed [7:0] weight,
    output wire result_valid, input wire result_ready,
    output wire signed [7:0] result,
    output wire busy, output wire error, output wire [1:0] error_code
);
    localparam IDLE=3'd0, START=3'd1, STREAM=3'd2, FINISH=3'd3,
               QUANT=3'd4, OUTPUT=3'd5, FAULT=3'd6;
    reg [2:0] state;
    reg [1:0] fault_code;
    reg signed [31:0] saved_bias, saved_multiplier;
    reg signed [7:0] saved_input_zero;
    reg [6:0] saved_shift;
    reg signed [15:0] saved_output_zero, saved_lower, saved_upper;
    reg [31:0] remaining;
    wire config_valid;
    wire mac_begin_ready, mac_ready, mac_end_ready, mac_result_valid, mac_error;
    wire signed [31:0] mac_result;
    wire quant_ready, quant_valid, quant_error;
    wire any_fault;
    assign config_valid = input_zero_point >= -16'sd128 && input_zero_point <= 16'sd127 &&
        !multiplier[31] && shift <= 7'd62 &&
        output_zero_point >= -16'sd128 && output_zero_point <= 16'sd127 &&
        lower >= -16'sd128 && upper <= 16'sd127 && lower <= upper;
    assign any_fault = state==FAULT || mac_error || quant_error;
    assign error = any_fault;
    assign error_code = mac_error ? 2'd2 : (quant_error ? 2'd1 : fault_code);
    assign busy = state != IDLE;
    assign begin_ready = state==IDLE && !any_fault;
    assign sample_ready = state==STREAM && remaining!=0 && mac_ready && !any_fault;
    assign result_valid = state==OUTPUT && quant_valid && !any_fault;

    int8_mac_lane mac (
        .clk(clk), .reset(reset),
        .begin_valid(state==START && !any_fault), .begin_ready(mac_begin_ready), .bias(saved_bias),
        .mac_valid(sample_valid && sample_ready), .mac_ready(mac_ready),
        .activation(activation), .zero_point(saved_input_zero), .weight(weight),
        .end_valid(state==FINISH && !any_fault), .end_ready(mac_end_ready),
        .result_valid(mac_result_valid), .result_ready(state==QUANT && quant_ready && !any_fault),
        .result(mac_result), .error(mac_error), .active(), .accumulator()
    );
    int8_requantize quant (
        .clk(clk), .reset(reset),
        .input_valid(state==QUANT && mac_result_valid && !any_fault), .input_ready(quant_ready),
        .accumulator(mac_result), .multiplier(saved_multiplier), .shift(saved_shift),
        .zero_point(saved_output_zero), .lower(saved_lower), .upper(saved_upper),
        .output_valid(quant_valid), .output_ready(state==OUTPUT && result_ready && !any_fault),
        .result(result), .error(quant_error)
    );

    always @(posedge clk) begin
        if (reset) begin
            state<=IDLE; fault_code<=0; remaining<=0;
            saved_bias<=0; saved_multiplier<=0; saved_input_zero<=0;
            saved_shift<=0; saved_output_zero<=0; saved_lower<=0; saved_upper<=0;
        end else if (mac_error || quant_error) begin
            state<=FAULT;
            fault_code<=mac_error ? 2'd2 : 2'd1;
        end else case (state)
            IDLE: if (begin_valid && begin_ready) begin
                if (!config_valid) begin state<=FAULT; fault_code<=2'd1; end
                else begin
                    saved_bias<=bias; saved_input_zero<=input_zero_point[7:0];
                    saved_multiplier<=multiplier; saved_shift<=shift;
                    saved_output_zero<=output_zero_point; saved_lower<=lower; saved_upper<=upper;
                    remaining<=length; state<=START;
                end
            end
            START: if (mac_begin_ready) state <= remaining==0 ? FINISH : STREAM;
            STREAM: if (sample_valid && sample_ready) begin
                remaining<=remaining-1'b1;
                if (remaining==1) state<=FINISH;
            end
            FINISH: if (mac_end_ready) state<=QUANT;
            QUANT: if (mac_result_valid && quant_ready) state<=OUTPUT;
            OUTPUT: if (result_valid && result_ready) state<=IDLE;
            default: state<=FAULT;
        endcase
    end
endmodule
