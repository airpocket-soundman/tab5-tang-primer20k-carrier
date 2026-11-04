`timescale 1ps/1ps
// Track J v2: reply-clock edge counters measured inside the data-valid interval.
// Opcodes: logical 0x4c read, 0x4d clear (sent tagged as 0xcc/0xcd so the reply is a fast prefixed one).
// Scenarios (EDGE=1): healthy reply followed by a LONG idle clock tail (the real continuous-RX behaviour),
// an extra close edge (reject), an extra edge the filter still accepts (spacing anomaly), a missing edge.
module tb_edge_monitor;
    parameter EDGE=1;
    reg filter_clk=0;always #2315 filter_clk=~filter_clk;
    reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
    reg [7:0] host_data=0,q[0:7],r[0:2065];
    wire [7:0] data_i=host_data,data_o;wire ready,oe;
    integer i,n,waits,seqno=0,packets=0;reg [15:0] crc;
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
    // Host keeps clocking after the reply is complete (ISR lease / READY-low tail in continuous RX).
    task tail(input integer count,input integer half_ps);
        begin for(n=0;n<count;n=n+1)begin bus_clk=1;#(half_ps);bus_clk=0;#(half_ps);end end
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
    // Read one edge-monitor register through opcode 0x4c. The value describes the reply window that
    // closed BEFORE this query; the query's own 16-edge reply is a new window. Window-specific fields
    // (idx 4..14, 21..30, 32) are therefore only valid for the FIRST query after the window of interest.
    reg [15:0] ev;reg [7:0] st;
    task edge_get(input [7:0] idx);
        begin make(8'hcc,idx,0);send();read_count(16,12500);complete(16);st=r[9];ev={r[13],r[12]};end
    endtask
    task edge_clear;
        begin make(8'hcd,8'h5a,8'ha5);send();read_count(16,12500);complete(16);st=r[9];end
    endtask
    task settle; begin #2000000; end endtask
    integer K,pre,post,flags;
    reg [7:0] kk;
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
`ifndef TB_EDGE0
        // ---- argument checking ----
        make(8'hcc,34,0);send();read_count(16,12500);complete(16);if(r[9]!=3)$fatal(1,"index range");
        make(8'hcc,0,1);send();read_count(16,12500);complete(16);if(r[9]!=3)$fatal(1,"reserved byte");
        make(8'hcd,8'h5a,8'ha4);send();read_count(16,12500);complete(16);if(r[9]!=3)$fatal(1,"clear key");
        edge_get(0);if(st!=0||ev!==16'hed02)$fatal(1,"edge id %h st=%0d",ev,st);
        clear();edge_clear();

        // ---- (a) healthy 16-edge reply, then a 40-edge idle clock tail ----
        make(8'hb0,0,0);send();read_count(16,12500);tail(40,12500);complete(16);settle();
        $display("A16: pre=%0d post=%0d rej=%0d drp=%0d rnt=%0d tail=%0d flags=%h excess=%0d deficit=%0d fpos=%h spj=%0d spmin=%0d spmax=%0d minh=%0d minl=%0d",
            dut.edge_diag.l_pre,dut.edge_diag.l_post,dut.edge_diag.l_rej,dut.edge_diag.l_drp,dut.edge_diag.l_rnt,dut.edge_diag.l_tail,
            dut.edge_diag.l_flags,dut.edge_diag.l_excess,dut.edge_diag.l_deficit,dut.edge_diag.l_fpos,dut.edge_diag.l_spjump,
            dut.edge_diag.l_spmin,dut.edge_diag.l_spmax,dut.edge_diag.l_minh,dut.edge_diag.l_minl);
        if(dut.edge_diag.l_pre!=16 || dut.edge_diag.l_expect!=16)$fatal(1,"A16 valid-interval rises %0d expect %0d",dut.edge_diag.l_pre,dut.edge_diag.l_expect);
        if(dut.edge_diag.l_post<38 || dut.edge_diag.l_post>40)$fatal(1,"A16 tail rises %0d (host sent 40)",dut.edge_diag.l_post);
        if(dut.edge_diag.l_rej!=0||dut.edge_diag.l_drp!=0||dut.edge_diag.l_rnt!=0||dut.edge_diag.l_tail!=0)$fatal(1,"A16 anomaly counters not zero");
        if(dut.edge_diag.l_excess!=0||dut.edge_diag.l_deficit!=0)$fatal(1,"A16 excess/deficit on a healthy window");
        if(!dut.edge_diag.l_flags[7]||!dut.edge_diag.l_flags[6]||!dut.edge_diag.l_flags[0]||dut.edge_diag.l_flags[4:1]!=0)$fatal(1,"A16 flags=%h",dut.edge_diag.l_flags);
        if(dut.edge_diag.l_fpos!=12'hfff||dut.edge_diag.l_spjump!=0)$fatal(1,"A16 spurious anomaly position/jump");
        if(dut.edge_diag.l_didx!=15)$fatal(1,"A16 done_index=%0d",dut.edge_diag.l_didx);
        if(dut.edge_diag.excess_windows!=0||dut.edge_diag.deficit_windows!=0||dut.edge_diag.bad_windows!=0)$fatal(1,"A16 history flagged a healthy window");
        // Same window through the opcode path (first query after the window).
        make(8'hb0,0,0);send();read_count(16,12500);tail(40,12500);complete(16);settle();
        edge_get(21);if(st!=0||ev!=0)$fatal(1,"idx21 last excess %0d",ev);
        edge_get(19);if(ev!=0)$fatal(1,"idx19 excess windows %0d",ev);
        edge_get(2);if(ev!=0)$fatal(1,"idx2 bad windows %0d on a healthy link",ev);

        // ---- (a) healthy 2066-edge tile reply, then a 300-edge idle clock tail ----
        make(8'hbb,0,0);send();read_count(2066,12500);tail(300,12500);complete(2066);settle();
        $display("A2066: pre=%0d post=%0d flags=%h ticks=%0d spj=%0d spmin=%0d spmax=%0d minh=%0d minl=%0d didx=%0d",
            dut.edge_diag.l_pre,dut.edge_diag.l_post,dut.edge_diag.l_flags,dut.edge_diag.l_ticks,dut.edge_diag.l_spjump,
            dut.edge_diag.l_spmin,dut.edge_diag.l_spmax,dut.edge_diag.l_minh,dut.edge_diag.l_minl,dut.edge_diag.l_didx);
        if(dut.edge_diag.l_pre!=2066||dut.edge_diag.l_expect!=2066||dut.edge_diag.l_didx!=2065)$fatal(1,"A2066 pre/expect/didx");
        if(dut.edge_diag.l_post<298||dut.edge_diag.l_post>300)$fatal(1,"A2066 tail rises %0d (host sent 300)",dut.edge_diag.l_post);
        if(dut.edge_diag.l_excess!=0||dut.edge_diag.l_deficit!=0||dut.edge_diag.l_rej!=0||dut.edge_diag.l_rnt!=0||dut.edge_diag.l_spjump!=0)$fatal(1,"A2066 anomaly on a healthy window");
        if(!dut.edge_diag.l_flags[6]||!dut.edge_diag.l_flags[0])$fatal(1,"A2066 flags=%h",dut.edge_diag.l_flags);
        // 2065 spacings of ~5.4 sampler ticks.
        if(dut.edge_diag.l_ticks<10800||dut.edge_diag.l_ticks>11500)$fatal(1,"A2066 valid-interval ticks=%0d",dut.edge_diag.l_ticks);
        if(dut.edge_diag.l_spmin<5||dut.edge_diag.l_spmax>6)$fatal(1,"A2066 spacing %0d..%0d",dut.edge_diag.l_spmin,dut.edge_diag.l_spmax);
        if(dut.edge_diag.l_minh<2||dut.edge_diag.l_minl<2)$fatal(1,"A2066 pulse widths %0d/%0d",dut.edge_diag.l_minh,dut.edge_diag.l_minl);
        if(dut.edge_diag.excess_windows!=0||dut.edge_diag.deficit_windows!=0)$fatal(1,"A2066 history flagged a healthy window");

        // ---- (b1) extra CLOSE edge inside the reply (inside the 5-sample cooldown): reject + fault ----
        edge_clear();
        make(8'hb0,0,0);send();K=6;
        for(n=0;n<K;n=n+1)begin bus_clk=1;#12500;bus_clk=0;#12500;end
        @(negedge filter_clk);bus_clk=1;#9260;bus_clk=0;#9260;bus_clk=1;#9260;bus_clk=0;#50000;
        dir=0;#2000000;
        $display("B1: pre=%0d rej=%0d drp=%0d flags=%h excess=%0d deficit=%0d fpos=%0d fkind=%0d",
            dut.edge_diag.l_pre,dut.edge_diag.l_rej,dut.edge_diag.l_drp,dut.edge_diag.l_flags,dut.edge_diag.l_excess,dut.edge_diag.l_deficit,
            dut.edge_diag.l_fpos,dut.edge_diag.l_fkind);
        if(dut.edge_diag.l_rej<1)$fatal(1,"B1 reject not counted");
        if(!dut.edge_diag.l_flags[2])$fatal(1,"B1 fault flag missing");
        if(dut.edge_diag.l_excess!=1)$fatal(1,"B1 excess=%0d (one extra rise was rejected)",dut.edge_diag.l_excess);
        if(dut.edge_diag.l_deficit!=16-7)$fatal(1,"B1 deficit=%0d (fault ended the interval after 7 accepted rises)",dut.edge_diag.l_deficit);
        if(dut.edge_diag.l_fkind!=1||dut.edge_diag.l_fpos!==K+1)$fatal(1,"B1 first anomaly kind=%0d pos=%0d expected reject after byte %0d",dut.edge_diag.l_fkind,dut.edge_diag.l_fpos,K+1);
        if(dut.edge_diag.excess_windows<1||dut.edge_diag.min_fpos!==K+1)$fatal(1,"B1 history excess_windows=%0d min_fpos=%0d",dut.edge_diag.excess_windows,dut.edge_diag.min_fpos);
        edge_get(21);$display("B1 opcode idx21 excess=%0d",ev);if(st!=0)$fatal(1,"B1 idx21 st");
        edge_get(19);if(ev<1)$fatal(1,"B1 idx19");edge_get(23);if(ev<1)$fatal(1,"B1 idx23 worst excess");
        edge_get(31);if(ev!==K+1)$fatal(1,"B1 idx31 min first position=%0d",ev);
        info();tile(0);

        // ---- (b2) extra edge the filter ACCEPTS (spacing anomaly, no reject): 10MHz clock, one short extra cycle ----
        edge_clear();
        make(8'hb0,0,0);send();K=6;
        for(n=0;n<K;n=n+1)begin bus_clk=1;#50000;bus_clk=0;#50000;end
        bus_clk=1;#25000;bus_clk=0;#25000;                      // extra short cycle (period half of normal)
        for(n=K;n<16;n=n+1)begin bus_clk=1;#50000;bus_clk=0;#50000;end
        dir=0;#2000000;
        $display("B2: pre=%0d post=%0d rej=%0d flags=%h excess=%0d deficit=%0d fpos=%0d fkind=%0d spj=%0d spmin=%0d spmax=%0d",
            dut.edge_diag.l_pre,dut.edge_diag.l_post,dut.edge_diag.l_rej,dut.edge_diag.l_flags,dut.edge_diag.l_excess,dut.edge_diag.l_deficit,
            dut.edge_diag.l_fpos,dut.edge_diag.l_fkind,dut.edge_diag.l_spjump,dut.edge_diag.l_spmin,dut.edge_diag.l_spmax);
        if(dut.edge_diag.l_rej!=0||dut.edge_diag.l_drp!=0||dut.edge_diag.l_rnt!=0)$fatal(1,"B2 must not be a reject/drop/runt");
        if(dut.edge_diag.l_pre!=16||!dut.edge_diag.l_flags[6])$fatal(1,"B2 the serializer still completes by count");
        if(dut.edge_diag.l_post!=1)$fatal(1,"B2 the extra cycle shows up as one tail rise (got %0d)",dut.edge_diag.l_post);
        if(dut.edge_diag.l_spjump<2||dut.edge_diag.l_fkind!=4)$fatal(1,"B2 spacing anomaly not detected jumps=%0d kind=%0d",dut.edge_diag.l_spjump,dut.edge_diag.l_fkind);
        if(dut.edge_diag.l_fpos<K+1||dut.edge_diag.l_fpos>K+3)$fatal(1,"B2 first anomaly position %0d",dut.edge_diag.l_fpos);
        if(dut.edge_diag.l_spmin>12||dut.edge_diag.l_spmax<20)$fatal(1,"B2 spacing range %0d..%0d",dut.edge_diag.l_spmin,dut.edge_diag.l_spmax);
        if(!(dut.edge_diag.bad_windows>=1))$fatal(1,"B2 window not counted bad");
        info();

        // ---- (c) MISSING edge: one cycle fewer than the reply length, with a double-length gap ----
        edge_clear();
        make(8'hb0,0,0);send();K=6;
        for(n=0;n<K;n=n+1)begin bus_clk=1;#50000;bus_clk=0;#50000;end
        #100000;                                                  // the lost cycle
        for(n=K;n<15;n=n+1)begin bus_clk=1;#50000;bus_clk=0;#50000;end
        dir=0;#2000000;
        $display("C: pre=%0d post=%0d flags=%h excess=%0d deficit=%0d fpos=%0d fkind=%0d spj=%0d spmin=%0d spmax=%0d",
            dut.edge_diag.l_pre,dut.edge_diag.l_post,dut.edge_diag.l_flags,dut.edge_diag.l_excess,dut.edge_diag.l_deficit,
            dut.edge_diag.l_fpos,dut.edge_diag.l_fkind,dut.edge_diag.l_spjump,dut.edge_diag.l_spmin,dut.edge_diag.l_spmax);
        if(dut.edge_diag.l_pre!=15||dut.edge_diag.l_flags[6])$fatal(1,"C valid interval must end short: pre=%0d flags=%h",dut.edge_diag.l_pre,dut.edge_diag.l_flags);
        if(dut.edge_diag.l_deficit!=1||dut.edge_diag.l_excess!=0)$fatal(1,"C deficit=%0d excess=%0d",dut.edge_diag.l_deficit,dut.edge_diag.l_excess);
        if(dut.edge_diag.l_spjump<2||dut.edge_diag.l_fkind!=4||dut.edge_diag.l_spmax<40)$fatal(1,"C gap not seen jumps=%0d kind=%0d spmax=%0d",dut.edge_diag.l_spjump,dut.edge_diag.l_fkind,dut.edge_diag.l_spmax);
        if(dut.edge_diag.deficit_windows<1)$fatal(1,"C deficit_windows not counted");
        edge_get(22);$display("C opcode idx22 deficit=%0d",ev);if(st!=0||ev!=1)$fatal(1,"C idx22");
        edge_get(20);if(ev<1)$fatal(1,"C idx20");

        // ---- history clear and datapath unchanged by the monitor ----
        edge_clear();edge_get(1);if(ev>3)$fatal(1,"clear did not reset windows (%0d)",ev);
        edge_get(19);if(ev!=0)$fatal(1,"clear did not reset excess windows");
        repeat(4)begin tile(0);info();tile(1);end
        settle();
        if(dut.edge_diag.excess_windows!=0||dut.edge_diag.deficit_windows!=0||dut.edge_diag.bad_windows!=0)$fatal(1,"healthy traffic after clear flagged: bad=%0d",dut.edge_diag.bad_windows);
        $display("PASS EDGE=1 valid-interval edge counters: healthy replies with long idle tails are clean, close edge->reject, accepted extra edge->spacing jump, missing edge->deficit; packets=%0d",packets);$finish;
`endif
    end
    initial begin #10000000000;$fatal(1,"watchdog");end
endmodule
