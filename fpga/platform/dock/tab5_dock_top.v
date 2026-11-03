// Dock-only top. Raw reset/ARM deassertion removes OE without waiting for clk.
module tab5_dock_top #(
    parameter GFX_ENABLE=0,
    parameter TIMEOUT_CYCLES=2700000,
    parameter CORE_CLOCK_MHZ=27,
    parameter CLOCK_QUERY_ENABLE=0,
    parameter FAST_REPLY_ENABLE=0,
    parameter TX_CAPTURE_ENABLE=0
)(
    input wire sys_clk, reset_n, arm_sw, bus_clk, dir,
    input wire [3:0] aux,
    inout wire [7:0] data,
    output wire ready,
    output wire [3:0] led
);
    reg [2:0] reset_sync=0;
    reg [2:0] arm_sync=0;
    reg [23:0] heartbeat=0;
    wire [7:0] data_o;
    wire data_oe;
    wire core_reset_n=reset_n && reset_sync[2];
    wire arm_reset_n=reset_n && arm_sw;
    wire armed=core_reset_n && arm_sw && arm_sync[2];
    always @(posedge sys_clk or negedge reset_n) begin
        if(!reset_n) begin reset_sync<=0; heartbeat<=0; end
        else begin
            reset_sync<={reset_sync[1:0],1'b1};
            heartbeat<=heartbeat+1'b1;
        end
    end
    always @(posedge sys_clk or negedge arm_reset_n) begin
        if(!arm_reset_n) arm_sync<=0;
        else arm_sync<={arm_sync[1:0],1'b1};
    end
    assign data=data_oe ? data_o : 8'bz;
    link_bringup #(.GFX_ENABLE(GFX_ENABLE), .TIMEOUT_CYCLES(TIMEOUT_CYCLES),
                    .CORE_CLOCK_MHZ(CORE_CLOCK_MHZ),.CLOCK_QUERY_ENABLE(CLOCK_QUERY_ENABLE),.FAST_REPLY_ENABLE(FAST_REPLY_ENABLE),.TX_CAPTURE_ENABLE(TX_CAPTURE_ENABLE)) core(
        sys_clk,core_reset_n,armed,bus_clk,dir,data,data_o,data_oe,ready);
    // Active-low: armed, driving, response ready, slow clock heartbeat.
    assign led=~{heartbeat[23],ready,data_oe,armed};
    // AUX pins intentionally remain inputs; no roles are assigned by this top.
endmodule
