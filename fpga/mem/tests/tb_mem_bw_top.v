`timescale 1ns/1ps
// mem_top integration bench: LINK byte protocol -> mem_link -> (mem_mailbox | mem_bw_port) -> shared native bus -> DDR3 IP stand-in.
// Checks bus ownership, ABI separation (MEM diagnostic 0x50..0x5C vs bandwidth 0x60..0x6F), BIST regression before/after bandwidth
// jobs, rejection rules, cancel + RECAL recovery. The IP stand-in models only the native user interface; RTL evidence only.
// Parameters: BW (mem_top.BW_ENABLE), SAMPLE (1: DDR3_Memory_Interface_Top style IP with app_burst_number, row-pad layout).
module tb_mem_bw_top;
parameter BW=1;
parameter SAMPLE=0;
parameter BWPIPE=0;   // mem_top.BW_EN_PIPE
parameter BWGATE=0;   // mem_top.BW_SHARED_GATE (needs the PIPELINE=4 BIST of the generated variants)
reg sys_clk=0; always #18.5185 sys_clk=~sys_clk;
reg reset_n=0,arm_sw=0,bus=0,dir=0; reg [7:0] di=0; wire [7:0] data; wire ready; wire [3:0] led;
assign data=dir?8'bz:di;
wire [12:0] ddr_addr; wire [2:0] ddr_bank; wire ddr_cs,ddr_ras,ddr_cas,ddr_we,ddr_ck,ddr_ck_n,ddr_cke,ddr_odt,ddr_reset_n; wire [1:0] ddr_dm;
wire [15:0] ddr_dq; wire [1:0] ddr_dqs,ddr_dqs_n;
mem_top #(.BW_ENABLE(BW),.BW_ROW_PAD(SAMPLE),.BW_EN_PIPE(BWPIPE),.BW_SHARED_GATE(BWGATE)) dut(.sys_clk(sys_clk),.reset_n(reset_n),.arm_sw(arm_sw),.bus_clk(bus),.dir(dir),.aux(4'b0),.data(data),.ready(ready),.led(led),
    .ddr_addr(ddr_addr),.ddr_bank(ddr_bank),.ddr_cs(ddr_cs),.ddr_ras(ddr_ras),.ddr_cas(ddr_cas),.ddr_we(ddr_we),.ddr_ck(ddr_ck),.ddr_ck_n(ddr_ck_n),
    .ddr_cke(ddr_cke),.ddr_odt(ddr_odt),.ddr_reset_n(ddr_reset_n),.ddr_dm(ddr_dm),.ddr_dq(ddr_dq),.ddr_dqs(ddr_dqs),.ddr_dqs_n(ddr_dqs_n));

// Shared enable stage (BW_EN_PIPE>=1): the IP-facing enables must equal the engines' own accounting strobes in every cycle.
integer gate_checked=0;
always @(negedge dut.user_clk) if(dut.user_reset_n===1'b1) begin
  gate_checked=gate_checked+1;
  if(BW!=0) begin
    if(dut.cmd_en!==(dut.b_cmd_en||dut.bw.w_cmd_en)) begin
      $display("DBG cmd_en=%b b=%b w=%b cmd_ready=%b wr_ready=%b bwbusy=%b",dut.cmd_en,dut.b_cmd_en,dut.bw.w_cmd_en,dut.cmd_ready,dut.wr_ready,dut.bw.bw_busy);
      $fatal(1,"IP cmd_en differs from the engines' strobes at %0t",$time);
    end
    if(dut.wr_en!==(dut.b_wr_en||dut.bw.w_wr_en)) $fatal(1,"IP wr_en differs from the engines' strobes at %0t",$time);
  end
end
function [15:0] crc; input [15:0] old; input [7:0] bv; reg [15:0] v; integer k;
 begin v=old^{bv,8'b0}; for(k=0;k<8;k=k+1) v=v[15]?(v<<1)^16'h1021:v<<1; crc=v; end endfunction
reg [7:0] q [0:7]; reg [7:0] r [0:7]; reg [15:0] c; integer i,n,checks=0; reg [7:0] seqid=0;
reg [7:0] st; reg [15:0] rs;
task pulse; begin #500; bus=1; #500; bus=0; end endtask
// one LINK transaction; st/rs hold the device status/result. Link-level errors (status 1/2) are returned like device statuses.
task xfer; input [7:0] code,x,y;
 begin
  dir=0; #500; q[0]=8'ha5; q[1]=code; q[2]=seqid; q[3]=2; q[4]=x; q[5]=y;
  c=16'hffff; for(i=0;i<6;i=i+1) c=crc(c,q[i]); q[6]=c[7:0]; q[7]=c[15:8];
  for(i=0;i<8;i=i+1) begin di=q[i]; pulse; end
  n=0; while(!ready&&n<200000) begin #100; n=n+1; end
  if(!ready) $fatal(1,"no reply for op %h",code);
  dir=1; #500;
  for(i=0;i<8;i=i+1) begin r[i]=data; pulse; end
  c=16'hffff; for(i=0;i<6;i=i+1) c=crc(c,r[i]);
  if(r[0]!=8'h5a||r[2]!==seqid||r[3]!=2||{r[7],r[6]}!==c) $fatal(1,"bad reply frame for op %h",code);
  st=r[1]; rs={r[5],r[4]}; dir=0; #500; seqid=seqid+1; checks=checks+1;
 end endtask
task want; input [7:0] code,x,y,ws; begin xfer(code,x,y); if(st!==ws) $fatal(1,"op %h(%0d,%0d): status %0d expected %0d",code,x,y,st,ws); end endtask
task want_v; input [7:0] code,x,y,ws; input [15:0] wv; begin want(code,x,y,ws); if(rs!==wv) $fatal(1,"op %h(%0d,%0d): result %h expected %h",code,x,y,rs,wv); end endtask
task w32; input [7:0] opl,oph; input [31:0] v; begin want(opl,v[7:0],v[15:8],0); want(oph,v[23:16],v[31:24],0); end endtask

// ---- helpers ----
task wait_ready; integer t; begin
  t=0; xfer(8'h5c,6,0);
  while(((rs&16'h3c1)!==16'h381 || (rs&16'h2)!==0) && t<2000) begin #20000; xfer(8'h5c,6,0); t=t+1; end
  if(t>=2000) $fatal(1,"MEM never became ready (flags %h)",rs);
  // bit0 calibrated, 7 guard, 8 user ready, 9 heartbeat fresh, bit1 busy must be 0 (0x381 mask above)
 end endtask
reg [15:0] w [0:63]; reg [15:0] fl;
function [31:0] wd32; input integer o; begin wd32={w[o+1],w[o]}; end endfunction
// ---- MEM diagnostic BIST (existing ABI) ----
task bist_run; input [31:0] base,count,seed; integer t; reg [31:0] job,ver,mis;
 begin
  w32(8'h51,8'h52,base); w32(8'h53,8'h54,count); w32(8'h55,8'h56,seed);
  want(8'h57,0,0,0); job=rs;
  t=0; fl=0;
  while(!(fl&4) && t<400) begin #10000; want(8'h58,0,0,0); want(8'h59,0,0,0); fl=rs; t=t+1; end
  if(t>=400) $fatal(1,"BIST did not finish");
  want(8'h59,1,0,0); if(rs!==16'h0500) $fatal(1,"BIST phase/error word %h",rs);
  want(8'h59,4,0,0); ver=rs; want(8'h59,5,0,0); ver=ver|(rs<<16);
  want(8'h59,6,0,0); mis=rs; want(8'h59,7,0,0); mis=mis|(rs<<16);
  if((fl&31)!==5||ver!==count*2||mis!==0) $fatal(1,"BIST not an exact PASS: flags %h verified %0d mismatches %0d",fl,ver,mis);
  $display("INFO BIST base=%0d count=%0d PASS (job %0d)",base,count,job);
 end endtask
// ---- bandwidth engine ----
reg [15:0] ctl16;
task bw_cfg; input [31:0] base,count,seed; input [1:0] mode; input [2:0] pat; input [4:0] rl; input [2:0] blg; input [15:0] run; input [23:0] stride; input [7:0] mw,mr;
 begin
  w32(8'h60,8'h61,base); w32(8'h62,8'h63,count); w32(8'h64,8'h65,seed);
  ctl16={3'b0,blg,rl,pat,mode};
  want_v(8'h66,ctl16[7:0],ctl16[15:8],0,ctl16);
  want(8'h67,mw,mr,0); want(8'h68,run[7:0],run[15:8],0); want(8'h69,stride[7:0],stride[15:8],0); want(8'h6a,stride[23:16],0,0);
 end endtask
task bw_wait; integer t; begin
  t=0; fl=0;
  while(!(fl&8) && t<3000) begin #10000; want(8'h6f,1,0,0); fl=rs; t=t+1; end
  if(t>=3000) $fatal(1,"BW job did not finish (flags %h)",fl);
  if(fl&4) $fatal(1,"BW busy and done");
 end endtask
task bw_snap; input [8*16:1] tag; input [31:0] base,count,seed; input [1:0] mode; input [2:0] pat; input [4:0] rl; input [2:0] blg; input [15:0] run; input [23:0] stride; input [7:0] mw,mr;
 integer j;
 begin
  want(8'h6d,0,0,0);
  for(j=0;j<62;j=j+1) begin want(8'h6e,j,0,0); w[j]=rs; end
  $write("PORTSNAP tag=%0s sample=%0d mode=%0d pat=%0d blg=%0d run=%0d stride=%0d rl=%0d mixw=%0d mixr=%0d count=%0d base=%0d seed=%0d words=",
         tag,SAMPLE,mode,pat,blg,run,stride,rl,mw,mr,count,base,seed);
  for(j=0;j<62;j=j+1) $write("%04x",w[j]);
  $write("\n");
 end endtask
task bw_job; input [8*16:1] tag; input [31:0] base,count,seed; input [1:0] mode; input [2:0] pat; input [4:0] rl; input [2:0] blg; input [15:0] run; input [23:0] stride; input [7:0] mw,mr;
 begin
  bw_cfg(base,count,seed,mode,pat,rl,blg,run,stride,mw,mr);
  want(8'h6b,0,0,0);
  bw_wait;
  bw_snap(tag,base,count,seed,mode,pat,rl,blg,run,stride,mw,mr);
  if(w[1][7:0]!==0) $fatal(1,"BW job %0s error %0d",tag,w[1][7:0]);
 end endtask

initial begin
 #200; reset_n=1; arm_sw=1;
 wait_ready;
 want_v(8'h50,0,0,0,16'h014d);
 // ---- ABI separation / link level ----
 want_v(8'h5c,8,0,0,16'h014e);
 if(BW) begin
   want_v(8'h6f,0,0,0,16'h0150); want_v(8'h6f,3,0,0,16'd62); want_v(8'h6f,4,0,0,16'd1);
   want(8'h6f,9,0,3); want(8'h6f,0,1,3);
   want(8'h6e,0,0,5);                       // READ before any snapshot
   want(8'h6d,0,0,5);                       // SNAPSHOT before any job
   want(8'h6b,0,0,5);                       // START before CFG
   want(8'h6c,0,0,5);                       // CANCEL while idle
 end else begin
   xfer(8'h6f,0,0); if(st!==2) $fatal(1,"BW opcode must be rejected by the link when BW_ENABLE=0 (status %0d)",st);
   xfer(8'h60,0,0); if(st!==2) $fatal(1,"BW opcode 0x60 must be rejected when BW_ENABLE=0");
 end
 xfer(8'h70,0,0); if(st!==2) $fatal(1,"opcode 0x70 must stay unknown");
 xfer(8'h5d,0,0); if(st!==2) $fatal(1,"opcode 0x5d must stay unknown");
 // ---- BIST regression before ----
 bist_run(0,64,32'h1234);
 if(BW) begin
  // ---- bandwidth jobs on the shared bus ----
  bw_job("seq_w",32'h100000,4096,32'hCAFE0001,0,0,23,0,1,1,1,1);
  bw_job("seq_r",32'h100000,4096,32'hCAFE0001,1,0,23,0,1,1,1,1);
  bw_job("strided_w",32'h200000,512,32'h5,0,5,23,0,16'd4,24'd1024,1,1);
  bw_job("strided_r",32'h200000,512,32'h5,1,5,23,0,16'd4,24'd1024,1,1);
  if(SAMPLE) begin
   bw_job("burst8_w",32'h300000,1024,32'h77,0,0,23,3,1,1,1,1);
   bw_job("burst8_r",32'h300000,1024,32'h77,1,0,23,3,1,1,1,1);
   bw_job("burst64_w",32'h340000,2048,32'h78,0,0,23,6,1,1,1,1);
   bw_job("burst64_r",32'h340000,2048,32'h78,1,0,23,6,1,1,1,1);
   bw_job("bstride_w",32'h380000,1024,32'h79,0,5,23,3,16'd2,24'd128,1,1);
   bw_job("bstride_r",32'h380000,1024,32'h79,1,5,23,3,16'd2,24'd128,1,1);
  end
  bw_job("mix_m",32'h3c0000,256,32'h31,2,0,23,0,1,1,3,1);
  // BIST regression after bandwidth jobs (same bus, same mailbox)
  bist_run(0,128,32'h99);
  // ---- configuration errors end as done+error 2 without a fault and without touching the bus ----
  bw_cfg(32'h100008,64,1,0,0,23,0,1,1,1,1);   // base not 16-byte aligned
  want(8'h6b,0,0,0); bw_wait; want(8'h6d,0,0,0); want(8'h6e,1,0,0); if(rs[7:0]!==2) $fatal(1,"unaligned base: error %0d",rs[7:0]);
  want(8'h6e,0,0,0); if(rs[2]) $fatal(1,"config error must not fault the engine");
  bw_job("after_cfgerr",32'h100000,64,32'h5,0,0,23,0,1,1,1,1);
  // ---- exclusion while a long job runs ----
  bw_cfg(32'h0,1048576,32'h42,0,0,23,0,1,1,1,1);
  want(8'h6b,0,0,0);
  want(8'h6b,0,0,5);                          // second START
  want(8'h60,0,0,5);                          // CFG write while busy
  want(8'h6d,0,0,5);                          // SNAPSHOT while busy
  xfer(8'h57,0,0); if(st!==5) $fatal(1,"BIST START must be refused while a bandwidth job runs (status %0d)",st);
  want(8'h6c,0,0,0);                          // CANCEL
  bw_wait;
  want(8'h6d,0,0,0); want(8'h6e,1,0,0); if(rs[7:0]!==7) $fatal(1,"cancel: error %0d",rs[7:0]);
  want(8'h6e,0,0,0); if(!rs[2]) $fatal(1,"cancel must fault the engine");
  want(8'h6b,0,0,5);                          // faulted until RECAL
  // ---- RECAL recovers both engines ----
  want(8'h5b,0,0,0);
  #200000; wait_ready;
  bw_job("after_recal",32'h100000,1024,32'h6,0,0,23,0,1,1,1,1);
  bw_job("after_recal_r",32'h100000,1024,32'h6,1,0,23,0,1,1,1,1);
  bist_run(0,64,32'h7);
 end else begin
  // BW image disabled: the BIST path alone
  bist_run(0,256,32'h55);
 end
 $display("PASS mem_top bandwidth integration BW=%0d SAMPLE=%0d BWPIPE=%0d BWGATE=%0d %0d link transactions, %0d cycles of IP enables checked",BW,SAMPLE,BWPIPE,BWGATE,checks,gate_checked);
 $finish;
end
initial begin #3000000000; $fatal(1,"global timeout"); end
endmodule
