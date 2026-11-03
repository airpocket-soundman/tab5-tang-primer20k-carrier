// Experimental reply-clock phase offset. Delays the conditioned reply clock by
// TICKS cycles of the sampling clock (216MHz: ~4.63ns per tick). Every pulse is
// delayed by the same amount, so pulse width and spacing are unchanged. Used
// only when REPLY_PHASE_TICKS>0; the default netlist does not instantiate it.
module reply_phase_delay #(parameter TICKS = 1)(
    input wire sample_clk, reset_n, clean_in,
    output wire clean_out
);
    (* keep = "true" *) reg [TICKS-1:0] shift;
    always @(posedge sample_clk or negedge reset_n)
        if(!reset_n) shift <= {TICKS{1'b0}};
        else if(TICKS==1) shift <= clean_in;
        else shift <= {shift[TICKS-2:0],clean_in};
    assign clean_out = shift[TICKS-1];
endmodule
