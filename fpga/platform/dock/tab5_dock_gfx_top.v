module tab5_dock_gfx_top(
    input wire sys_clk, reset_n, arm_sw, bus_clk, dir,
    input wire [3:0] aux,
    inout wire [7:0] data,
    output wire ready,
    output wire [3:0] led
);
    tab5_dock_top #(.GFX_ENABLE(1)) platform(
        sys_clk,reset_n,arm_sw,bus_clk,dir,aux,data,ready,led);
endmodule
