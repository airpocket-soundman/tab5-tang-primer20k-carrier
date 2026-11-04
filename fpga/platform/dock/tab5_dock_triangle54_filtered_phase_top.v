// Experimental reply-phase sweep top. Same ports and core as
// tab5_dock_triangle54_filtered_top (the qualified 85bac224 source) plus two
// build-time knobs on the reply DATA phase:
//   REPLY_PHASE_TICKS 0..15 : coarse, whole reply clock delayed by N x 4.63ns
//                             (216MHz sampler ticks)
//   REPLY_FINE_DLY    0..127: fine, IODELAY C_STATIC_DLY on each DATA output
//                             (about 18ps per step on GW2A-18, UG289 4.4.1)
// Both 0 reproduces the qualified design. IODELAY serves the output path only;
// the DATA pad's request-input path is not delayed.
module tab5_dock_triangle54_filtered_phase_top #(
    parameter REPLY_PHASE_TICKS = 0,
    parameter REPLY_FINE_DLY = 0
)(
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
    wire [7:0]data_pad;
    generate if(REPLY_FINE_DLY==0) begin: fine_none
        assign data_pad=data_o;
    end else begin: fine_delay
        genvar i;
        for(i=0;i<8;i=i+1) begin: dly_bit
            IODELAY #(.C_STATIC_DLY(REPLY_FINE_DLY)) odly(
                .DI(data_o[i]),.SDTAP(1'b0),.SETN(1'b0),.VALUE(1'b0),.DO(data_pad[i]),.DF());
        end
    end endgenerate
    assign data=data_oe?data_pad:8'bz;
    link_bringup_filtered #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(5400000),.CORE_CLOCK_MHZ(54),
        .CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1),.REPLY_PHASE_TICKS(REPLY_PHASE_TICKS)) core(
        core_clk,core_reset_n,armed,bus_clk,dir,data,data_o,data_oe,ready,filter_clk,platform_reset_n && arm_sw);
    assign led=~{heartbeat[23],ready,data_oe,armed};
endmodule
