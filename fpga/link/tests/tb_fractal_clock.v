`timescale 1ns/1ps
// Track G: tagged Mandelbrot TILE_READ through the RAW serializer with a
// free-running host clock (DMA-like) and an optional extra bus_clk edge.
// Digital model only: no analog crosstalk, ringing or pad delay.
module tb_fractal_clock #(parameter MODE=0, parameter HALF_NS=100, parameter GLITCH_AT=900);
    reg clk=0, reset_n=0, arm=0, bus_clk=0, dir=0, host_oe=0;
    reg [7:0] host_data=0;
    tri [7:0] data;
    wire ready;wire [3:0] led;
    reg [7:0] q[0:7],expected[0:2065],got[0:2065];
    reg [1023:0] path;
    integer fd,n,i,count,length,cycles,first_bad,ready_drop,released_at,j;
    always #9.259 clk=~clk;
    assign data=host_oe?host_data:8'hzz;
    tab5_dock_top #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(600000),.FAST_REPLY_ENABLE(1)) dut(
        clk,reset_n,arm,bus_clk,dir,4'b0,data,ready,led);
    always @(posedge clk) if(host_oe && dut.data_oe) $fatal(1,"contention");
    task pulse;begin #60;bus_clk=1;#60;bus_clk=0;#60;end endtask
    task send;
        integer k;
        begin dir=0;#100;host_oe=1;
            for(k=0;k<8;k=k+1)begin host_data=q[k];pulse();end
            host_oe=0;
        end
    endtask
    task wait_ready;
        begin
            cycles=0;while(!ready && cycles<2000000)begin #10;cycles=cycles+1;end
            if(!ready)$fatal(1,"response timeout op=%h vector=%0d",q[1],count);
        end
    endtask
    // Host samples the OLD byte immediately before each rising edge.
    task read_free(input integer bytes,input integer glitch_at);
        integer k;
        begin
            wait_ready();dir=1;#100;ready_drop=-1;released_at=-1;
            for(k=0;k<bytes;k=k+1)begin
                got[k]=data;
                if(!ready && ready_drop<0)ready_drop=k;
                if(!dut.data_oe && released_at<0)released_at=k;
                bus_clk=1;#(HALF_NS);bus_clk=0;
                if(k==glitch_at)begin #(HALF_NS/2);bus_clk=1;#3;bus_clk=0;#(HALF_NS/2-3);end
                else #(HALF_NS);
            end
        end
    endtask
    initial begin
        #100;reset_n=1;#100;arm=1;#100;
        if(!$value$plusargs("vectors=%s",path))$fatal(1,"missing vectors");
        fd=$fopen(path,"r");if(!fd)$fatal(1,"cannot open vectors");count=0;
        while(!$feof(fd))begin
            n=$fscanf(fd,"%d",length);
            if(n==1)begin
                for(i=0;i<8;i=i+1)begin n=$fscanf(fd,"%h",q[i]);end
                for(i=0;i<length;i=i+1)begin n=$fscanf(fd,"%h",expected[i]);end
                send();
                if(length==2066)begin
                    read_free(length,(MODE==2)?GLITCH_AT:-1);
                    first_bad=-1;
                    for(i=0;i<length;i=i+1)if(got[i]!==expected[i] && first_bad<0)first_bad=i;
                    $display("RESULT mode=%0d half_ns=%0d glitch_at=%0d first_bad=%0d ready_drop=%0d bus_released_at=%0d",
                             MODE,HALF_NS,GLITCH_AT,first_bad,ready_drop,released_at);
                    $display("TAIL %h %h %h %h",got[length-4],got[length-3],got[length-2],got[length-1]);
                    $finish;
                end else begin
                    wait_ready();dir=1;#100;
                    for(j=0;j<length;j=j+1)begin got[j]=data;pulse();end
                    for(i=0;i<length;i=i+1)if(got[i]!==expected[i])$fatal(1,"setup vector=%0d byte=%0d",count,i);
                    dir=0;#100;
                end
                count=count+1;
            end else if(n!=-1 && !$feof(fd))$fatal(1,"invalid vector token");
        end
        $fatal(1,"no TILE vector");
    end
    initial begin #2000000000;$fatal(1,"watchdog");end
endmodule
