// Diagnostic whole-response clock delay, one216MHz tick ~=4.63ns.
// Serializer and read RAM must use the same delayed clock. Default0 bypass
// is implemented in memv1_sys, so this module requires TICKS>=1.
module reply_phase_delay #(parameter TICKS=1)(
 input wire sample_clk,reset_n,clean_in,output wire clean_out
);
(* keep = "true" *) reg [TICKS-1:0] shift;
generate if(TICKS==1)begin: one_tick
 always @(posedge sample_clk or negedge reset_n)
  if(!reset_n)shift<=0;else shift<=clean_in;
end else begin: several_ticks
 always @(posedge sample_clk or negedge reset_n)
  if(!reset_n)shift<=0;else shift<={shift[TICKS-2:0],clean_in};
end endgenerate
assign clean_out=shift[TICKS-1];
endmodule
