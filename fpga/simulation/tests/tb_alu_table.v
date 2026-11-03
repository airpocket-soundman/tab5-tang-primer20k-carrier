`timescale 1ns/1ps
module tb_alu_table;
    reg i0=1, i1=1, i3=1, cin=1;
    wire sum, cout;
    integer i;
    ALU #(.ALU_MODE(2)) dut(.I0(i0),.I1(i1),.I3(i3),.CIN(cin),.SUM(sum),.COUT(cout));
    initial begin
        for(i=0;i<16;i=i+1) begin
            {i0,i1,i3,cin}=i; #1;
            $display("%0d %b%b",i,sum,cout);
        end
        $finish;
    end
endmodule
