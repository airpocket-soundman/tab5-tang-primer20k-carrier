`timescale 1ps/1ps
module tb_request_capture_fifo;
 parameter integer PHYSICAL_FF=0;
 parameter integer PIPELINED_READ=0,LOW_PS=25000,HIGH_PS=25000;
`ifdef VENDOR_FF
 GSR GSR(1'b1);
`endif
 parameter integer SYS_PHASE_PS=0;
 parameter integer CLK_SKEW_PS=0;
 reg sample_clk=0,sys_clk=0,reset_n=0,arm=0,dir=1,raw_clk=0;
 reg [7:0] data_i=0;reg byte_ready=0;
 wire byte_valid,overflow;wire [7:0] byte_data;
 wire received_clk;assign #(CLK_SKEW_PS) received_clk=raw_clk;
 request_capture_fifo #(.PHYSICAL_FF(PHYSICAL_FF),.PIPELINED_READ(PIPELINED_READ)) dut(.raw_clk(received_clk),.*);
 always #2315 sample_clk=~sample_clk;
 initial begin #(SYS_PHASE_PS);forever #9260 sys_clk=~sys_clk;end
 integer received=0,sent=0,sys_ticks=0,i,n,full_packets=0;
 reg scoring=0,stall_all=0;
 reg [7:0] expected[0:1289];reg [15:0] c,value;integer field,record;
 reg held=0;reg[7:0] held_data;
 function [15:0] crc;
  input [15:0] old;input [7:0] b;reg [15:0] v;integer k;
  begin v=old^{b,8'b0};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc=v;end
 endfunction
 always @(posedge sys_clk)begin
  if(held && byte_valid && byte_data!==held_data)$fatal(1,"data changed under backpressure");
  held=byte_valid && !byte_ready;held_data=byte_data;
  if(byte_valid && byte_ready && scoring)begin
   if(received>=1290 || byte_data!==expected[received])$fatal(1,"byte%0d got%02x expected%02x",received,byte_data,expected[received]);
   received=received+1;
  end
  sys_ticks=sys_ticks+1;
  // Approximate a parser pause plus occasional consumer latency; mean
  // service capacity remains above20MB/s. No retries or dropped bytes.
  byte_ready<=!stall_all && (sys_ticks%11!=0) && !(scoring && received==8 && sys_ticks%3!=0);
 end
 task wait_quiet;
  input integer ticks;
  begin repeat(ticks)@(negedge sys_clk);end
 endtask
 task prepare_packet;
  begin
   expected[0]=8'ha5;expected[1]=8'hc1;expected[2]=8'h57;expected[3]=2;expected[4]=64;expected[5]=1;
   c=16'hffff;for(n=0;n<6;n=n+1)c=crc(c,expected[n]);expected[6]=c[7:0];expected[7]=c[15:8];
   // Legal legacy TRI_BATCH64 records, with a bound payload trailer CRC.
   for(record=0;record<64;record=record+1)for(field=0;field<10;field=field+1)begin
    case(field)
     0,1,3,4:value=0;2,5:value=512;6,7,8:value=record*100+1;
     default:value=(record*197)^16'ha65a;
    endcase
    expected[8+record*20+field*2]=value[7:0];expected[9+record*20+field*2]=value[15:8];
   end
   c=16'hffff;for(n=0;n<6;n=n+1)c=crc(c,expected[n]);for(n=8;n<1288;n=n+1)c=crc(c,expected[n]);
   expected[1288]=c[7:0];expected[1289]=c[15:8];
  end
 endtask
 task send_bytes;
  input integer count;
  begin
   for(i=0;i<count;i=i+1)begin data_i=expected[i];#(LOW_PS);raw_clk=1;#(HIGH_PS);raw_clk=0;sent=sent+1;end
  end
 endtask
 task complete_packet;
  integer timeout;
  begin
   scoring=1;received=0;sent=0;raw_clk=0;#500000;
   send_bytes(1290);timeout=0;
   while(received<1290 && timeout<10000)begin wait_quiet(1);timeout=timeout+1;end
   if(received!=1290 || overflow)$fatal(1,"packet incomplete received%0d overflow%0d",received,overflow);
   wait_quiet(12);if(byte_valid)$fatal(1,"extra byte after packet");scoring=0;full_packets=full_packets+1;
  end
 endtask
 task assert_empty;
  begin wait_quiet(20);if(byte_valid)$fatal(1,"stale/fake byte after boundary");end
 endtask
 initial begin
  prepare_packet();#100000;reset_n=1;arm=1;dir=0;#500000;
  complete_packet();
  // Aborted request and reply clocks cannot contaminate the next request.
  scoring=0;send_bytes(100);dir=1;raw_clk=0;#1;if(byte_valid)$fatal(1,"DIR did not kill valid");
  for(n=0;n<20;n=n+1)begin #(LOW_PS);raw_clk=1;#(HIGH_PS);raw_clk=0;end
  raw_clk=1;wait_quiet(10);dir=0;assert_empty();raw_clk=0;#500000;complete_packet();
  // ARM drop while bytes remain queued; rearm with a stopped HIGH clock.
  send_bytes(100);arm=0;raw_clk=1;#1;if(byte_valid)$fatal(1,"ARM did not kill valid");
  wait_quiet(10);arm=1;assert_empty();raw_clk=0;#500000;complete_packet();
  // Global reset with rawCLK already HIGH must not invent a first byte.
  send_bytes(100);reset_n=0;raw_clk=1;#1;if(byte_valid)$fatal(1,"reset did not kill valid");
  wait_quiet(10);reset_n=1;assert_empty();raw_clk=0;#500000;complete_packet();
  // Overflow is sticky/failclosed, not silently cleared by a DIR round trip.
  stall_all=1;wait_quiet(2);send_bytes(40);wait_quiet(8);
  if(!overflow || byte_valid)$fatal(1,"overflow did not close output");
  dir=1;wait_quiet(4);dir=0;wait_quiet(8);stall_all=0;wait_quiet(20);
  if(!overflow || byte_valid)$fatal(1,"DIR cleared a sticky overflow");
  arm=0;wait_quiet(4);arm=1;raw_clk=0;#500000;
  if(overflow)$fatal(1,"explicit rearm failed to clear overflow");
  complete_packet();
  $display("REQUEST FIFO PASS: SYSphase%0dps CLKskew%0dps packets%0d exactbytes%0d period%0dps pipe%0d, stalled parser, DIR/ARM/reset, stoppedCLK, overflow/rearm",SYS_PHASE_PS,CLK_SKEW_PS,full_packets,full_packets*1290,LOW_PS+HIGH_PS,PIPELINED_READ);
  $finish;
 end
 initial begin #1000000000;$fatal(1,"watchdog");end
endmodule
