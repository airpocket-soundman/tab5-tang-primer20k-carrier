`timescale 1ns/1ps
module tb_synth_bench;
    reg clk=0, reset_n=0, arm=0, bus_clk=0, dir=0, host_oe=0;
    reg [7:0] host_data=0;
    tri [7:0] data;
    wire ready; wire [3:0] led;
    reg [7:0] q[0:7], expected[0:7], got[0:7];
    reg [2047:0] vector_path;
    integer fd, n, i, count, wait_cycles;
    always #5 clk=~clk;
    assign data=host_oe ? host_data : 8'hzz;
    tab5_dock_gfx_top dut(clk,reset_n,arm,bus_clk,dir,4'b0,data,ready,led);
    task pulse; begin #60; bus_clk=1; #60; bus_clk=0; #60; end endtask
    task send;
        integer k;
        begin dir=0; #100; host_oe=1;
            for(k=0;k<8;k=k+1) begin host_data=q[k]; pulse(); end
            host_oe=0;
        end
    endtask
    task receive;
        integer k;
        begin
            wait_cycles=0;
            while(ready !== 1'b1 && wait_cycles<1500) begin #10; wait_cycles=wait_cycles+1; end
            if(ready !== 1'b1) $fatal(1,"response timeout vector=%0d",count);
            dir=1; #100;
            for(k=0;k<8;k=k+1) begin got[k]=data; pulse(); end
            dir=0; #100;
            if(ready !== 1'b0 || data !== 8'hzz) $fatal(1,"bus not released");
        end
    endtask
    initial begin
        #100; reset_n=1; #100; arm=1; #100;
        if(!$value$plusargs("vectors=%s",vector_path)) $fatal(1,"missing vectors");
        fd=$fopen(vector_path,"r"); if(!fd) $fatal(1,"cannot open vectors");
        count=0;
        while(!$feof(fd)) begin
            n=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],
                expected[0],expected[1],expected[2],expected[3],expected[4],expected[5],expected[6],expected[7]);
            if(n==16) begin
                send(); receive();
                for(i=0;i<8;i=i+1) if(got[i] !== expected[i])
                    $fatal(1,"vector=%0d op=%h byte=%0d got=%h expected=%h",count,q[1],i,got[i],expected[i]);
                count=count+1;
            end else if(n!=-1) $fatal(1,"bad vector");
        end
        $fclose(fd);
        send(); while(ready !== 1'b1) #10; dir=1; #100; arm=0; #1;
        if(ready !== 1'b0 || data !== 8'hzz) $fatal(1,"disarm failed release");
        #100; dir=0; arm=1; #100; send(); while(ready !== 1'b1) #10; dir=1; #100; reset_n=0; #1;
        if(ready !== 1'b0 || data !== 8'hzz) $fatal(1,"reset failed release");
        $display("PASS synthesized oracle vectors=%0d",count); $finish;
    end
    initial begin #100000000; $fatal(1,"watchdog"); end
endmodule
