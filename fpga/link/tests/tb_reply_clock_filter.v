`timescale 1ps/1ps
module tb_reply_clock_filter;
    parameter integer PERIOD_PS=25000;
    parameter integer HIGH_PS=12500;
    parameter integer PHASE_PS=0;
    parameter integer NOISE_MODE=0;
    parameter integer DIV_INTEGER=0;
    parameter integer DIV_NUMERATOR=0;
    parameter integer DIV_DENOMINATOR=1;
    reg clk=0,reset_n=0,raw=0,active=0;
    wire clean,fault;
    integer rises=0,edges=0,i,accumulator=0,divider,period_now,high_now;
    time last_clean=0,high_start=0,last_raw=0;
    time min_latency=999999,max_latency=0,latency;
    always #2315 clk=~clk; //4630ps approximates216MHz; exact value recorded.
    reply_clock_filter dut(clk,reset_n,raw,active,clean,fault);
    always @(posedge raw)begin edges=edges+1;last_raw=$time;end
    always @(posedge clean)begin
        if(last_clean && $time-last_clean<23150)$fatal(1,"cooldown offbyone");
        rises=rises+1;last_clean=$time;high_start=$time;
        latency=$time-last_raw;
        if(latency<min_latency)min_latency=latency;
        if(latency>max_latency)max_latency=latency;
    end
    always @(negedge clean)if(reset_n && high_start && $time-high_start<9260)$fatal(1,"short clean HIGH");
    initial begin
        #20000;reset_n=1;active=1;#(PHASE_PS+50000);
        if(NOISE_MODE==1)begin
            //A single sub-tick pulse can produce at most one sampled HIGH.
            raw=1;#1000;raw=0;#50000;
            if(rises!=0 || fault)$fatal(1,"short pulse not rejected");
        end
        if(NOISE_MODE==2)begin
            //Two2sample-high/low excursions within5ticks must fault closed.
            @(negedge clk);raw=1;#9260;raw=0;#9260;raw=1;#9260;raw=0;#50000;
            if(!fault)$fatal(1,"oversized short-spacing event hidden");
        end else begin
            for(i=0;i<200;i=i+1)begin
                period_now=PERIOD_PS;high_now=HIGH_PS;
                if(DIV_INTEGER)begin
                    accumulator=accumulator+DIV_NUMERATOR;divider=DIV_INTEGER;
                    if(accumulator>=DIV_DENOMINATOR)begin accumulator=accumulator-DIV_DENOMINATOR;divider=divider+1;end
                    period_now=6250*divider;high_now=6250*(divider/2);
                end
                raw=1;#(high_now);raw=0;#(period_now-high_now);
            end
            #50000;
            if(rises!=200 || fault)$fatal(1,"clean count expected200 got%0d fault%0d",rises,fault);
        end
        //With raw clock stopped, reset immediately suppresses the clean clock.
        reset_n=0;#1;if(clean || fault)$fatal(1,"asynchronous reset failed");
        $display("FILTER,%0d,%0d,%0d,%0d,%0d,%0d,%0d",PERIOD_PS,HIGH_PS,PHASE_PS,NOISE_MODE,rises,min_latency,max_latency);
        $finish;
    end
endmodule
