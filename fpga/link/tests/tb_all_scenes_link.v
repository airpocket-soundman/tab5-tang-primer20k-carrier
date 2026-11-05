`timescale 1ns/1ps
module tb_all_scenes_link;
reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0;
reg [7:0] data_i=0;
wire [7:0] data_o;wire oe,ready;
`ifdef FEATURE_OFF
localparam ENABLE=0;
`else
localparam ENABLE=1;
`endif
`ifdef FAST_REPLY
localparam FAST=1;
`else
localparam FAST=0;
`endif
`ifdef VENDOR_RAM
GSR GSR(1'b1);
`endif
link_bringup #(.GFX_ENABLE(2),.ALL_SCENES_ENABLE(ENABLE),.FAST_REPLY_ENABLE(FAST),.TIMEOUT_CYCLES(2000000)) dut(
    clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready);
`ifdef REGISTERED_INPUT
`ifndef FEATURE_OFF
defparam dut.triangle.scenes_batch.staging2d.REGISTER_INPUT=1;
defparam dut.triangle.scenes_batch.upload_staging.REGISTER_INPUT=1;
`endif
`endif
always #5 clk=~clk;
always @(posedge clk) begin
    if(dut.batch_receiving && (dut.batch_cmd_start || dut.triangle.renderer.sys_writing))
        $fatal(1,"unvalidated batch execution or RAM write");
end
reg [7:0] q[0:1289],r[0:2065];
integer fd,qlen,rlen,i,n,cycles,vectors=0;
reg [2047:0] path;
task pulse;begin #60;bus_clk=1;#60;bus_clk=0;#60;end endtask
initial begin
    #100;reset_n=1;arm=1;#100;
    if(!$value$plusargs("vectors=%s",path))$fatal(1,"vectors missing");
    fd=$fopen(path,"r");
    while(!$feof(fd)) begin
        n=$fscanf(fd,"%d %d",qlen,rlen);
        if(n==2)begin
            for(i=0;i<qlen;i=i+1)n=$fscanf(fd,"%h",q[i]);
            for(i=0;i<rlen;i=i+1)n=$fscanf(fd,"%h",r[i]);
            dir=0;#100;
            for(i=0;i<qlen;i=i+1)begin data_i=q[i];pulse();end
            if(rlen==0)begin
                // The vector is deliberately truncated before its payload CRC.
                if(ready || !dut.batch_receiving)$fatal(1,"truncated batch state invalid");
                arm=0;#200;if(ready||oe)$fatal(1,"ARM drop did not release bus");
                arm=1;#200;
            end else begin
                cycles=0;while(!ready && cycles<1900000)begin #10;cycles=cycles+1;end
                if(!ready)$fatal(1,"timeout vector%0d",vectors);
                dir=1;#100;
                for(i=0;i<rlen;i=i+1)begin
                    if(!oe || data_o!==r[i])$fatal(1,"vector%0d byte%0d got%h want%h oe%0d",vectors,i,data_o,r[i],oe);
                    pulse();
                end
                #50;if(ready||oe)$fatal(1,"reply not complete vector%0d",vectors);
                dir=0;#100;
            end
            vectors=vectors+1;
        end
    end
    $display("all-scenes LINK RTL PASS: enabled%0d vectors%0d, exact bytes/CRC, pre-CRC write prohibition and abort",ENABLE,vectors);
    $finish;
end
initial begin #1000000000;$fatal(1,"watchdog");end
endmodule
