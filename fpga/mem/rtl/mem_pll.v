// Public rPLL primitive, based on official Sipeed PLL port/attribute usage.
// 27*(11+1)/(0+1)=324MHz; ODIV2 gives648MHz VCO.
module mem_pll(input wire clk,reset,output wire memory_clk,locked);
rPLL pll(.CLKIN(clk),.RESET(reset),.RESET_P(1'b0),.CLKFB(1'b0),
.FBDSEL(6'b0),.IDSEL(6'b0),.ODSEL(6'b0),.PSDA(4'b0),.DUTYDA(4'b0),.FDLY(4'b0),
.CLKOUT(memory_clk),.LOCK(locked),.CLKOUTP(),.CLKOUTD(),.CLKOUTD3());
defparam pll.FCLKIN="27",pll.DYN_IDIV_SEL="false",pll.IDIV_SEL=0,
pll.DYN_FBDIV_SEL="false",pll.FBDIV_SEL=11,pll.DYN_ODIV_SEL="false",pll.ODIV_SEL=2,
pll.PSDA_SEL="0000",pll.DYN_DA_EN="true",pll.DUTYDA_SEL="1000",
pll.CLKOUT_FT_DIR=1'b1,pll.CLKOUTP_FT_DIR=1'b1,pll.CLKOUT_DLY_STEP=0,pll.CLKOUTP_DLY_STEP=0,
pll.CLKFB_SEL="internal",pll.CLKOUT_BYPASS="false",pll.CLKOUTP_BYPASS="false",
pll.CLKOUTD_BYPASS="false",pll.DYN_SDIV_SEL=2,pll.CLKOUTD_SRC="CLKOUT",
pll.CLKOUTD3_SRC="CLKOUT",pll.DEVICE="GW2A-18C";
endmodule
