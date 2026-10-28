// Electrical wrapper example ONLY. Not a board top; arm must stay 0 until reviewed.
module link_bus_wrapper(input wire sys_clk, reset_n, arm, bus_clk, dir,
                        inout wire [7:0] data, output wire ready);
    wire [7:0] data_o;
    wire oe;
    assign data=oe ? data_o : 8'bz;
    link_bringup core(sys_clk,reset_n,arm,bus_clk,dir,data,data_o,oe,ready);
endmodule
