// Experimental 27 MHz core image: triangle GFX plus the resident triangle model (MODEL_*).
// Slow-clock functional bring-up variant (no PLL, no fast reply); same physical ports.
module tab5_dock_triangle_model_top(
    input wire sys_clk, reset_n, arm_sw, bus_clk, dir,
    input wire [3:0] aux, inout wire [7:0] data,
    output wire ready, output wire [3:0] led
);
    tab5_dock_top #(.GFX_ENABLE(2),.MODEL_ENABLE(1)) platform(
        sys_clk,reset_n,arm_sw,bus_clk,dir,aux,data,ready,led);
endmodule
