`timescale 1ns/1ps
module tb_dock_link_top;
    reg clk=0, reset_n=1, arm=1, bus_clk=0, dir=1;
    wire [7:0] data;
    wire ready;
    wire [3:0] led;
    always #18.519 clk=~clk;
    dock_link_top dut(clk,reset_n,arm,bus_clk,dir,4'b0,data,ready,led);
    task cycles(input integer n);
        repeat(n) @(negedge clk);
    endtask
    initial begin
        cycles(30);
        if (dut.armed !== 0 || ready !== 0 || data !== 8'bz)
            $fatal(1,"SW ON at configuration must not arm");
        arm=0; cycles(5); arm=1; cycles(5);
        if (dut.armed !== 1) $fatal(1,"OFF then ON must arm");
        arm=0; #1;
        if (dut.armed !== 0 || data !== 8'bz)
            $fatal(1,"OFF must immediately disarm");
        cycles(4); arm=1; cycles(5);
        reset_n=0; #1;
        if (dut.armed !== 0 || ready !== 0 || data !== 8'bz)
            $fatal(1,"reset must disable bus immediately");
        cycles(3); reset_n=1; cycles(30);
        if (dut.armed !== 0) $fatal(1,"reset requires a fresh OFF/ON");
        $display("PASS Dock power-on/reset/ARM safety");
        $finish;
    end
endmodule
