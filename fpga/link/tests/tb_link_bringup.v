`timescale 1ns/1ps
module tb_link_bringup;
    reg sys_clk=0, reset_n=0, arm=0, bus_clk=0, dir=0;
    reg host_oe=0;
    reg [7:0] host_data=0;
    wire [7:0] data_o;
    wire data_oe,ready;
    wire [7:0] bus_data=host_oe ? host_data : data_oe ? data_o : 8'bz;
    reg [7:0] q[0:7],r[0:7];
    reg [15:0] crc;
    integer i,n;
    always #5 sys_clk=~sys_clk;
    link_bringup #(.TIMEOUT_CYCLES(5000)) dut(sys_clk,reset_n,arm,bus_clk,dir,bus_data,data_o,data_oe,ready);
    always @(posedge sys_clk) if(host_oe && data_oe) $fatal(1,"bus contention");
    function [15:0] crc_byte;
        input [15:0] c; input [7:0] b;
        reg [15:0] v; integer k;
        begin v=c^{b,8'b0}; for(k=0;k<8;k=k+1) v=v[15]?(v<<1)^16'h1021:v<<1; crc_byte=v; end
    endfunction
    task pulse;
        begin #100; bus_clk=1; #100; bus_clk=0; #100; end
    endtask
    task send_request;
        input [7:0] op,a,b; input corrupt;
        integer t; reg [15:0] c;
        begin
            dir=0; #100; host_oe=1;
            q[0]=8'ha5; q[1]=op; q[2]=8'h73; q[3]=2; q[4]=a; q[5]=b;
            c=16'hffff; for(t=0;t<6;t=t+1) c=crc_byte(c,q[t]);
            q[6]=c[7:0]^corrupt; q[7]=c[15:8];
            for(t=0;t<8;t=t+1) begin host_data=q[t]; pulse(); end
            host_oe=0; #200; dir=1; #200;
            if(!ready || !data_oe) $fatal(1,"response missing");
        end
    endtask
    task read_response;
        integer t; reg [15:0] c;
        begin
            for(t=0;t<8;t=t+1) begin r[t]=bus_data; pulse(); end
            dir=0; #200;
            if(ready || data_oe) $fatal(1,"response not released");
            c=16'hffff; for(t=0;t<6;t=t+1) c=crc_byte(c,r[t]);
            if(r[0]!==8'h5a || r[2]!==8'h73 || r[3]!==2 || r[6]!==c[7:0] || r[7]!==c[15:8]) $fatal(1,"response envelope/CRC");
        end
    endtask
    initial begin
        #100; reset_n=1; #100;
        if(data_oe || ready) $fatal(1,"unarmed drives bus");
        arm=1; #100;
        send_request(1,0,0,0); read_response();
        if(r[1]!==0 || r[4]!==8'h54 || r[5]!==8'h50) $fatal(1,"ID");
        for(n=0;n<256;n=n+1) begin
            send_request(2,n,n^8'ha5,0); read_response();
            if(r[1]!==0 || r[4]!==q[4] || r[5]!==q[5]) $fatal(1,"echo");
            send_request(3,n,255-n,0); read_response();
            if(r[1]!==0 || r[4]!==~q[4] || r[5]!==~q[5]) $fatal(1,"invert");
        end
        send_request(2,1,2,1); read_response(); if(r[1]!==1) $fatal(1,"bad CRC accepted");
        send_request(99,1,2,0); read_response(); if(r[1]!==2) $fatal(1,"unknown op accepted");
        // Partial request followed by invalid direction: must not drive.
        host_oe=1; host_data=8'ha5; pulse(); host_oe=0; dir=1; #200;
        if(data_oe || ready) $fatal(1,"partial request response");
        dir=0; #200;
        send_request(1,0,0,0); // timeout while response pending
        #60000; if(ready || data_oe) $fatal(1,"timeout did not release bus");
        dir=0; #200; send_request(1,0,0,0);
        arm=0; #1; if(data_oe || ready) $fatal(1,"disarm release");
        #100; arm=1; dir=0; #100; send_request(1,0,0,0);
        reset_n=0; #1; if(data_oe || ready) $fatal(1,"reset release");
        #100; reset_n=1; dir=0; #100; send_request(1,0,0,0);
        dir=0; #1; if(data_oe) $fatal(1,"raw DIR release");
        $display("PASS link-bringup: ID, 512 patterns, CRC/op rejection, partial DIR, timeout, arm/reset/OE");
        $finish;
    end
    initial begin #10000000; $fatal(1,"testbench watchdog"); end
endmodule
