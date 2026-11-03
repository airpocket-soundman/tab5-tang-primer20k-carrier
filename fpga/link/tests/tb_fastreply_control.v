`timescale 1ps/1ps
module tb_fastreply_control;
    reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
    reg [7:0] host_data=0,q[0:7],r[0:2065];
    wire [7:0] data_i=host_data,data_o;wire ready,oe;
    integer i,waits,seqno=0,packets=0;reg [15:0] crc;
    reg [49:0] previous_metadata;reg previous_offer=0;
    always #9259 clk=~clk;
    link_bringup #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(5000),.CORE_CLOCK_MHZ(54),
        .CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1)) dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready);
    always @(posedge clk) begin
        if(host_oe && oe)$fatal(1,"contention");
        if(dut.fast_offer && previous_offer && dut.fast_metadata!==previous_metadata)$fatal(1,"metadata changed under offer");
        previous_metadata<=dut.fast_metadata;previous_offer<=dut.fast_offer;
        if(dut.raw_ram_enable && (dut.triangle.renderer.state==1 || dut.triangle.renderer.state==13 ||
           (dut.triangle.renderer.state==6 && dut.triangle.renderer.fragment_valid && dut.triangle.renderer.fragment_write)))
            $fatal(1,"RAM write raced raw read ownership");
        if((dut.triangle.renderer.state==1 || dut.triangle.renderer.state==13 ||
           (dut.triangle.renderer.state==6 && dut.triangle.renderer.fragment_valid && dut.triangle.renderer.fragment_write)) &&
           dut.triangle.renderer.tile_stream)$fatal(1,"SYS shared-port address invariant");
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
            // Existing master handoff raises idle CLK while DIR=0: ignored.
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
            // The final physical sample must release outputs independently of
            // a later SYS acknowledgement, including when bus_clk then stops.
            #1;if(ready || oe)$fatal(1,"last byte did not release immediately");
            for(j=0;j<8;j=j+1)if(r[j]!=8'hc3)$fatal(1,"prefix count/data changed");
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
        begin make(8'hb0,0,0);send();read_count(16,12500);complete(16);
            if(r[9]!=0 || r[12]!=31 || r[13]!=2)$fatal(1,"wrong vivid v2 INFO");end
    endtask
    task clear;
        begin make(8'hab,8'haa,8'h55);send();read_count(16,12500);complete(16);if(r[9]!=0)$fatal(1,"clear failed");end
    endtask
    task tile(input integer plane);
        integer j;
        begin make(8'hbb,0,plane);send();read_count(2066,12500);complete(2066);
            if(r[9]!=0 || r[12]!=0 || r[13]!=plane)$fatal(1,"tile metadata");
            for(j=16;j<2064;j=j+1)if(r[j]!== (plane?8'h00:(j%2?8'h55:8'haa)))$fatal(1,"tile word mismatch byte=%0d",j);
        end
    endtask
    initial begin
        #100000;reset_n=1;arm=1;#200000;info();clear();tile(0);tile(1);info();
        // Repeated packets vary seq/plane and prove four-phase state reset.
        repeat(8)begin tile(0);info();tile(1);end
        make(8'hb0,0,0);send();dir=0;#1;
        if(!ready || oe)$fatal(1,"pre-first-byte DIR wait must remain offered");
        #200000;dir=1;#200000;read_count(16,12500);complete(16);
        // Abort with stopped LOW clock using raw DIR. No bus edge can help.
        make(8'hbb,0,0);send();read_count(17,12500);dir=0;#1;
        if(ready || oe)$fatal(1,"DIR abort not immediate");#200000;info();tile(0);
        make(8'hbb,0,0);send();read_count(33,12500);arm=0;#1;
        if(ready || oe)$fatal(1,"ARM abort not immediate");dir=0;#200000;arm=1;#200000;info();clear();
        make(8'hbb,0,0);send();read_count(9,12500);reset_n=0;#1;
        if(ready || oe)$fatal(1,"reset abort not immediate");dir=0;#200000;reset_n=1;#200000;info();clear();
        // Stopped HIGH clock, mid-frame timeout: SYS must release without RAW edges.
        make(8'hbb,0,0);send();read_count(20,12500);bus_clk=1;#100000000;
        if(ready || oe || dut.fast_offer)$fatal(1,"stopped HIGH clock timeout");bus_clk=0;dir=0;#200000;info();tile(1);
        // No read edge at all after READY must also time out cleanly.
        make(8'hbb,0,0);send();#100000000;
        if(ready || oe || dut.fast_offer)$fatal(1,"no-clock timeout");dir=0;#200000;info();
        // Malformed tagged requests stay ordinary unprefixed eight-byte errors.
        make(8'h81,0,0);q[6]=q[6]^1;send();read_count(8,500000);
        if(ready || oe || r[0]!=8'h5a || r[1]!=1)$fatal(1,"bad-tag CRC path changed");
        $display("PASS RAW control packets=%0d exact prefix/CRC, no write race, DIR/ARM/reset/timeout with stopped CLK, repeated planes/seq",packets);$finish;
    end
    initial begin #10000000000;$fatal(1,"watchdog");end
endmodule
