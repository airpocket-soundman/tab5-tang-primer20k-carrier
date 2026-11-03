`timescale 1ns/1ps
module tb_triangle_bbox #(parameter FAST_REPLY_ENABLE=0);
    reg clk=0, reset_n=0, arm=0, bus_clk=0, dir=0, host_oe=0;
    reg [7:0] host_data=0;
    tri [7:0] data;
    wire ready;wire [3:0] led;
    reg variant_arm=0;
    wire link_ready,gfx_ready,link_oe,gfx_oe;
    wire [7:0] link_data,gfx_data;
    reg [7:0] q[0:7],expected[0:73],got[0:73];
    reg [1023:0] path;
    integer fd,n,i,count,length,cycles,max_candidates,triangle_candidates;
    always @(posedge clk) if(dut.core.triangle.renderer.state==5 && dut.core.triangle.renderer.fragment_ready) triangle_candidates=triangle_candidates+1;
    always #5 clk=~clk;
    assign data=host_oe?host_data:8'hzz;
    tab5_dock_top #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(200000),.FAST_REPLY_ENABLE(FAST_REPLY_ENABLE)) dut(
        clk,reset_n,arm,bus_clk,dir,4'b0,data,ready,led);
    link_bringup #(.GFX_ENABLE(0),.TIMEOUT_CYCLES(200000)) link_only(
        clk,reset_n,variant_arm,bus_clk,dir,host_data,link_data,link_oe,link_ready);
    link_bringup #(.GFX_ENABLE(1),.TIMEOUT_CYCLES(200000)) gfx_only(
        clk,reset_n,variant_arm,bus_clk,dir,host_data,gfx_data,gfx_oe,gfx_ready);
    always @(posedge clk) if(host_oe && dut.data_oe) $fatal(1,"contention");
    function [15:0] crc_byte(input [15:0] c,input [7:0] b);
        reg [15:0] v;integer j;
        begin v=c^{b,8'b0};for(j=0;j<8;j=j+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    task make(input [7:0] op,input [7:0] a,input [7:0] b);
        reg [15:0] crc;integer j;
        begin
            q[0]=8'ha5;q[1]=op;q[2]=8'h5a;q[3]=2;q[4]=a;q[5]=b;
            crc=16'hffff;for(j=0;j<6;j=j+1)crc=crc_byte(crc,q[j]);q[6]=crc[7:0];q[7]=crc[15:8];
        end
    endtask
    task pulse;begin #60;bus_clk=1;#60;bus_clk=0;#60;end endtask
    task send;
        integer j;
        begin triangle_candidates=0;dir=0;#100;host_oe=1;
            for(j=0;j<8;j=j+1)begin host_data=q[j];pulse();end
            host_oe=0;
        end
    endtask
    task begin_read;
        begin
            cycles=0;while(!ready && cycles<150000)begin #10;cycles=cycles+1;end
            if(!ready)$fatal(1,"response timeout op=%h vector=%0d",q[1],count);
            dir=1;#100;
        end
    endtask
    task read_bytes(input integer bytes);
        integer j;
        begin
            begin_read();
            for(j=0;j<bytes;j=j+1)begin
                if(!ready || !dut.data_oe)$fatal(1,"early release vector=%0d byte=%0d",count,j);
                got[j]=data;pulse();
            end
        end
    endtask
    task finish_read;
        begin
            if(ready || dut.data_oe || data!==8'hzz)$fatal(1,"final byte did not release bus");
            dir=0;#100;
        end
    endtask
    initial begin
        #100;reset_n=1;#100;arm=1;#100;
        if(!$value$plusargs("vectors=%s",path))$fatal(1,"missing vectors");
        fd=$fopen(path,"r");if(!fd)$fatal(1,"cannot open vectors");count=0;
        while(!$feof(fd))begin
            n=$fscanf(fd,"%d",length);
            if(n==1)begin
                if(length!=8 && length!=74)$fatal(1,"bad response length");
                n=$fscanf(fd,"%d",max_candidates);if(n!=1)$fatal(1,"missing candidate limit");
                for(i=0;i<8;i=i+1)begin n=$fscanf(fd,"%h",q[i]);if(n!=1)$fatal(1,"bad request");end
                for(i=0;i<length;i=i+1)begin n=$fscanf(fd,"%h",expected[i]);if(n!=1)$fatal(1,"bad response");end
                send();read_bytes(length);finish_read();
                for(i=0;i<length;i=i+1)if(got[i]!==expected[i])
                    $fatal(1,"vector=%0d op=%h byte=%0d got=%h expected=%h",count,q[1],i,got[i],expected[i]);
                if(q[1]==8'h2c && got[1]==0 && triangle_candidates>max_candidates)
                    $fatal(1,"bbox candidate excess vector=%0d got=%0d maximum=%0d",count,triangle_candidates,max_candidates);
                count=count+1;
            end else if(n!=-1 && !$feof(fd))$fatal(1,"invalid vector token");
        end
        $fclose(fd);
        // Snapshot construction is an operation: timeout aborts it and invalidates tile.
        make(8'h2f,0,0);send();wait(dut.core.gfx_pending);#50;
        force dut.core.idle_count=199999;#20;release dut.core.idle_count;#100;
        if(ready || dut.core.gfx_pending)$fatal(1,"snapshot timeout did not abort");
        make(8'h2f,0,0);send();read_bytes(8);finish_read();
        if(got[1]!=5)$fatal(1,"snapshot abort must invalidate tile");
        make(8'h2b,0,0);send();read_bytes(8);finish_read();
        // A truncated row stays pending until timeout, then permits a fresh request.
        make(8'h2f,0,0);send();read_bytes(30);
        if(!ready)$fatal(1,"truncated reply released early");
        #2001000;if(ready || dut.data_oe || data!==8'hzz)$fatal(1,"truncated row timeout failed");
        dir=0;#100;make(8'h20,0,0);send();read_bytes(8);finish_read();
        if(got[1]!=0)$fatal(1,"timeout recovery failed");
        // Read rows are not RAM mutations; timeout may invalidate implementation state.
        make(8'h2b,0,0);send();read_bytes(8);finish_read();
        make(8'h2f,31,1);send();read_bytes(73);
        if(!ready || !dut.data_oe)$fatal(1,"READY must remain high before byte74");
        arm=0;#1;if(ready || data!==8'hzz)$fatal(1,"disarm during row failed");
        #100;dir=0;arm=1;#100;
        make(8'h2f,0,0);send();read_bytes(8);finish_read();
        if(got[1]!=5)$fatal(1,"disarm must invalidate tile");
        make(8'h2b,0,0);send();read_bytes(8);finish_read();
        make(8'h2f,0,0);send();read_bytes(20);
        reset_n=0;#1;if(ready || data!==8'hzz)$fatal(1,"reset during row failed");
        #100;dir=0;arm=0;reset_n=1;variant_arm=1;#100;
        // The opcode is isolated to the triangle image; existing images reject it.
        make(8'h2f,0,0);send();
        cycles=0;while((!link_ready || !gfx_ready) && cycles<1000)begin #10;cycles=cycles+1;end
        if(!link_ready || !gfx_ready)$fatal(1,"legacy variant did not respond");
        dir=1;#100;
        for(i=0;i<8;i=i+1)begin
            if(!link_ready || !gfx_ready || !link_oe || !gfx_oe)$fatal(1,"legacy early release");
            if(i==1 && (link_data!==8'h02 || gfx_data!==8'h02))$fatal(1,"legacy accepted TRI_ROW");
            pulse();
        end
        if(link_ready || gfx_ready || link_oe || gfx_oe)$fatal(1,"legacy reply not eight bytes");
        $display("PASS triangle bbox pin-level vectors=%0d, final-byte/timeout/disarm/reset",count);$finish;
    end
    initial begin #1000000000;$fatal(1,"watchdog");end
endmodule
