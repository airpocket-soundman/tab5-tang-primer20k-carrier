// Timing-only logic-cone fixture. NEVER program: no LINK/GFX implementation.
module filter_timing_top(input wire sys_clk,reset_n,arm_sw,bus_clk,dir,
    input wire [3:0]aux,inout wire [7:0]data,output wire ready,output wire [3:0]led);
    (* keep *)wire filter_clk;
    wire locked,clean,fault;
    dock_pll216 pll(sys_clk,filter_clk,locked);
    reply_clock_filter clock_conditioner(filter_clk,reset_n && locked && arm_sw,bus_clk,dir,clean,fault);
    assign data=8'bz;
    assign ready=clean;
    assign led={fault,clean,locked,dir};
endmodule
