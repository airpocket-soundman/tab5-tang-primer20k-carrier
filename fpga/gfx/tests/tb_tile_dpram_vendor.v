`timescale 1ps/1ps
module tb_tile_dpram_vendor;
    GSR GSR(1'b1);
    reg clk_a=0,clk_b=0,write_a=0,read_b=0;
    reg [9:0]a=0,b=0;reg [15:0]d=0;
    wire [15:0]qa,qb;
    integer i,checks=0;reg [15:0]held;
    tile_dpram_vendor dut(clk_a,write_a,a,d,qa,clk_b,read_b,b,qb);
    function [15:0]pattern(input integer address);
        reg [15:0]v;begin v=address+1;v=v^(v<<7);v=v^(v>>9);v=v^(v<<8);pattern=v^16'h5a3c;end
    endfunction
    task tick_a;begin #5000;clk_a=1;#5000;clk_a=0;end endtask
    initial begin
        #100000;
        for(i=0;i<1024;i=i+1)begin a=i;d=pattern(i);write_a=1;tick_a();end
        write_a=0;
        for(i=0;i<1024;i=i+1)begin
            a=i;tick_a();if(qa!==pattern(i))$fatal(1,"A registered read mismatch%0d",i);checks=checks+1;
        end
        held=qa;write_a=1;a=1023;d=pattern(1023);tick_a();
        if(qa!==held)$fatal(1,"normal-mode write must hold A output");checks=checks+1;write_a=0;
        read_b=1;
        for(i=0;i<1024;i=i+1)begin
            b=i;#8000;clk_b=1;#1;
            if(qb!==pattern(i))$fatal(1,"B one-clock latency/data mismatch%0d got%h expected%h",i,qb,pattern(i));
            checks=checks+1;#7999;clk_b=0;
        end
        held=qb;read_b=0;b=0;#8000;clk_b=1;#1;
        if(qb!==held)$fatal(1,"disabled B output changed");checks=checks+1;
        $display("PASS vendorDPB native checks=%0d",checks);$finish;
    end
endmodule
