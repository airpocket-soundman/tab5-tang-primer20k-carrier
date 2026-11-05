`timescale 1ns/1ps
// MEMV1 full-path bench: host BFM (LINK byte protocol at the SYS side) -> memv1_sys -> bridge CDC (27MHz ->
// 99.56MHz) -> mem_adapter -> native-interface model of the Gowin 1:4/BL8 controller IP (independent
// stalls, read latency, byte masks, address decoded back from rank/bank/row/column). Replays the reference
// model vectors (memv1_model.py), then hand-written cases: cancel, timeout, calibration loss, reset in flight,
// stale completion, BIST coexistence/BUSY. Not a DRAM/hardware proof.
module tb_mem_v1_core;
parameter FAST_REPLY_ENABLE=0;
parameter TX_NEG_PREAMBLE=0;
parameter REPLY_PHASE_TICKS=0;
parameter real RX_HALF=150.0,TX_HALF=150.0,SYS_PHASE=0.0,DATA_DELAY=0.0,SAMPLE_OFFSET=0.0;
parameter QUICK=0;
parameter VEC_DEFAULT="memv1_vectors.hex";
reg sys_clk=0,user_clk=0;
initial begin #SYS_PHASE;forever #18.5185 sys_clk=~sys_clk;end
reg reply_sample_reset=1;
reg reply_sample_clk=0;always #2.314815 reply_sample_clk=~reply_sample_clk;
always #5.0219 user_clk=~user_clk;
reg reset_n=0,arm=1,bus=0,dir=0,drive=0;reg[7:0] di=0;wire[7:0] data;
assign data=drive?di:8'bz;
wire [7:0] sampled_data;assign #(DATA_DELAY) sampled_data=data;
wire ready;wire[3:0] led;wire controller_reset_n;
wire[2:0] cmd;wire cmd_en;wire[26:0] address;wire[127:0] wr_data;wire wr_en,wr_end;wire[15:0] mask;
reg cmd_ready=0,wr_ready=0,rd_valid=0,rd_end=1;reg[127:0] rd_data=0;
reg calibrated=0,cal_override=0;
mem_v1_core #(.FAST_REPLY_ENABLE(FAST_REPLY_ENABLE),.REPLY_PHASE_TICKS(REPLY_PHASE_TICKS),.RESET_HOLD_INIT(16'd40),.RECAL_HOLD(16'd40),.LINK_TIMEOUT(20000000),.DEADLINE(20000000),
 .ADAPTER_TIMEOUT(3000),.ADAPTER_SETTLE(4),.BIST_SETTLE(4),.CAL_GUARD(16),.MAILBOX_DEADLINE(20000000)) dut(
 sys_clk,reset_n,arm,bus,dir,4'b0,data,ready,led,
 1'b1,user_clk,1'b0,calibrated,controller_reset_n,
 cmd,cmd_en,address,cmd_ready,wr_data,wr_en,wr_end,mask,wr_ready,rd_data,rd_valid,rd_end,reply_sample_clk,reset_n&&reply_sample_reset);
// ---- IP calibration emulation ----
integer cal_cnt=0;
always @(posedge user_clk)begin
 if(!controller_reset_n)begin cal_cnt<=0;calibrated<=0;end
 else if(cal_cnt<150)begin cal_cnt<=cal_cnt+1;calibrated<=0;end
 else calibrated<=!cal_override;
end
// ---- native memory model ----
reg[127:0] mem[0:65535];reg[31:0] mtag[0:65535];reg mval[0:65535];
integer ii;initial for(ii=0;ii<65536;ii=ii+1)mval[ii]=0;
integer mode=0; // 0 random stalls, 1 slow (one paired ready per slow_period), 2 hang, 3 always ready
integer slow_period=2000,slow_cnt=0,rtick=0;
integer nwrites=0,nreads=0,nbad=0;
reg pc=0,pd=0;reg[26:0] saved_addr=0;reg[127:0] saved_data=0;reg[15:0] saved_mask=0;
reg pr=0;integer rdelay=0;reg[26:0] raddr=0;
function [31:0] decode;input[26:0] a;reg[25:0] lw;begin lw={a[22:10],a[26:24],a[9:0]};decode={5'b0,lw,1'b0};end endfunction
reg[31:0] ba;integer idx,bb;
always @(negedge user_clk)begin
 rtick=rtick+1;rd_valid=0;rd_end=1;
 case(mode)
 0:begin cmd_ready=($random&3)!=0;wr_ready=($random&3)!=0;end
 1:begin if(slow_cnt==0)begin cmd_ready=1;wr_ready=1;slow_cnt=slow_period;end else begin cmd_ready=0;wr_ready=0;slow_cnt=slow_cnt-1;end end
 2:begin cmd_ready=0;wr_ready=0;end
 default:begin cmd_ready=1;wr_ready=1;end
 endcase
 if(pr)begin if(rdelay==0)begin
  ba=decode(raddr);idx=ba[19:4];
  if(!mval[idx]||mtag[idx]!==ba)begin nbad=nbad+1;$display("READ of unwritten/aliased native addr %h byte %h",raddr,ba);end
  rd_data=mem[idx];rd_valid=1;pr=0;nreads=nreads+1;
 end else rdelay=rdelay-1;end
end
always @(posedge user_clk) if(controller_reset_n)begin
 if(cmd_en&&!cmd_ready)begin nbad=nbad+1;$display("cmd_en without ready");end
 if(wr_en&&!wr_ready)begin nbad=nbad+1;$display("wr_en without ready");end
 if(cmd_en&&cmd_ready)begin
  if(cmd==0)begin pc=1;saved_addr=address;end
  else begin if(pr)begin nbad=nbad+1;$display("multiple outstanding reads");end pr=1;raddr=address;rdelay=5;end
 end
 if(wr_en&&wr_ready)begin pd=1;saved_data=wr_data;saved_mask=mask;if(!wr_end)begin nbad=nbad+1;$display("wr_end missing");end end
 if(pc&&pd)begin
  ba=decode(saved_addr);idx=ba[19:4];
  if(!mval[idx])mem[idx]=0;
  for(bb=0;bb<16;bb=bb+1)if(!saved_mask[bb])mem[idx][bb*8+:8]=saved_data[bb*8+:8];
  mtag[idx]=ba;mval[idx]=1;pc=0;pd=0;nwrites=nwrites+1;
 end
end else begin pc=0;pd=0;pr=0;end
// ---- host BFM ----
localparam HT=150;
reg[7:0] qb[0:4199],rb[0:4199],ex[0:4199];
task pulse;begin #TX_HALF bus=1;#TX_HALF bus=0;end endtask
task receive_byte;output [7:0] b;begin #RX_HALF;bus=1;#SAMPLE_OFFSET;b=sampled_data;#(RX_HALF-SAMPLE_OFFSET);bus=0;end endtask
task send_byte;input[7:0] b;begin
 if(TX_NEG_PREAMBLE)begin #TX_HALF;bus=1;di=b;#TX_HALF;bus=0;end
 else begin di=b;pulse;end
end endtask
integer checks=0,i,n,k;reg[7:0] last_status;reg[15:0] last_r;
// Sends qn bytes, waits for READY, reads rn bytes into rb. Returns without checking contents.
task xchg;input integer qn,rn;
begin
 dir=0;drive=1;if(TX_NEG_PREAMBLE)di=0;#300;
 for(i=0;i<qn;i=i+1)send_byte(qb[i]);
 if(TX_NEG_PREAMBLE)begin pulse;#2000;end // Trailing idle edge and actual driver last-CRC hold.
 drive=0;
 n=0;while(!ready&&n<200000)begin #100;n=n+1;end
 if(!ready)begin $display("FAIL no reply (qn=%0d)",qn);$fatal(1,"no reply");end
 dir=1;#300;
 if(data===8'hxx)begin end
 for(i=0;i<rn;i=i+1)begin receive_byte(rb[i]);end
 #300;
 if(ready)begin $display("FAIL reply longer than expected");$fatal(1,"long reply");end
 dir=0;#300;
 if(TX_NEG_PREAMBLE&&(dut.link.rx_cnt!==0||dut.link.ext_rx!==0))$fatal(1,"partial request survived DIR roundtrip");
 last_status=rb[1];last_r={rb[5],rb[4]};
end endtask
task compare;input integer rn;input integer id;
begin
 for(i=0;i<rn;i=i+1)if(rb[i]!==ex[i])begin
  $display("FAIL record %0d byte %0d got %h want %h",id,i,rb[i],ex[i]);$fatal(1,"mismatch");end
 checks=checks+1;
end endtask
// helpers building small frames with the same bitwise CRC
function[15:0] crc16;input[15:0] old;input[7:0] b;reg[15:0] v;integer kk;
begin v=old^{b,8'b0};for(kk=0;kk<8;kk=kk+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc16=v;end endfunction
reg[15:0] fc;
task mkframe;input integer at;input[7:0] op,seq,a,b;integer kk;
begin qb[at+0]=8'ha5;qb[at+1]=op;qb[at+2]=seq;qb[at+3]=2;qb[at+4]=a;qb[at+5]=b;
 fc=16'hffff;for(kk=0;kk<6;kk=kk+1)fc=crc16(fc,qb[at+kk]);qb[at+6]=fc[7:0];qb[at+7]=fc[15:8];end endtask
reg[7:0] seqn=8'h40;
task lcmd;input[7:0] op,a,b;
begin seqn=seqn+1;mkframe(0,op,seqn,a,b);xchg(8,8);
 if(rb[0]!=8'h5a||rb[2]!==seqn||rb[3]!=2)$fatal(1,"small reply header");
 fc=16'hffff;for(k=0;k<6;k=k+1)fc=crc16(fc,rb[k]);
 if({rb[7],rb[6]}!==fc)$fatal(1,"small reply crc");
 last_status=rb[1];last_r={rb[5],rb[4]};end endtask
task status_word;input[7:0] w;begin lcmd(8'h61,w,0);if(last_status!=0)$fatal(1,"status word %0d st=%0d",w,last_status);end endtask
// 32-bit CRC reference (bitwise, independent of memv1_crc32b)
function[31:0] crc32_byte;input[31:0] c;input[7:0] d;reg[31:0] v;integer kk;
begin v=c^{24'b0,d};for(kk=0;kk<8;kk=kk+1)v=v[0]?(v>>1)^32'hedb88320:(v>>1);crc32_byte=v;end endfunction
// build a WR request into qb (returns length in qlen); payload pattern from seed
integer qlen;reg[31:0] c32;reg[31:0] lfsr;
task mkwr;input[7:0] seq;input integer beats;input[31:0] addr;input[31:0] pseed;
integer kk;reg[7:0] pb;
begin
 mkframe(0,8'h63,seq,beats[7:0],beats>>8);
 qb[8]=addr[7:0];qb[9]=addr[15:8];qb[10]=addr[23:16];qb[11]=addr[31:24];
 lfsr=pseed;c32=32'hffffffff;
 for(kk=0;kk<beats*16;kk=kk+1)begin lfsr=lfsr*32'd1664525+32'd1013904223;pb=lfsr[23:16];qb[16+kk]=pb;c32=crc32_byte(c32,pb);end
 c32=~c32;
 qb[12]=c32[7:0];qb[13]=c32[15:8];qb[14]=c32[23:16];qb[15]=c32[31:24];
 fc=16'hffff;for(kk=0;kk<6;kk=kk+1)fc=crc16(fc,qb[kk]);
 for(kk=8;kk<16+beats*16;kk=kk+1)fc=crc16(fc,qb[kk]);
 qb[16+beats*16]=fc[7:0];qb[17+beats*16]=fc[15:8];qlen=18+beats*16;
end endtask
task mkrd;input[7:0] op,seq;input integer beats;input[31:0] addr;input[31:0] arg;
integer kk;
begin
 mkframe(0,op,seq,beats[7:0],beats>>8);
 qb[8]=addr[7:0];qb[9]=addr[15:8];qb[10]=addr[23:16];qb[11]=addr[31:24];
 qb[12]=arg[7:0];qb[13]=arg[15:8];qb[14]=arg[23:16];qb[15]=arg[31:24];
 fc=16'hffff;for(kk=0;kk<6;kk=kk+1)fc=crc16(fc,qb[kk]);
 for(kk=8;kk<16;kk=kk+1)fc=crc16(fc,qb[kk]);
 qb[16]=fc[7:0];qb[17]=fc[15:8];qlen=18;
end endtask
// compare a RD reply payload against the pattern of mkwr(pseed) (beats long)
task check_rd;input integer beats;input[31:0] pseed;
integer kk;reg[7:0] pb;reg[15:0] tc;
begin
 if(rb[0]!=8'h5a||rb[1]!=0)$fatal(1,"RD status %0d",rb[1]);
 lfsr=pseed;tc=16'hffff;for(kk=0;kk<6;kk=kk+1)tc=crc16(tc,rb[kk]);
 for(kk=0;kk<beats*16;kk=kk+1)begin lfsr=lfsr*32'd1664525+32'd1013904223;pb=lfsr[23:16];
  if(rb[8+kk]!==pb)begin $display("FAIL RD data byte %0d got %h want %h",kk,rb[8+kk],pb);$fatal(1,"rd data");end
  tc=crc16(tc,rb[8+kk]);end
 if({rb[9+beats*16],rb[8+beats*16]}!==tc)$fatal(1,"RD trailer");
 checks=checks+1;
end endtask
reg[7:0] vec[0:262143];
integer vp,lq,lr,vid,vdone;
reg[1023:0] vecpath;
integer nw0,nw,gen0,gen1,tries;
reg[31:0] s1,s2;reg[7:0] b1,b2;reg[15:0] tc;
task run_vectors;
begin
 vp=0;vid=0;vdone=0;
 while(!vdone)begin
  lq={vec[vp+1],vec[vp]};lr={vec[vp+3],vec[vp+2]};
  if(lq==0)vdone=1;
  else begin
   for(i=0;i<lq;i=i+1)qb[i]=vec[vp+4+i];
   for(i=0;i<lr;i=i+1)ex[i]=vec[vp+4+lq+i];
   xchg(lq,lr);compare(lr,vid);
   vp=vp+4+lq+lr;vid=vid+1;
  end
 end
end endtask
// send a frame without waiting for the reply (host keeps DIR=0)
task send_only;input integer qn;
begin dir=0;drive=1;#300;for(i=0;i<qn;i=i+1)send_byte(qb[i]);drive=0;end endtask
task read_reply8;
begin
 n=0;while(!ready&&n<200000)begin #100;n=n+1;end
 if(!ready)$fatal(1,"no reply");
 dir=1;#300;for(i=0;i<8;i=i+1)begin receive_byte(rb[i]);end
 #300;if(ready)$fatal(1,"reply too long");dir=0;#300;
 last_status=rb[1];last_r={rb[5],rb[4]};
end endtask
task wait_alive;
begin n=0;while(!(calibrated&&dut.link.cal_s[1]&&dut.link.urn_s[1])&&n<200000)begin #100;n=n+1;end
 if(n>=200000)$fatal(1,"not alive");#3000;end endtask
task expect_st;input[7:0] want;input integer id;
begin if(last_status!==want)begin $display("FAIL case %0d status %0d want %0d",id,last_status,want);$fatal(1,"status");end checks=checks+1;end endtask
initial begin
 if(!$value$plusargs("VEC=%s",vecpath))vecpath=VEC_DEFAULT;
 $readmemh(vecpath,vec);
 #500;reset_n=1;
 wait_alive;
 // ---- 1. reference-model vectors (random backpressure) ----
 mode=0;vid=0;if(QUICK!=2)run_vectors;
 if(QUICK)begin
  // Maximum request and response, full 4KiB payload, high-entropy pattern.
  mode=3;mkwr(8'h31,256,32'h100000,32'h314159);xchg(qlen,8);expect_st(0,100);
  mkrd(8'h62,8'h32,256,32'h100000,0);xchg(qlen,4106);check_rd(256,32'h314159);
  if(TX_NEG_PREAMBLE)begin
   reg [31:0] saved_c32;saved_c32=c32;
   // Exactly one physical dummy for one DMA burst: tagged WR4KiB + tagged CANCEL.
   // No extra dummy/idle pulse is inserted between the two logical frames.
   mode=1;slow_period=2000;slow_cnt=0;mkwr(8'h3b,256,32'h110000,32'habcdef);
   mkframe(0,8'he3,8'h3b,0,1);fc=16'hffff;
   for(k=0;k<6;k=k+1)fc=crc16(fc,qb[k]);for(k=8;k<qlen-2;k=k+1)fc=crc16(fc,qb[k]);
   qb[qlen-2]=fc[7:0];qb[qlen-1]=fc[15:8];mkframe(qlen,8'he7,8'h3c,0,0);
   xchg(qlen+8,16);for(k=0;k<8;k=k+1)if(rb[k]!==8'hc3)$fatal(1,"cancel prefix");
   for(k=0;k<8;k=k+1)rb[k]=rb[k+8];last_status=rb[1];last_r={rb[5],rb[4]};
   expect_st(0,108);if(rb[2]!==8'h3c||last_r!==1)$fatal(1,"combined CANCEL not acknowledged");
   fc=16'hffff;for(k=0;k<6;k=k+1)fc=crc16(fc,rb[k]);if({rb[7],rb[6]}!==fc)$fatal(1,"cancel crc");
   mode=3;lcmd(8'h60,0,0);expect_st(0,109);c32=saved_c32;
  end
  // Tagged full reply: training prefix and same bound payload CRC.
  mkrd(8'he2,8'h33,256,32'h100000,0);xchg(qlen,4114);
  for(k=0;k<8;k=k+1)if(rb[k]!==8'hc3)$fatal(1,"tag prefix");
  for(k=0;k<4106;k=k+1)rb[k]=rb[k+8];check_rd(256,32'h314159);
  // CRC32 extended response and nonzero status header.
  mkrd(8'h66,8'h34,256,32'h100000,0);xchg(qlen,14);expect_st(0,101);
  if({rb[11],rb[10],rb[9],rb[8]}!==c32)$fatal(1,"crc32 result");
  tc=16'hffff;for(k=0;k<6;k=k+1)tc=crc16(tc,rb[k]);
  for(k=8;k<12;k=k+1)tc=crc16(tc,rb[k]);if({rb[13],rb[12]}!==tc)$fatal(1,"crc32 trailer");
  mkframe(0,8'h60,8'h35,0,1);xchg(8,8);expect_st(3,102);
  // A stopped clock preserves the current response; DIR abort releases OE.
  mkrd(8'h62,8'h36,256,32'h100000,0);send_only(qlen);wait(ready);dir=1;#300;
  for(k=0;k<4;k=k+1)receive_byte(rb[k]);#2000;
  if(!ready)$fatal(1,"stopped clock lost response");
  dir=0;#1;if(data!==8'bz)$fatal(1,"DIR did not release bus");#500;
  if(ready)$fatal(1,"DIR abort kept ready");lcmd(8'h60,0,0);expect_st(0,103);
  // ARM/reset must kill OE/READY without another reply clock edge.
  mkrd(8'h62,8'h37,256,32'h100000,0);send_only(qlen);wait(ready);dir=1;#300;
  receive_byte(rb[0]);arm=0;#1;if(ready||data!==8'bz)$fatal(1,"ARM failed immediate kill");
  dir=0;#2000;arm=1;wait_alive;lcmd(8'h60,0,0);expect_st(0,104);
  // Calibration loss after READY invalidates even an already prepared reply.
  mkrd(8'h62,8'h38,256,32'h100000,0);send_only(qlen);wait(ready);dir=1;#300;
  receive_byte(rb[0]);cal_override=1;#500;
  if(ready||data!==8'bz)$fatal(1,"generation loss did not abort reply");
  dir=0;cal_override=0;wait_alive;lcmd(8'h60,0,0);expect_st(0,105);
  // Sampler lock/reset loss must kill OE without bus clocks, and recover.
  mkrd(8'h62,8'h39,256,32'h100000,0);send_only(qlen);wait(ready);dir=1;#300;
  receive_byte(rb[0]);reply_sample_reset=0;#1;
  if(ready||data!==8'bz)$fatal(1,"sampler reset did not kill OE");
  dir=0;#500;reply_sample_reset=1;#500;lcmd(8'h60,0,0);expect_st(0,106);
  // Sub-SYS lock pulse must stay latched through the next SYS edge.
  mkrd(8'h62,8'h3a,256,32'h100000,0);send_only(qlen);wait(ready);dir=1;#300;
  receive_byte(rb[0]);@(negedge sys_clk);#1;reply_sample_reset=0;#1;reply_sample_reset=1;#1;
  if(ready||data!==8'bz)$fatal(1,"short sampler reset reoffered old reply");
  #200;if(ready)$fatal(1,"short sampler fault not retained");
  dir=0;#500;lcmd(8'h60,0,0);expect_st(0,107);
  $display("PASS memv1 fast fullpath RXhalf=%0f TXhalf=%0f SYSphase=%0f checks=%0d vectors=%0d",RX_HALF,TX_HALF,SYS_PHASE,checks,vid);$finish;
 end
 // STATUS word 7: raw signals while running: pll_lock, controller_reset_n, !ip_user_reset, user_reset_n, calibrated, reset_hold==0, epoch, USER clock alive
 status_word(7);if(last_r!==16'h01bb&&last_r!==16'h01fb)$fatal(1,"diag word %h",last_r);checks=checks+1;
 // ---- 2. cancel in the middle of a slow write ----
 mode=3;mkwr(8'h70,64,32'h80000,32'h1111);xchg(qlen,8);if(rb[1]!=0)$fatal(1,"old pattern write");
 nw0=nwrites;mode=1;slow_period=2000;slow_cnt=0;
 mkwr(8'h71,64,32'h80000,32'h2222);send_only(qlen);#60000;
 mkframe(0,8'h67,8'h72,0,0);send_only(8);read_reply8;
 mode=3;nw=nwrites-nw0;
 if(rb[2]!=8'h72||last_status!=0||last_r!=16'd1)$fatal(1,"cancel reply st=%0d r=%0d",last_status,last_r);
 if(nw<=0||nw>=64)$fatal(1,"cancel written beats %0d",nw);
 status_word(0);if(!(last_r&16)||(last_r&4))$fatal(1,"status flags after cancel %h",last_r);
 status_word(4);if(last_r!=16'h0000)$fatal(1,"undef addr lo");status_word(5);if(last_r!=16'h0008)$fatal(1,"undef addr hi %h",last_r);
 status_word(6);if(last_r!==nw)$fatal(1,"undef beats %0d vs %0d",last_r,nw);
 status_word(2);if(last_r!=16'd8)$fatal(1,"last status");
 mkrd(8'h62,8'h73,64,32'h80000,0);xchg(qlen,8+1024+2);
 if(rb[1]!=0)$fatal(1,"RD after cancel");
 s1=32'h1111;s2=32'h2222;tc=16'hffff;for(k=0;k<6;k=k+1)tc=crc16(tc,rb[k]);
 for(k=0;k<1024;k=k+1)begin s1=s1*32'd1664525+32'd1013904223;s2=s2*32'd1664525+32'd1013904223;
  b1=s1[23:16];b2=s2[23:16];
  if(rb[8+k]!==((k<16*nw)?b2:b1))$fatal(1,"post-cancel content byte %0d (nw=%0d)",k,nw);
  tc=crc16(tc,rb[8+k]);end
 if({rb[1033],rb[1032]}!==tc)$fatal(1,"post-cancel trailer");checks=checks+1;
 // ---- 3. DDR no-progress timeout ----
 mode=2;mkwr(8'h74,1,32'h90000,32'h3);xchg(qlen,8);expect_st(4,3);
 mode=3;status_word(2);if(last_r!=16'd4)$fatal(1,"last status 4");
 status_word(0);if(!(last_r&16))$fatal(1,"undef flag after timeout");
 mkwr(8'h75,2,32'h91000,32'h4);xchg(qlen,8);expect_st(0,4);mkrd(8'h62,8'h76,2,32'h91000,0);xchg(qlen,8+32+2);check_rd(2,32'h4);
 // ---- 4. calibration loss in flight -> STALE; late completion absorbed ----
 status_word(1);gen0=last_r;
 mode=1;slow_cnt=0;mkwr(8'h77,8,32'hA0000,32'h5);send_only(qlen);#30000;
 cal_override=1;#2000;cal_override=0;read_reply8;expect_st(10,5);
 mode=3;wait_alive;
 status_word(1);gen1=last_r;if(gen1!==gen0+1)$fatal(1,"generation %0d -> %0d",gen0,gen1);
 status_word(0);if(last_r&4)$fatal(1,"inflight stuck after STALE");
 mkwr(8'h78,2,32'hA1000,32'h6);xchg(qlen,8);expect_st(0,6);mkrd(8'h62,8'h79,2,32'hA1000,0);xchg(qlen,8+32+2);check_rd(2,32'h6);
 // ---- 5. spurious/stale completion while a command runs is ignored ----
 nw0=nwrites;mode=1;slow_cnt=0;slow_period=500;
 mkwr(8'h7a,4,32'hB0000,32'h7);send_only(qlen);#8000;
 dut.bridge.done_t=~dut.bridge.done_t;read_reply8;expect_st(0,7);
 mode=3;if(nwrites-nw0!=4)$fatal(1,"stale completion test writes %0d",nwrites-nw0);
 mkrd(8'h62,8'h7b,4,32'hB0000,0);xchg(qlen,8+64+2);check_rd(4,32'h7);
 // ---- 6. reset in flight ----
 status_word(1);gen0=last_r;
 mode=1;slow_period=2000;slow_cnt=0;mkwr(8'h7c,8,32'hC0000,32'h8);send_only(qlen);#30000;
 reset_n=0;#2000;if(ready)$fatal(1,"ready during reset");reset_n=1;dir=0;drive=0;#1000;
 mode=3;wait_alive;
 status_word(1);gen1=last_r;if(gen1===gen0)$fatal(1,"generation unchanged by reset");
 status_word(3);if(last_r!=0)$fatal(1,"op count after reset %0d",last_r);
 mkwr(8'h7d,3,32'hC1000,32'h9);xchg(qlen,8);expect_st(0,8);mkrd(8'h62,8'h7e,3,32'hC1000,0);xchg(qlen,8+48+2);check_rd(3,32'h9);
 // ---- 7. BIST coexistence: BUSY while it runs, adapter works afterwards ----
 mode=1;slow_period=300;slow_cnt=0;
 lcmd(8'h51,0,0);lcmd(8'h52,8'h10,0);lcmd(8'h53,8'd64,0);lcmd(8'h54,0,0);lcmd(8'h55,8'h34,8'h12);lcmd(8'h56,0,0);
 tries=0;last_status=5;
 while(last_status!=0&&tries<200)begin lcmd(8'h57,0,0);if(last_status!=0)#20000;tries=tries+1;end
 expect_st(0,9);
 mkrd(8'h62,8'h7f,1,32'hC1000,0);xchg(qlen,8);expect_st(6,10);
 status_word(0);if(!(last_r&8))$fatal(1,"bist_active flag");
 mode=3;tries=0;last_r=0;
 while(!(last_r&4)&&tries<400)begin lcmd(8'h58,0,0);lcmd(8'h59,0,0);if(!(last_r&4))#20000;tries=tries+1;end
 if(!(last_r&4)||(last_r&8)||(last_r&16))$fatal(1,"BIST result flags %h",last_r);checks=checks+1;
 mkwr(8'h7c,5,32'hD0000,32'ha);xchg(qlen,8);expect_st(0,11);mkrd(8'h62,8'h7d,5,32'hD0000,0);xchg(qlen,8+80+2);check_rd(5,32'ha);
 if(nbad!=0)$fatal(1,"native model reported %0d violations",nbad);
 $display("PASS mem_v1_core %0d checks, %0d vector records, %0d native writes, %0d reads: vectors, cancel, timeout, calibration-loss STALE, stale completion, reset in flight, BIST coexistence",checks,vid,nwrites,nreads);
 $finish;
end
initial begin #400000000;$fatal(1,"bench deadline");end
endmodule
