`timescale 1ps/1ps
// Track J: reply-clock edge counters (opcodes logical 0x4c read, 0x4d clear; sent tagged as 0xcc/0xcd so the reply is a fast prefixed one).
module tb_edge_monitor;
    parameter EDGE=1;
    reg filter_clk=0;always #2315 filter_clk=~filter_clk;
    reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
    reg [7:0] host_data=0,q[0:7],r[0:2065];
    wire [7:0] data_i=host_data,data_o;wire ready,oe;
    integer i,waits,seqno=0,packets=0;reg [15:0] crc;
    always #9259 clk=~clk;
    link_bringup_filtered #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(5000),.CORE_CLOCK_MHZ(54),
        .CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1),.EDGE_MONITOR_ENABLE(EDGE)) dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready,filter_clk,reset_n && arm);
    always @(posedge clk) if(host_oe && oe)$fatal(1,"contention");
    function [15:0] crc_byte(input [15:0] c,input [7:0] b);
        reg [15:0] v;integer k;
        begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    task make(input [7:0] op,input [7:0] a,input [7:0] b);
        begin seqno=seqno+1;q[0]=8'ha5;q[1]=op;q[2]=seqno;q[3]=2;q[4]=a;q[5]=b;
            crc=16'hffff;for(i=0;i<6;i=i+1)crc=crc_byte(crc,q[i]);q[6]=crc[7:0];q[7]=crc[15:8];end
    endtask
    task send;
        begin dir=0;bus_clk=0;#200000;host_oe=1;
            for(i=0;i<8;i=i+1)begin host_data=q[i];#500000;bus_clk=1;#500000;bus_clk=0;#500000;end
            host_oe=0;waits=0;while(!ready && waits<200000)begin #1000;waits=waits+1;end
            if(!ready)$fatal(1,"READY timeout op=%h",q[1]);
            bus_clk=1;#200000;bus_clk=0;dir=1;#2000000;
        end
    endtask
    task read_count(input integer count,input integer half_ps);
        begin for(i=0;i<count;i=i+1)begin
            if(!ready || !oe)$fatal(1,"early release op=%h byte=%0d",q[1],i);
            r[i]=data_o;bus_clk=1;#(half_ps);bus_clk=0;#(half_ps);
        end end
    endtask
    task complete(input integer count);
        integer j;reg [15:0] v;
        begin
            #1;if(ready || oe)$fatal(1,"last byte did not release immediately");
            for(j=0;j<8;j=j+1)if(r[j]!=8'hc3)$fatal(1,"prefix changed");
            v=16'hffff;for(j=8;j<14;j=j+1)v=crc_byte(v,r[j]);
            if(r[8]!=8'h5a || r[10]!=q[2] || r[11]!=2 || r[14]!=v[7:0] || r[15]!=v[15:8])$fatal(1,"bad header/seq/CRC");
            dir=0;#200000;
            if(dut.valid || dut.fast_offer)$fatal(1,"SYS acknowledgement stuck");
            packets=packets+1;
        end
    endtask
    task info;
        begin make(8'hb0,0,0);send();read_count(16,12500);complete(16);if(r[9]!=0)$fatal(1,"info status");end
    endtask
    task clear;
        begin make(8'hab,8'haa,8'h55);send();read_count(16,12500);complete(16);if(r[9]!=0)$fatal(1,"clear failed");end
    endtask
    task tile(input integer plane);
        begin make(8'hbb,0,plane);send();read_count(2066,12500);complete(2066);if(r[9]!=0)$fatal(1,"tile status");end
    endtask
    // Read one edge-monitor register through opcode 0x4c. The value describes the
    // reply window that closed BEFORE this query; the query's own 16-edge reply is
    // a new window. So "window of interest, then one query" reads that window.
    reg [15:0] ev;reg [7:0] st;
    task edge_get(input [7:0] idx);
        begin make(8'hcc,idx,0);send();read_count(16,12500);complete(16);st=r[9];ev={r[13],r[12]};end
    endtask
    task edge_clear;
        begin make(8'hcd,8'h5a,8'ha5);send();read_count(16,12500);complete(16);st=r[9];end
    endtask
    task settle; begin #2000000; end endtask
    integer pre,post,rej,exp_n,flags,windows,bad;
    initial begin
        #100000;reset_n=1;arm=1;#200000;
        if(EDGE==0)begin
            make(8'hcc,0,0);send();read_count(16,12500);complete(16);
            if(r[9]!=2)$fatal(1,"EDGE=0 opcode 0x4c status %0d",r[9]);
            make(8'hcd,8'h5a,8'ha5);send();read_count(16,12500);complete(16);
            if(r[9]!=2)$fatal(1,"EDGE=0 opcode 0x4d status %0d",r[9]);
            info();clear();tile(0);tile(1);
            $display("PASS EDGE=0 opcodes 0x4c/0x4d unsupported, normal traffic unchanged");$finish;
        end
        // Argument checking.
        make(8'hcc,21,0);send();read_count(16,12500);complete(16);if(r[9]!=3)$fatal(1,"index range");
        make(8'hcc,0,1);send();read_count(16,12500);complete(16);if(r[9]!=3)$fatal(1,"reserved byte");
        make(8'hcd,8'h5a,8'ha4);send();read_count(16,12500);complete(16);if(r[9]!=3)$fatal(1,"clear key");
        clear();
        // Clean 16-edge window; each successive query reports the previous 16-edge query.
        info();settle();
        edge_get(0);if(st!=0||ev!==16'hed01)$fatal(1,"edge id %h st=%0d",ev,st);
        edge_get(14);flags=ev;
        $display("after queries: flags=%h",flags);
        if(!flags[7])$fatal(1,"no valid snapshot");
        edge_get(12);exp_n=ev;if(exp_n!=16)$fatal(1,"expect=%0d",exp_n);
        edge_get(4);pre=ev;edge_get(5);post=ev;edge_get(6);rej=ev;
        $display("16-edge window: pre=%0d post=%0d rej=%0d",pre,post,rej);
        if(pre+post!=16)$fatal(1,"accepted rises %0d != 16",pre+post);
        if(rej!=0)$fatal(1,"clean window reject");
        edge_get(7);if(ev!=0)$fatal(1,"drop");edge_get(8);if(ev!=0)$fatal(1,"runt");
        edge_get(14);flags=ev;
        if(flags[2]||flags[1]||!flags[0]||flags[4]||flags[3])$fatal(1,"clean flags=%h",flags);
        // Counters reset by 0x4d.
        edge_get(1);windows=ev;if(windows==0)$fatal(1,"no windows counted");
        edge_clear();edge_get(1);windows=ev;
        if(windows>3)$fatal(1,"clear did not reset windows (%0d)",windows);
        // Full tile window of 2066 edges: tile then exactly one query per register.
        tile(0);settle();edge_get(12);
        if(ev!=2066)$fatal(1,"tile expect=%0d",ev);
        tile(0);settle();edge_get(4);pre=ev;
        tile(0);settle();edge_get(5);post=ev;
        tile(0);settle();edge_get(6);rej=ev;
        tile(0);settle();edge_get(13);
        $display("tile window: pre=%0d post=%0d rej=%0d done_index=%0d",pre,post,rej,ev);
        if(rej!=0||ev==0||ev>2065)$fatal(1,"tile done_index/rej");
        if(pre<2060||pre>2066||post>6)$fatal(1,"tile pre/post");
        // Clean traffic must show no excess windows. (idx 20 counts aborts/short windows; checked after the abort test.)
        edge_get(19);if(ev!=0)$fatal(1,"excess windows on a clean link: %0d",ev);
        // Injected qualified short-spacing edge: reject/fault must be visible.
        edge_clear();
        make(8'h81,0,0);send();@(negedge filter_clk);
        bus_clk=1;#9260;bus_clk=0;#9260;bus_clk=1;#9260;bus_clk=0;#50000;
        if(!dut.clock_filter_fault)$fatal(1,"fault not raised");
        dir=0;#2000000;
        edge_get(2);bad=ev;
        $display("noise: bad_windows=%0d",bad);
        if(bad==0)$fatal(1,"noise window not flagged bad");
        edge_get(15);$display("worst_rej=%0d",ev);
        if(ev==0)$fatal(1,"worst rej not recorded");
        // A 1ns excursion never becomes a rise.
        make(8'h81,0,0);send();bus_clk=1;#1000;bus_clk=0;#50000;
        read_count(16,12500);complete(16);settle();
        edge_get(4);pre=ev;
        if(pre!=16)$fatal(1,"glitch window pre=%0d",pre);
        // Datapath unchanged by the monitor.
        repeat(4)begin tile(0);info();tile(1);end
        // Abort path (DIR drops mid-frame) closes the window without done.
        make(8'hbb,0,0);send();read_count(17,12500);dir=0;#2000000;
        edge_get(14);flags=ev;
        $display("abort: flags=%h",flags);
        if(flags[0])$fatal(1,"abort window must not report done flags=%h",flags);
        edge_get(20);if(ev==0)$fatal(1,"deficit windows not counted after abort");
        $display("PASS EDGE=1 edge counters: clean 16/2066-edge replies counted, noise/reject/fault visible, clear/args/abort ok packets=%0d",packets);$finish;
    end
    initial begin #10000000000;$fatal(1,"watchdog");end
endmodule
