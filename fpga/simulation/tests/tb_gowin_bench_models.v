`timescale 1ns/1ps
module tb_gowin_bench_models;
    reg clk=0, ce=1, oce=1, reset=0, wre=0;
    reg [2:0] block_sel=0;
    reg [13:0] ad=0;
    reg [35:0] di=0;
    wire [35:0] dout;
    reg host_enable=0, host_data=0, buffer_enable_n=1, buffer_input=0;
    wire pin, buffer_output;
    SPX9 dut(.DO(dout), .CLK(clk), .CE(ce), .OCE(oce), .RESET(reset),
             .WRE(wre), .BLKSEL(block_sel), .AD(ad), .DI(di));
    IOBUF io(.I(buffer_input), .OEN(buffer_enable_n), .IO(pin), .O(buffer_output));
    assign pin=host_enable ? host_data : 1'bz;
    task tick; begin #5; clk=1; #1; #4; clk=0; #1; end endtask
    task expect_data(input [17:0] expected);
        begin if(dout[17:0] !== expected) $fatal(1,"expected %h got %h",expected,dout[17:0]); end
    endtask
    initial begin
        #1;
        if(pin !== 1'bz || buffer_output !== 1'bz) $fatal(1,"IOBUF idle");
        host_enable=1; host_data=1; #1; if(buffer_output !== 1) $fatal(1,"IOBUF input");
        host_enable=0; buffer_enable_n=0; buffer_input=0; #1;
        if(pin !== 0 || buffer_output !== 0) $fatal(1,"IOBUF output low");
        buffer_input=1; #1; if(pin !== 1 || buffer_output !== 1) $fatal(1,"IOBUF output high");
        buffer_enable_n=1; #1; if(pin !== 1'bz) $fatal(1,"IOBUF release");
        // WRITE_MODE=2 returns the old word, then stores the new word.
        ad={10'd1,2'b00,2'b11}; di=18'h2a5c3; wre=1; tick(); expect_data(0);
        di=18'h12345; tick(); expect_data(18'h2a5c3);
        wre=0; tick(); expect_data(18'h12345);
        // A changed address alone must not update the bypass output before a clock.
        ad={10'd1023,4'b0000}; #1; expect_data(18'h12345);
        tick(); expect_data(0);
        wre=1; ad={10'd1023,2'b00,2'b11}; di=18'h3d872; tick(); expect_data(0);
        wre=0; ad={10'd1,4'b0000}; tick(); expect_data(18'h12345);
        ad={10'd1023,4'b0000}; tick(); expect_data(18'h3d872);
        // Individual 9-bit lanes have independent active-high byte enables.
        wre=1; ad={10'd1,2'b00,2'b01}; di=18'h001aa; tick(); expect_data(18'h12345);
        wre=0; tick(); expect_data((18'h12345 & 18'h3fe00) | 18'h001aa);
        wre=1; ad={10'd1,2'b00,2'b10}; di=18'h2c000; tick();
        wre=0; tick(); expect_data(18'h2c1aa);
        // Bypass mode ignores OCE, CE and block select suppress accesses.
        oce=0; ad={10'd1023,4'b0000}; tick(); expect_data(18'h3d872);
        ce=0; wre=1; ad={10'd1023,2'b00,2'b11}; di=18'h00001; tick(); expect_data(18'h3d872);
        ce=1; wre=0; tick(); expect_data(18'h3d872);
        block_sel=1; wre=1; di=18'h00002; tick(); expect_data(18'h3d872);
        block_sel=0; wre=0; tick(); expect_data(18'h3d872);
        // Async output reset acts without a clock, and never clears memory.
        reset=1; #1; expect_data(0); reset=0; #1; expect_data(0);
        tick(); expect_data(18'h3d872);
        $display("PASS independent SPX9 and IOBUF functional tests"); $finish;
    end
endmodule
module tb_gowin_bench_nonzero_init;
    wire [35:0] dout;
    SPX9 #(.INIT_RAM_3F(288'b1)) invalid(.DO(dout),.CLK(1'b0),.CE(1'b1),.OCE(1'b1),.RESET(1'b0),.WRE(1'b0),.BLKSEL(3'b0),.AD(14'b0),.DI(36'b0));
endmodule
module tb_gowin_bench_unsupported_alu;
    wire s,c;
    ALU #(.ALU_MODE(0)) invalid(.SUM(s),.COUT(c),.I0(1'b0),.I1(1'b0),.I3(1'b0),.CIN(1'b0));
endmodule
module tb_gowin_bench_unsupported;
    wire [35:0] dout;
    SPX9 #(.BIT_WIDTH(9)) invalid(.DO(dout),.CLK(1'b0),.CE(1'b1),.OCE(1'b1),.RESET(1'b0),.WRE(1'b0),.BLKSEL(3'b0),.AD(14'b0),.DI(36'b0));
endmodule
