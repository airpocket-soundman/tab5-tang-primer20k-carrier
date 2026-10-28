`timescale 1ns/1ps
// Python-generated independent CRC/result oracle shared with the C host test.
module tb_link_vectors;
    localparam COUNT=583;
    reg sys_clk=0, reset_n=0, arm=0, bus_clk=0, dir=0, host_oe=0;
    reg [7:0] host_data=0;
    wire [7:0] data_o;
    wire data_oe,ready;
    wire [7:0] bus_data=host_oe ? host_data : data_oe ? data_o : 8'bz;
    reg [127:0] vectors[0:COUNT-1];
    integer n,b;
    always #5 sys_clk=~sys_clk;
    link_bringup #(.TIMEOUT_CYCLES(5000)) dut(sys_clk,reset_n,arm,bus_clk,dir,bus_data,data_o,data_oe,ready);
    always @(posedge sys_clk) if(host_oe && data_oe) $fatal(1,"bus contention");
    task pulse;
        begin #100; bus_clk=1; #100; bus_clk=0; #100; end
    endtask
    initial begin
        $readmemh("link/tests/link_vectors.mem",vectors);
        #100; reset_n=1; arm=1; #100;
        for(n=0;n<COUNT;n=n+1) begin
            dir=0; #100; host_oe=1;
            for(b=0;b<8;b=b+1) begin
                host_data=vectors[n][127-b*8 -: 8]; pulse();
            end
            host_oe=0; #200; dir=1; #200;
            if(!ready || !data_oe) $fatal(1,"vector %0d response missing",n);
            for(b=0;b<8;b=b+1) begin
                if(bus_data !== vectors[n][63-b*8 -: 8])
                    $fatal(1,"vector %0d byte %0d actual %02x expected %02x",n,b,bus_data,vectors[n][63-b*8 -: 8]);
                pulse();
            end
            dir=0; #200;
            if(ready || data_oe) $fatal(1,"vector %0d not released",n);
        end
        $display("PASS Python golden vectors: %0d",COUNT);
        $finish;
    end
    initial begin #10000000; $fatal(1,"vector watchdog"); end
endmodule
