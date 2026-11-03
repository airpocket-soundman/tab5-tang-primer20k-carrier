`timescale 1ns/1ps
module tb_triangle_tile_dock;
    reg sys_clk=0, reset_n=0, arm=0, bus_clk=0, dir=0, host_oe=0;
    reg [7:0] host_data=0;
    tri [7:0] data;
    wire ready; wire [3:0] led;
    reg [7:0] q[0:7], expected[0:7], got[0:7];
    reg [1023:0] vector_path;
    integer fd, n, i, count;
    always #5 sys_clk=~sys_clk;
    assign data=host_oe ? host_data : 8'hzz;
    tab5_dock_top #(.GFX_ENABLE(2), .TIMEOUT_CYCLES(200000)) dut(
        sys_clk,reset_n,arm,bus_clk,dir,4'b0,data,ready,led);
    always @(posedge sys_clk) if(host_oe && dut.data_oe) $fatal(1,"host/FPGA contention");
    function [15:0] crc_byte(input [15:0] c, input [7:0] b);
        reg [15:0] v; integer k;
        begin v=c^{b,8'b0}; for(k=0;k<8;k=k+1) v=v[15]?(v<<1)^16'h1021:v<<1; crc_byte=v; end
    endfunction
    task make_request(input [7:0] op, input [7:0] a, input [7:0] b);
        reg [15:0] c; integer k;
        begin
            q[0]=8'ha5; q[1]=op; q[2]=8'h9b; q[3]=2; q[4]=a; q[5]=b;
            c=16'hffff; for(k=0;k<6;k=k+1) c=crc_byte(c,q[k]);
            q[6]=c[7:0]; q[7]=c[15:8];
        end
    endtask
    task pulse; begin #60; bus_clk=1; #60; bus_clk=0; #60; end endtask
    task send;
        integer k;
        begin
            dir=0; #100; host_oe=1;
            for(k=0;k<8;k=k+1) begin host_data=q[k]; pulse(); end
            host_oe=0;
        end
    endtask
    task receive;
        integer k, wait_cycles;
        begin
            wait_cycles=0;
            while(!ready && wait_cycles<150000) begin #10; wait_cycles=wait_cycles+1; end
            if(!ready) $fatal(1,"response timeout op=%h vector=%0d",q[1],count);
            dir=1; #100;
            if(!dut.data_oe) $fatal(1,"missing output enable");
            for(k=0;k<8;k=k+1) begin got[k]=data; pulse(); end
            dir=0; #100;
            if(ready || dut.data_oe || data !== 8'hzz) $fatal(1,"bus not released");
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
            end else if(n!=-1) $fatal(1,"invalid vector %0d",n);
        end
        $fclose(fd);
        // Abort an actual in-flight fragment, not only a bulk clear.
        make_request(8'h2c,0,0); send();
        wait(dut.core.triangle.renderer.state==6); #100;
        force dut.core.idle_count=199999; #20; release dut.core.idle_count; #100;
        if(dut.core.gfx_pending || dut.core.triangle.renderer.state != 0 || ready)
            $fatal(1,"timeout did not abort fragment");
        make_request(8'h2e,0,0); send(); receive();
        if(got[1] != 5) $fatal(1,"aborted draw must invalidate depth");
        // Force timeout while a clear is writing; it invalidates all RAM state.
        make_request(8'h2b,0,0); send();
        wait(dut.core.gfx_pending); #100;
        force dut.core.idle_count=199999; #20; release dut.core.idle_count; #100;
        if(dut.core.gfx_pending || dut.core.triangle.renderer.state != 0 || ready)
            $fatal(1,"timeout did not abort triangle renderer");
        make_request(8'h20,0,0); send(); receive();
        if(got[1] != 0 || got[4] != 8'h20 || got[5] != 8'h20)
            $fatal(1,"command after timeout failed");
        make_request(8'h2d,0,0); send(); receive();
        if(got[1] != 5) $fatal(1,"aborted clear must invalidate tile");
        make_request(8'h2b,0,0); send(); wait(dut.core.gfx_pending); #100;
        arm=0; #1; if(ready || data !== 8'hzz) $fatal(1,"disarm during clear");
        #100; arm=1; #100; make_request(8'h2d,0,0); send(); receive();
        if(got[1] != 5) $fatal(1,"disarmed clear must invalidate tile");
        // Timeout of a pending response must release the physical bus.
        send(); while(!ready) #10; dir=1; #100; #2001000;
        if(ready || dut.data_oe || data !== 8'hzz) $fatal(1,"timeout failed to release bus");
        dir=0; #100; send(); receive();
        // Disarm/reset must remove the physical drive immediately.
        send(); while(!ready) #10; dir=1; #100; arm=0; #1;
        if(ready || data !== 8'hzz) $fatal(1,"disarm failed immediate release");
        #100; dir=0; arm=1; #100; send(); while(!ready) #10; dir=1; #100;
        reset_n=0; #1; if(ready || data !== 8'hzz) $fatal(1,"reset failed immediate release");
        $display("PASS triangle tile pin-level oracle vectors=%0d, timeout/disarm/reset",count); $finish;
    end
    initial begin #1000000000; $fatal(1,"watchdog"); end
endmodule
