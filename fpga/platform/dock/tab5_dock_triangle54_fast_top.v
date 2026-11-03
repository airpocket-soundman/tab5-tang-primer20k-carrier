// Experimental source-synchronous tagged replies; identical physical ports.
module tab5_dock_triangle54_fast_top(
    input wire sys_clk, reset_n, arm_sw, bus_clk, dir,
    input wire [3:0] aux, inout wire [7:0] data,
    output wire ready, output wire [3:0] led
);
    wire core_clk,pll_locked;
    wire platform_reset_n=reset_n && pll_locked;
    dock_pll54 clock_gen(.clock_in(sys_clk),.clock_out(core_clk),.locked(pll_locked));
    tab5_dock_top #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(5400000),.CORE_CLOCK_MHZ(54),
                    .CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1)) platform(
        core_clk,platform_reset_n,arm_sw,bus_clk,dir,aux,data,ready,led);
endmodule
