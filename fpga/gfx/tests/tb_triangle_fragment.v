`timescale 1ns/1ps
module tb_triangle_fragment;
    localparam COUNT=436;
    reg clk=0,reset_n=0,in_valid=0,out_ready=0;
    reg [831:0] sample=0;
    reg [831:0] inputs[0:COUNT-1];
    reg [511:0] expected[0:COUNT-1];
    reg [511:0] held;
    wire in_ready,out_valid,covered,degenerate,invalid_input,depth_pass,write_enable;
    wire [15:0] new_depth,out_color;
    wire [9:0] out_x;
    wire [8:0] out_y;
    wire [511:0] actual={{63'b0,covered},{63'b0,degenerate},{63'b0,invalid_input},
        {63'b0,depth_pass},{48'b0,new_depth},{54'b0,out_x},{55'b0,out_y},{48'b0,out_color}};
    integer n,k,cycles;
    always #5 clk=~clk;
    triangle_fragment dut(.clk(clk),.reset_n(reset_n),.in_valid(in_valid),.in_ready(in_ready),
        .ax(sample[783:768]),.ay(sample[719:704]),.bx(sample[655:640]),
        .by(sample[591:576]),.cx(sample[527:512]),.cy(sample[463:448]),
        .za(sample[399:384]),.zb(sample[335:320]),.zc(sample[271:256]),.old_depth(sample[207:192]),
        .pixel_x(sample[137:128]),.pixel_y(sample[72:64]),.color(sample[15:0]),
        .out_valid(out_valid),.out_ready(out_ready),.covered(covered),.degenerate(degenerate),
        .invalid_input(invalid_input),.depth_pass(depth_pass),.write_enable(write_enable),
        .new_depth(new_depth),.out_color(out_color),.out_x(out_x),.out_y(out_y));
    initial begin
        $readmemh("gfx/tests/fragment_inputs.mem",inputs);
        $readmemh("gfx/tests/fragment_expected.mem",expected);
        #1;reset_n=1;#1;reset_n=0;#1;
        if(in_ready!==0 || out_valid!==0 || write_enable!==0 || actual!==0) $fatal(1,"async reset");
        #9;reset_n=1;
        for(n=0;n<COUNT;n=n+1) begin
            @(negedge clk);if(!in_ready) $fatal(1,"not ready %0d",n);
            sample=inputs[n];in_valid=1;out_ready=0;
            @(posedge clk);#1;cycles=0;
            while(!out_valid) begin
                @(negedge clk);sample=~sample;in_valid=1;
                if(in_ready || write_enable) $fatal(1,"accepted or wrote while busy");
                @(posedge clk);#1;cycles=cycles+1;
                if(cycles>56) $fatal(1,"latency timeout");
            end
            if(actual!==expected[n]) $fatal(1,"vector mismatch %0d actual %0128x expected %0128x",n,actual,expected[n]);
            held=actual;
            for(k=0;k<3;k=k+1) begin
                @(negedge clk);sample=~sample;in_valid=1;
                @(posedge clk);#1;
                if(!out_valid || in_ready || actual!==held || write_enable) $fatal(1,"output stall changed");
            end
            @(negedge clk);out_ready=1;in_valid=0;#1;
            if(write_enable!==(covered && !degenerate && !invalid_input && depth_pass)) $fatal(1,"write gate");
            @(posedge clk);#1;if(out_valid || !in_ready || write_enable) $fatal(1,"consume");
        end
        // Abort during coverage and during the divider; neither may leak a result.
        for(k=0;k<2;k=k+1) begin
            @(negedge clk);sample=inputs[15];in_valid=1;out_ready=0;
            @(posedge clk);#1;in_valid=0;
            if(k==1) repeat(10) begin @(posedge clk);#1;end
            #1;reset_n=0;#1;if(out_valid || in_ready || write_enable || actual!==0) $fatal(1,"inflight reset");
            #1;reset_n=1;
            repeat(60) begin @(posedge clk);#1;if(out_valid || write_enable) $fatal(1,"reset stale result");end
        end
        $display("PASS triangle_fragment %0d candidates, metadata, stalls, reset",COUNT);$finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
