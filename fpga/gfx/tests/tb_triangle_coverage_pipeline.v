`timescale 1ns/1ps
module tb_triangle_coverage_pipeline;
    localparam COUNT=3328;
    reg clk=0,reset_n=0,in_valid=0;
    reg [127:0]sample=0,inputs[0:COUNT-1];
    reg [319:0]expected[0:COUNT-1],queue[0:3],previous=0;
    reg [3:0]valid_queue=0;
    wire out_valid,covered,degenerate,winding_swapped;
    wire signed [63:0]area,weight_a,weight_b,weight_c;
    wire [319:0]actual={61'b0,winding_swapped,degenerate,covered,area,weight_a,weight_b,weight_c};
    integer n,k,checked=0;
    always #5 clk=~clk;
    triangle_coverage dut(clk,reset_n,in_valid,sample[127:112],sample[111:96],sample[95:80],sample[79:64],sample[63:48],sample[47:32],sample[25:16],sample[8:0],out_valid,covered,degenerate,winding_swapped,area,weight_a,weight_b,weight_c);
    task drive(input integer index,input valid);
        begin
            @(negedge clk);in_valid=valid;sample=valid?inputs[index]:~sample;
            @(posedge clk);#1;
            for(k=3;k>0;k=k-1)queue[k]=queue[k-1];queue[0]=valid?expected[index]:0;
            valid_queue={valid_queue[2:0],valid};
            if(out_valid!==valid_queue[3])$fatal(1,"pipeline valid mismatch");
            if(valid_queue[3])begin
                if(actual!==queue[3])$fatal(1,"pipeline vector actual%080x expected%080x",actual,queue[3]);
                checked=checked+1;previous=actual;
            end else if(actual!==previous)$fatal(1,"invalid pipeline output changed");
        end
    endtask
    initial begin
        $readmemh("gfx/tests/inputs.mem",inputs);$readmemh("gfx/tests/expected.mem",expected);
        #1;reset_n=1;#1;reset_n=0;#1;if(actual!==0||out_valid!==0)$fatal(1,"reset");#9;reset_n=1;
        for(n=0;n<COUNT;n=n+1)begin drive(n,1);if(n%31==0)drive(0,0);end
        repeat(4)drive(0,0);
        if(checked!=COUNT)$fatal(1,"lost vectors");
        @(negedge clk);in_valid=1;sample=inputs[0];@(posedge clk);#1;reset_n=0;valid_queue=0;previous=0;#1;
        if(actual!==0||out_valid!==0)$fatal(1,"inflight reset");reset_n=1;repeat(4)drive(0,0);
        $display("PASS coverage pipeline %0d oraclevectors backtoback/bubbles/reset",checked);$finish;
    end
endmodule
