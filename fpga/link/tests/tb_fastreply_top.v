`timescale 1ps/1ps
// Test-only nominal PLL model: checks digital LOCK/reset policy, not analog PLL.
module rPLL #(parameter FCLKIN="27.0",parameter IDIV_SEL=0,
               parameter FBDIV_SEL=1,parameter ODIV_SEL=16)(
    output reg CLKOUT=0,output reg LOCK=0,output CLKOUTP,CLKOUTD,CLKOUTD3,
    input RESET,RESET_P,CLKIN,CLKFB,input [5:0] FBDSEL,IDSEL,ODSEL,
    input [3:0] PSDA,DUTYDA,FDLY);
    integer count=0;
    assign CLKOUTP=0;assign CLKOUTD=0;assign CLKOUTD3=0;
    always #9259 CLKOUT=~CLKOUT;
    always @(posedge CLKIN or posedge RESET) begin
        if(RESET)begin count<=0;LOCK<=0;end
        else if(count==7)LOCK<=1;else count<=count+1;
    end
    initial if(IDIV_SEL!=0 || FBDIV_SEL!=1 || ODIV_SEL!=16)$fatal(1,"wrong PLL ratio");
endmodule
module tb_fastreply_top;
    reg osc=0,reset_n=0,arm=1,bus_clk=0,dir=0,host_oe=0;
    reg [7:0] host_data=0,q[0:7],r[0:7];
    tri [7:0] data;
    wire ready;wire [3:0] led;
    integer i,edges=0,before_edges;
    reg [15:0] crc;
    always begin #18518;osc=1;#18519;osc=0;end
    assign data=host_oe?host_data:8'hzz;
    tab5_dock_triangle54_fast_top dut(osc,reset_n,arm,bus_clk,dir,4'b0,data,ready,led);
    always @(posedge dut.core_clk)edges=edges+1;
    always @(posedge dut.core_clk)if(host_oe && dut.platform.data_oe)$fatal(1,"bus contention");
    function [15:0] crc_byte(input [15:0] c,input [7:0] b);
        reg [15:0] v;integer j;
        begin v=c^{b,8'b0};for(j=0;j<8;j=j+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    task make(input [7:0] op,input [7:0] a,input [7:0] b);
        begin q[0]=8'ha5;q[1]=op;q[2]=8'h22;q[3]=2;q[4]=a;q[5]=b;
            crc=16'hffff;for(i=0;i<6;i=i+1)crc=crc_byte(crc,q[i]);q[6]=crc[7:0];q[7]=crc[15:8];end
    endtask
    task pulse;begin #1000000;bus_clk=1;#1000000;bus_clk=0;#1000000;end endtask
    task send;
        begin dir=0;#1000000;host_oe=1;
            for(i=0;i<8;i=i+1)begin host_data=q[i];pulse();end
            host_oe=0;wait(ready);dir=1;#1000000;end
    endtask
    task read_reply;
        begin for(i=0;i<8;i=i+1)begin r[i]=data;pulse();end
            crc=16'hffff;for(i=0;i<6;i=i+1)crc=crc_byte(crc,r[i]);
            if(r[0]!=8'h5a || r[2]!=8'h22 || r[3]!=2 || r[6]!=crc[7:0] || r[7]!=crc[15:8])$fatal(1,"bad reply");
            if(ready || data!==8'hzz)$fatal(1,"reply not released");dir=0;#1000000;end
    endtask
    initial begin
        #100000;reset_n=1;
        if(dut.pll_locked || ready || data!==8'hzz)$fatal(1,"output before PLL lock");
        wait(dut.pll_locked);#200000;before_edges=edges;#1851800;
        if(edges-before_edges!=100)$fatal(1,"nominal54MHz model frequency");
        make(8'h30,0,0);send();read_reply();
        if(r[1]!=0 || r[4]!=31 || r[5]!=2)$fatal(1,"wrong version2 INFO");
        make(8'h3d,0,0);send();read_reply();
        if(r[1]!=0 || r[4]!=54 || r[5]!=0)$fatal(1,"wrong core MHz");
        make(8'h3d,1,0);send();read_reply();if(r[1]!=3)$fatal(1,"badargs accepted");
        make(8'h3d,0,1);send();read_reply();if(r[1]!=3)$fatal(1,"bad high args accepted");
        make(8'hb0,0,0);send();pulse();arm=0;#1;
        if(ready || data!==8'hzz)$fatal(1,"raw ARM did not release immediately");
        dir=0;#200000;arm=1;#200000;
        make(8'hb0,0,0);send();pulse();force dut.pll_locked=0;#1;
        if(ready || data!==8'hzz)$fatal(1,"PLL lock loss did not release immediately");
        dir=0;#200000;release dut.pll_locked;#200000;
        make(8'h3d,0,0);send();read_reply();if(r[1]!=0 || r[4]!=54)$fatal(1,"relock recovery");
        make(8'hb0,0,0);send();pulse();reset_n=0;#1;
        if(ready || data!==8'hzz)$fatal(1,"raw reset did not release immediately");
        $display("PASS PLL54 top nominal model, lock gate, INFO/clock/args, raw ARM/reset/lock-loss/relock");$finish;
    end
    initial begin #1000000000;$fatal(1,"watchdog");end
endmodule
