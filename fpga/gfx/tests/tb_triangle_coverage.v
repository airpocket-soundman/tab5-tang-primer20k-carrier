`timescale 1ns/1ps
module tb_triangle_coverage;
    localparam COUNT=3328;
    reg clk=0, reset_n=0, in_valid=0;
    reg [127:0] sample=0;
    wire out_valid,covered,degenerate,winding_swapped;
    wire signed [63:0] area,weight_a,weight_b,weight_c;
    wire [319:0] actual={61'b0,winding_swapped,degenerate,covered,area,weight_a,weight_b,weight_c};
    reg [127:0] inputs[0:COUNT-1];
    reg [319:0] expected[0:COUNT-1];
    reg [319:0] previous;
    integer n;
    always #5 clk=~clk;
    triangle_coverage dut(.clk(clk),.reset_n(reset_n),.in_valid(in_valid),
        .ax(sample[127:112]),.ay(sample[111:96]),.bx(sample[95:80]),.by(sample[79:64]),
        .cx(sample[63:48]),.cy(sample[47:32]),.pixel_x(sample[25:16]),.pixel_y(sample[8:0]),
        .out_valid(out_valid),.covered(covered),.degenerate(degenerate),.winding_swapped(winding_swapped),
        .area(area),.weight_a(weight_a),.weight_b(weight_b),.weight_c(weight_c));
    initial begin
        $readmemh("gfx/tests/inputs.mem",inputs);
        $readmemh("gfx/tests/expected.mem",expected);
        #1; reset_n=1; #1; reset_n=0; #1; if(out_valid!==0 || actual!==0) $fatal(1,"initial reset");
        #9; reset_n=1;
        for(n=0;n<COUNT;n=n+1) begin
            @(negedge clk); sample=inputs[n]; in_valid=1;
            @(posedge clk); #1;
            if(out_valid!==1 || actual!==expected[n])
                $fatal(1,"vector %0d actual=%080x expected=%080x valid=%b",n,actual,expected[n],out_valid);
            if(n%31==0) begin
                previous=actual;
                @(negedge clk); in_valid=0; sample=~sample;
                @(posedge clk); #1;
                if(out_valid!==0 || actual!==previous) $fatal(1,"invalid bubble %0d",n);
            end
            if(n==1664) begin
                #1; reset_n=0; #1;
                if(out_valid!==0 || actual!==0) $fatal(1,"midstream reset");
                #1; reset_n=1;
            end
        end
        $display("PASS triangle_coverage: %0d vectors, back-to-back, bubbles, reset",COUNT);
        $finish;
    end
    initial begin #1000000; $fatal(1,"watchdog"); end
endmodule
