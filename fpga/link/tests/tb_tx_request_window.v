`timescale 1ps/1ps
// Digital request capture only: RX is deliberately slow and independent.
module tb_tx_request_window;
 parameter integer PERIOD_PS=50000,HIGH_PS=25000,SETUP_PS=25000,HOLD_PS=25000,PHASE_PS=1;
 reg clk=0,sampler=0,reset_n=0,arm=0,bus_clk=0,dir=0;
 reg [7:0] data_i=0;
 wire [7:0] data_o;wire oe,ready;
 always #9259 clk=~clk; // 18518ps approximation of 54MHz.
 always #2315 sampler=~sampler;
 GSR GSR(1'b1);
`ifdef REQUEST_FIFO_PIPE
 localparam REQUEST_PIPE=1;
`else
 localparam REQUEST_PIPE=0;
`endif
 `ifdef REQUEST_FIFO
 localparam REQUEST_FIFO=1;
`else
 localparam REQUEST_FIFO=0;
`endif
 `ifdef REQUEST_FF
 localparam REQUEST_FF=1;
`else
 localparam REQUEST_FF=0;
`endif
 link_bringup_filtered #(.REQUEST_DATA_FF(REQUEST_FF),.REQUEST_CAPTURE_FIFO(REQUEST_FIFO),.REQUEST_FIFO_PIPELINED_READ(REQUEST_PIPE),.GFX_ENABLE(2),.ALL_SCENES_ENABLE(1),.REQUEST_DATA_PIPELINE(1),
  .REPLY_ACTIVE_PIPELINE(1),.FAST_FILTER_SYNC(1),.FAST_REPLY_ENABLE(1),.CORE_CLOCK_MHZ(54),
  .TIMEOUT_CYCLES(100000)) dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready,sampler,reset_n && arm);
 reg [7:0] q[0:1289],expected[0:7],got[0:7],pre[0:7];
 integer fd,qlen,rlen,kind,n,idx,case_no=0,waits,accepted,words_ok,source_index;
 reg [2047:0] path;
 reg [15:0] crc,want;
 function [15:0] crc_byte(input [15:0] c,input [7:0] b);
  reg [15:0] v;integer k;
  begin v=c^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
 endfunction
 task slow_pulse;begin #200000;bus_clk=1;#200000;bus_clk=0;#200000;end endtask
 task await_reply;
  begin waits=0;while(!ready && waits<10000)begin @(negedge clk);waits=waits+1;end end
 endtask
 task read_reply;
  integer k;
  begin
   dir=1;#200000;
   for(k=0;k<8;k=k+1)begin got[k]=data_o;slow_pulse();end
   dir=0;#1000000;
  end
 endtask
 task initialize;
  integer k;
  begin
   reset_n=0;arm=0;dir=0;bus_clk=0;data_i=0;repeat(5)@(negedge clk);
   reset_n=1;arm=1;repeat(10)@(negedge clk);
   pre[0]=8'ha5;pre[1]=kind==3?8'h6d:8'h2b;pre[2]=0;pre[3]=2;
   pre[4]=kind==3?0:8'h42;pre[5]=0;
   crc=16'hffff;for(k=0;k<6;k=k+1)crc=crc_byte(crc,pre[k]);pre[6]=crc[7:0];pre[7]=crc[15:8];
   for(k=0;k<8;k=k+1)begin data_i=pre[k];slow_pulse();end
   await_reply();if(!ready)$fatal(1,"slow precondition timeout");read_reply();
   if(got[0]!==8'h5a || got[1]!==0 || got[2]!==0 || got[3]!==2)$fatal(1,"slow precondition failed");
  end
 endtask
 task transmit;
  integer ci,di;
  begin
   if(SETUP_PS+HOLD_PS<1 || SETUP_PS+HOLD_PS>PERIOD_PS)$fatal(1,"invalid DATA window");
   @(posedge clk);#PHASE_PS;
   fork
    begin
     #(2*PERIOD_PS);
     for(ci=0;ci<qlen;ci=ci+1)begin bus_clk=1;#(HIGH_PS);bus_clk=0;#(PERIOD_PS-HIGH_PS);end
    end
    begin
     data_i=8'h00;
     #(2*PERIOD_PS-SETUP_PS);
     for(di=0;di<qlen;di=di+1)begin
      data_i=q[di];#(SETUP_PS+HOLD_PS);data_i=q[di]^8'hff;#(PERIOD_PS-SETUP_PS-HOLD_PS);
     end
    end
   join
   #100000;
  end
 endtask
 initial begin
  if(!$value$plusargs("vectors=%s",path))$fatal(1,"vectors missing");fd=$fopen(path,"r");
  while(!$feof(fd))begin
   n=$fscanf(fd,"%d %d %d",qlen,rlen,kind);
   if(n==3)begin
    for(idx=0;idx<qlen;idx=idx+1)n=$fscanf(fd,"%h",q[idx]);
    for(idx=0;idx<rlen;idx=idx+1)n=$fscanf(fd,"%h",expected[idx]);
    initialize();transmit();await_reply();accepted=1;words_ok=1;
    if(!ready)accepted=0;
    else begin
     read_reply();for(idx=0;idx<8;idx=idx+1)if(got[idx]!==expected[idx])accepted=0;
     if(accepted && kind!=0)begin
      for(idx=0;idx<640;idx=idx+1)begin
       want={q[9+2*idx],q[8+2*idx]};
       if(kind==1 && dut.triangle.staging.words[idx]!==want)words_ok=0;
       if(kind==2 && dut.triangle.scenes_batch.staging2d.words[idx]!==want)words_ok=0;
       if(kind==3 && dut.triangle.scenes_batch.upload_staging.words[idx]!==want)words_ok=0;
      end
     end
    end
    $display("TXWINDOW,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",PERIOD_PS,HIGH_PS,SETUP_PS,HOLD_PS,PHASE_PS,kind,qlen,accepted,words_ok,waits);
    case_no=case_no+1;
   end
  end
  if(case_no!=4)$fatal(1,"expected four independent packet kinds");
  $finish;
 end
 initial begin #10000000000;$fatal(1,"TX window watchdog");end
endmodule
