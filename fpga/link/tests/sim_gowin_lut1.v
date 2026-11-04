// Simulation-only behavioural stand-in for the Gowin LUT1 primitive (F = INIT[I0]).
// Used only because the vendor primitive library is not installed in the offline environment;
// link_bringup_filtered uses it as a keep-buffer (INIT=2'h2). Not part of any image.
module LUT1 #(parameter [1:0] INIT=2'b00)(output F,input I0);
    assign F=INIT[I0];
endmodule
