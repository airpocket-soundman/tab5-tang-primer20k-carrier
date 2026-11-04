`timescale 1ps/1ps
// Track N: reply clock phase offset (REPLY_PHASE_TICKS). The host clock is slow
// (2.5MHz) so a delay of up to 15 sampler ticks never reaches the next host edge;
// this proves functional equivalence and measures the added DATA delay.
module tb_reply_phase;
    parameter TICKS=0;
    reg filter_clk=0;always #2315 filter_clk=~filter_clk;
    reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
    reg [7:0] host_data=0,q[0:7],r[0:2065];
    wire [7:0] data_i=host_data,data_o;wire ready,oe;
    integer i,waits,seqno=0,packets=0;reg [15:0] crc;
    always #9259 clk=~clk;
    link_bringup_filtered #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(5000),.CORE_CLOCK_MHZ(54),
        .CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1),.REPLY_PHASE_TICKS(TICKS)) dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready,filter_clk,reset_n && arm);
    always @(posedge clk) if(host_oe && oe)$fatal(1,"contention");
    // DATA-change delay relative to the last host CLK rise (only while the reply is driven).
    time last_rise=0;integer dmin=1000000000,dmax=0,dcount=0;
    always @(posedge bus_clk) last_rise=$time;
    always @(data_o) if(oe && dir && last_rise!=0 && $time-last_rise<200000) begin
        if($time-last_rise<dmin)dmin=$time-last_rise;
        if($time-last_rise>dmax)dmax=$time-last_rise;
        dcount=dcount+1;
    end
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
    // With a phase offset the last (delayed) CLK pulse reaches the serializer up to
    // TICKS sampler cycles after the host edge, so OE/READY release is delayed by the
    // same amount (documented risk for the turnaround). Bound it, do not require #1.
    task complete(input integer count);
        integer j,w;reg [15:0] v;
        begin
            w=0;while((ready||oe)&&w<100)begin #1000;w=w+1;end
            if(ready || oe)$fatal(1,"output did not release within 100ns after last CLK (ticks=%0d)",TICKS);
            if(w>TICKS*4630/1000+8)$fatal(1,"release took %0dns, expected <= %0d",w,TICKS*4630/1000+8);
            for(j=0;j<8;j=j+1)if(r[j]!=8'hc3)$fatal(1,"prefix changed");
            v=16'hffff;for(j=8;j<14;j=j+1)v=crc_byte(v,r[j]);
            if(r[8]!=8'h5a || r[10]!=q[2] || r[11]!=2 || r[14]!=v[7:0] || r[15]!=v[15:8])$fatal(1,"bad header/seq/CRC");
            if(count>16)begin
                for(j=16;j<count-2;j=j+1)v=crc_byte(v,r[j]);
                if(r[count-2]!=v[7:0] || r[count-1]!=v[15:8])$fatal(1,"bad bound CRC");
            end
            dir=0;#200000;
            if(dut.valid || dut.fast_offer)$fatal(1,"SYS acknowledgement stuck");
            packets=packets+1;
        end
    endtask
    task info;
        begin make(8'hb0,0,0);send();read_count(16,200000);complete(16);if(r[9]!=0)$fatal(1,"info status");end
    endtask
    task clear;
        begin make(8'hab,8'haa,8'h55);send();read_count(16,200000);complete(16);if(r[9]!=0)$fatal(1,"clear failed");end
    endtask
    task tile(input integer plane);
        integer j;
        begin make(8'hbb,0,plane);send();read_count(2066,200000);complete(2066);
            if(r[9]!=0 || r[13]!=plane)$fatal(1,"tile metadata");
            for(j=16;j<2064;j=j+1)if(r[j]!== (plane?8'h00:(j%2?8'h55:8'haa)))$fatal(1,"tile word mismatch byte=%0d",j);
        end
    endtask
    initial begin
        #100000;reset_n=1;arm=1;#200000;
        info();clear();tile(0);tile(1);info();
        repeat(2)begin tile(0);info();tile(1);end
        // DIR abort mid-frame must still release and recover with a delayed clock.
        make(8'hbb,0,0);send();read_count(17,200000);dir=0;#1;
        if(ready || oe)$fatal(1,"DIR abort not immediate");#400000;info();tile(0);
        $display("PHASE_RESULT ticks=%0d dmin_ps=%0d dmax_ps=%0d changes=%0d",TICKS,dmin,dmax,dcount);
        $display("PASS ticks=%0d packets=%0d",TICKS,packets);$finish;
    end
    initial begin #10000000000;$fatal(1,"watchdog");end
endmodule
