// Official Tang Primer 20K Dock only; 27 MHz, low-speed link v0.
module dock_link_top(
    input wire sys_clk, reset_n, arm_sw, bus_clk, dir,
    input wire [3:0] aux,
    inout wire [7:0] data,
    output wire ready,
    output wire [3:0] led
);
    // Configuration initializes POR even when KEY0 is never pressed.
    reg [7:0] por = 0;
    always @(posedge sys_clk or negedge reset_n)
        if (!reset_n) por <= 0;
        else por <= {por[6:0], 1'b1};
    wire run_n = por[7] && reset_n;
    reg [1:0] arm_sync;
    reg saw_disarmed;
    reg [24:0] heartbeat;
    always @(posedge sys_clk or negedge run_n) begin
        if (!run_n) begin
            arm_sync <= 0;
            saw_disarmed <= 0;
            heartbeat <= 0;
        end else begin
            arm_sync <= {arm_sync[0], arm_sw};
            // Allow synchronization to settle before recognizing OFF.
            if (&por && !arm_sync[1] && !arm_sw) saw_disarmed <= 1;
            heartbeat <= heartbeat + 1'b1;
        end
    end
    wire armed = run_n && arm_sw && arm_sync[1] && saw_disarmed;
    wire [7:0] data_o;
    wire data_oe;
    assign data = data_oe ? data_o : 8'bz;
    link_bringup core(
        .sys_clk(sys_clk), .reset_n(run_n), .arm(armed),
        .bus_clk(bus_clk), .dir(dir), .data_i(data),
        .data_o(data_o), .data_oe(data_oe), .ready(ready)
    );
    // Active-low Dock LEDs: heartbeat, armed, response ready, bus driving.
    assign led = ~{data_oe, ready, armed, heartbeat[24]};
endmodule
