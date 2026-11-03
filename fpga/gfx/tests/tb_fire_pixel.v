`timescale 1ns/1ps
// Compares fire_pixel against vectors generated from fpga/reference/fire_g0.py.
// +VEC=<file>: one 64-bit hex per line {9'b0,x[9:0],y[9:0],frame[15:0],oct[2:0],expected[15:0]}.
module tb_fire_pixel;
    reg clk=0,reset_n=0,abort=0,start=0;
    reg [9:0] x=0,y=0;
    reg [15:0] frame=0;
    reg [2:0] octaves=1;
    wire busy,done;
    wire [15:0] color;
    reg [63:0] vec[0:4095];
    reg [255*8:1] path;
    integer n,count,cycles,errors,checked;
    reg [15:0] expected;
    always #5 clk=~clk;
    fire_pixel dut(.clk(clk),.reset_n(reset_n),.abort(abort),.start(start),.x(x),.y(y),.frame(frame),
                   .octaves(octaves),.busy(busy),.done(done),.color(color));
    initial begin
        if(!$value$plusargs("VEC=%s",path)) $fatal(1,"missing +VEC");
        if(!$value$plusargs("COUNT=%d",count)) $fatal(1,"missing +COUNT");
        $readmemh(path,vec);
        errors=0;checked=0;
        #12;reset_n=1;
        for(n=0;n<count;n=n+1) begin
            @(negedge clk);
            x=vec[n][54:45];y=vec[n][44:35];frame=vec[n][34:19];octaves=vec[n][18:16];expected=vec[n][15:0];
            start=1;
            @(negedge clk);start=0;
            cycles=1;
            while(!done) begin
                if(cycles>1000) $fatal(1,"timeout vec %0d",n);
                @(negedge clk);cycles=cycles+1;
            end
            checked=checked+1;
            if(color!==expected) begin
                errors=errors+1;
                if(errors<=10) $display("MISMATCH vec=%0d x=%0d y=%0d frame=%0d oct=%0d got=%h exp=%h",n,x,y,frame,octaves,color,expected);
            end
            if(cycles!==8+14*octaves) begin
                errors=errors+1;
                if(errors<=10) $display("LATENCY vec=%0d oct=%0d cycles=%0d expected=%0d",n,octaves,cycles,8+14*octaves);
            end
            if(busy) $fatal(1,"busy stuck");
        end
        if(errors) $fatal(1,"fire_pixel FAIL errors=%0d checked=%0d",errors,checked);
        $display("PASS fire_pixel vectors=%0d",checked);
        $finish;
    end
endmodule
