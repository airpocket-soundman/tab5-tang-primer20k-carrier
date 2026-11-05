`timescale 1ns/1ps
module tb_all_scenes_tile;
    reg clk=0;always #5 clk=~clk;
    reg reset_n=0,abort=0,start=0;
    reg [7:0] opcode=0,a=0,b=0;
    wire done,off_done;
    wire [7:0] status,off_status;
    wire [15:0] result;
    wire [7:0] row_byte;
    reg [15:0] expected[0:1023],fire_expected[0:1023];
    integer i,j,transactions=0;
    reg [2047:0] golden;
`ifdef VENDOR_RAM
    GSR GSR(1'b1);
`endif
    triangle_tile #(.ALL_SCENES_ENABLE(1),.RAW_READ_ENABLE(1)) dut(
        .clk(clk),.reset_n(reset_n),.abort(abort),.start(start),.opcode(opcode),.a(a),.b(b),
        .done(done),.status(status),.result(result),.row_index(11'b0),.row_byte(row_byte),
        .raw_clk(clk),.raw_enable(1'b0),.raw_address(10'b0),.raw_color(),.raw_depth());
    triangle_tile #(.ALL_SCENES_ENABLE(0)) off_dut(
        .clk(clk),.reset_n(reset_n),.abort(abort),.start(start),.opcode(opcode),.a(a),.b(b),
        .done(off_done),.status(off_status),.result(),.row_index(11'b0),.row_byte(),
        .raw_clk(clk),.raw_enable(1'b0),.raw_address(10'b0),.raw_color(),.raw_depth());
    task command;
        input [7:0] op;input [15:0] value;
        input [7:0] want_status;input [15:0] want_result;
        integer cycles;
        begin
            @(negedge clk);opcode=op;a=value[7:0];b=value[15:8];start=1;
            @(negedge clk);start=0;cycles=0;
            if((op>=8'h60 || op==8'h5e) && (!off_done || off_status!==2))
                $fatal(1,"disabled feature accepted op%h status%h",op,off_status);
            while(!done) begin @(negedge clk);cycles=cycles+1;if(cycles>500000)$fatal(1,"tile timeout op%h",op);end
            if(status!==want_status || (want_status==0 && result!==want_result))
                $fatal(1,"op%h value%h status%h result%h expected%h/%h",op,value,status,result,want_status,want_result);
            transactions=transactions+1;
            @(negedge clk);
        end
    endtask
    task check_tile;
        integer at;
        begin for(at=0;at<1024;at=at+1) command(8'h2d,{3'b0,at[9:5],3'b0,at[4:0]},0,expected[at]);end
    endtask
    task setup_draw;
        input integer kind,x0,y0,x1,y1;input [15:0] ink;input [23:0] rgb;
        begin
            command(8'h61,x0,0,x0);command(8'h62,y0,0,y0);
            command(8'h63,x1,0,x1);command(8'h64,y1,0,y1);
            command(8'h65,ink,0,ink);command(8'h66,rgb[23:8],0,rgb[23:8]);
            command(8'h67,{8'b0,rgb[7:0]},0,{8'b0,rgb[7:0]});command(8'h68,kind,0,kind);
            command(8'h69,0,0,0);command(8'h6a,0,0,0);
        end
    endtask
    function [15:0] reference_add;
        input [15:0] dst;input [23:0] rgb;
        integer r,g,b;
        begin
            r=(dst>>11)*255/31+rgb[23:16];g=((dst>>5)&63)*255/63+rgb[15:8];b=(dst&31)*255/31+rgb[7:0];
            if(r>255)r=255;if(g>255)g=255;if(b>255)b=255;
            reference_add=((r&248)<<8)|((g&252)<<3)|(b>>3);
        end
    endfunction
    initial begin
        if(!$value$plusargs("fire=%s",golden))$fatal(1,"Fire golden missing");
        $readmemh(golden,fire_expected);
        repeat(3)@(negedge clk);reset_n=1;
        command(8'h5e,0,0,0);command(8'h5e,1,3,0);
        command(8'h60,0,0,16'h011f);command(8'h70,0,0,16'h0101);
        command(8'h60,1,3,0);command(8'h70,256,3,0);
        command(8'h6b,0,5,0);command(8'h6c,0,5,0);command(8'h6f,0,5,0);command(8'h78,0,5,0);
        command(8'h2b,16'h1234,0,0);
        command(8'h6d,1,3,0);command(8'h6d,0,0,0);
        for(i=0;i<1024;i=i+1) begin
            expected[i]=(i*37)^16'ha55a;
            command(8'h6c,expected[i],0,i+1);
            if(i==1022) command(8'h2d,0,5,0);
        end
        command(8'h6c,16'hffff,3,0);
        check_tile;
        setup_draw(0,31,31,0,0,16'hfa09,0);command(8'h6b,1,3,0);command(8'h6b,0,0,1024);
        expected[1023]=16'hfa09;
        setup_draw(2,-4,-3,4,5,16'h67a9,0);command(8'h6b,0,0,1024);
        for(i=0;i<=5;i=i+1)for(j=0;j<=4;j=j+1)expected[i*32+j]=16'h67a9;
        // Exact 45-degree line crossing both tile boundaries.
        setup_draw(1,-10,-10,40,40,16'hf81f,0);command(8'h6b,0,0,1024);
        for(i=0;i<32;i=i+1)expected[i*33]=16'hf81f;
        setup_draw(3,4,3,0,0,0,24'h3264c8);command(8'h6b,0,0,1024);
        expected[3*32+4]=reference_add(expected[3*32+4],24'h3264c8);
        command(8'h6b,0,0,1024);expected[3*32+4]=reference_add(expected[3*32+4],24'h3264c8);
        command(8'h67,16'h0100,3,0);command(8'h68,4,3,0);command(8'h69,1,3,0);
        check_tile;
        command(8'h6f,0,0,1024);
        for(i=0;i<1024;i=i+1)
            expected[i]=((((expected[i]>>11)*29/32)&31)<<11)|
                         (((((expected[i]>>5)&63)*29/32)&63)<<5)|(((expected[i]&31)*29/32)&31);
        check_tile;
        // Fire at a partial bottom tile, including zero-filled out-of-frame pixels.
        command(8'h71,288,0,288);command(8'h72,160,0,160);command(8'h73,320,0,320);
        command(8'h74,180,0,180);command(8'h75,65535,0,65535);command(8'h76,0,0,0);command(8'h77,2,0,2);
        command(8'h78,1,3,0);command(8'h78,0,0,1024);
        for(i=0;i<1024;i=i+1)expected[i]=fire_expected[i];check_tile;
        command(8'h73,319,0,319);command(8'h78,0,3,0);
        command(8'h73,320,0,320);command(8'h77,3,0,3);command(8'h78,0,3,0);
        command(8'h77,2,0,2);command(8'h71,320,0,320);command(8'h78,0,3,0);
        check_tile;
        // Abort removes initialization and parameters, and a fresh clear is required.
        setup_draw(1,-32768,0,32767,0,16'hffff,0);
        @(negedge clk);opcode=8'h6b;a=0;b=0;start=1;
        @(negedge clk);start=0;
        repeat(6)@(negedge clk);abort=1;
        repeat(2)@(negedge clk);abort=0;
        command(8'h2d,0,5,0);command(8'h6b,0,5,0);command(8'h78,0,5,0);
        command(8'h2b,0,0,0);command(8'h6b,0,5,0);
        command(8'h6d,0,0,0);command(8'h6c,16'h7fe0,0,1);
        @(negedge clk);abort=1;@(negedge clk);abort=0;
        command(8'h6c,16'hffff,5,0);command(8'h2d,0,5,0);
        $display("all-scenes tile RTL PASS: %0d transactions, full upload/2D/fade/Fire pixel checks, disabled ABI and abort",transactions);
        $finish;
    end
endmodule
