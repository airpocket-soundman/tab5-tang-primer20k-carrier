// Experimental27x8=216MHz; VCO216x4=864MHz. Hardware not yet qualified.
module dock_pll216(input wire clock_in,output wire clock_out,output wire locked);
    rPLL #(.FCLKIN("27.0"),.IDIV_SEL(0),.FBDIV_SEL(7),.ODIV_SEL(4)) pll(
        .CLKOUTP(),.CLKOUTD(),.CLKOUTD3(),.RESET(1'b0),.RESET_P(1'b0),.CLKFB(1'b0),
        .FBDSEL(6'b0),.IDSEL(6'b0),.ODSEL(6'b0),.PSDA(4'b0),.DUTYDA(4'b0),.FDLY(4'b0),
        .CLKIN(clock_in),.CLKOUT(clock_out),.LOCK(locked));
endmodule
