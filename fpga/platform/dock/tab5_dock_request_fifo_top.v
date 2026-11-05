// Experimental one-tick-shorter qualification; two synchronizer stages retained.
// Frame timer/raw bypass disabled to keep this candidate independent.
module tab5_dock_request_fifo_top(
    input wire sys_clk,reset_n,arm_sw,bus_clk,dir,
    input wire [3:0]aux,inout wire [7:0]data,
    output wire ready,output wire [3:0]led
);
    (* keep *) wire core_clk,filter_clk;
    wire core_locked,filter_locked;
    dock_pll54 core_pll(sys_clk,core_clk,core_locked);
    dock_pll216 filter_pll(sys_clk,filter_clk,filter_locked);
    wire platform_reset_n=reset_n && core_locked && filter_locked;
    reg [2:0]reset_sync=0,arm_sync=0;
    reg [23:0]heartbeat=0;
    wire arm_reset_n=platform_reset_n && arm_sw;
    wire core_reset_n=platform_reset_n && reset_sync[2];
    wire armed=core_reset_n && arm_sw && arm_sync[2];
    always @(posedge core_clk or negedge platform_reset_n)
        if(!platform_reset_n)begin reset_sync<=0;heartbeat<=0;end
        else begin reset_sync<={reset_sync[1:0],1'b1};heartbeat<=heartbeat+1'b1;end
    always @(posedge core_clk or negedge arm_reset_n)
        if(!arm_reset_n)arm_sync<=0;else arm_sync<={arm_sync[1:0],1'b1};
    wire [7:0]data_o;
    wire data_oe;
    assign data=data_oe?data_o:8'bz;
    link_bringup_filtered #(.GFX_ENABLE(2),.ALL_SCENES_ENABLE(1),.FRAME_TIMING_ENABLE(0),.REPLY_RAW_BYPASS(0),.FAST_FILTER_SYNC(1),.REPLY_ACTIVE_PIPELINE(1),.REQUEST_DATA_PIPELINE(1),.REQUEST_CAPTURE_FIFO(1),.TIMEOUT_CYCLES(5400000),.CORE_CLOCK_MHZ(54),
        .CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1)) core(
        core_clk,core_reset_n,armed,bus_clk,dir,data,data_o,data_oe,ready,filter_clk,platform_reset_n && arm_sw);
    assign led=~{heartbeat[23],ready,data_oe,armed};
endmodule
