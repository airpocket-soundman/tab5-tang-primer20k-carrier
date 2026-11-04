// Behavioural stand-in for the Gowin LUT1 primitive (simulation only; the real
// build uses the vendor primitive). F = I0 ? INIT[1] : INIT[0].
module LUT1 #(parameter [1:0] INIT = 2'h0)(output F, input I0);
    assign F = I0 ? INIT[1] : INIT[0];
endmodule
