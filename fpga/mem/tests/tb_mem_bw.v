`timescale 1ns/1ps
// Simulation of mem_bw against an independent memory shim (ideal and stalling). Not hardware evidence.
module tb_mem_bw;
parameter PAIRED=1;
parameter ROWPAD=0;
reg clk=0; always #5 clk=~clk;
reg rst=0,cal=1,start=0,cancel=0;
reg [1:0] mode=0; reg [2:0] pat=0; reg [4:0] rl=23; reg [7:0] mixw=4,mixr=4;
reg [31:0] base=0,count=64,seed=32'h1234abcd,job=1;
reg [2:0] blg=0; reg [15:0] runl=1; reg [23:0] strd=1; wire [5:0] bnum;
wire busy,done,faulted; wire [7:0] err; wire [31:0] accid,latmax;
wire [63:0] c_cyc,c_cmd,c_wb,c_rb,c_cs,c_ws,l_sum,l_n;
wire [127:0] ckw,ckr,cke; wire wr_ok,rd_ok;
wire [2:0] cmd; wire ce; wire [26:0] addr; wire [127:0] wd; wire we,wend; wire [15:0] wmask;
reg cr=0,wrdy=0,rv=0,re=1; reg [127:0] rd=0;
mem_bw #(.TIMEOUT_CYCLES(200),.TOTAL_TIMEOUT_CYCLES(64'd5000000),.PAIRED_WRITE(PAIRED),.CALIBRATION_SETTLE_CYCLES(4),
         .APP_ROW_PAD(ROWPAD),.MIX_LAG(8)) dut(
    .clk(clk),.reset_n(rst),.calibrated(cal),.start(start),.cancel(cancel),.mode(mode),.pattern(pat),.region_log2(rl),
    .mix_w(mixw),.mix_r(mixr),.base_byte(base),.beat_count(count),.seed(seed),.job_id(job),
    .burst_log2(blg),.run_len(runl),.stride(strd),.app_burst_number(bnum),
    .busy(busy),.done(done),.faulted(faulted),.error_code(err),.accepted_job_id(accid),
    .cnt_cycles(c_cyc),.cnt_cmds(c_cmd),.cnt_wbeats(c_wb),.cnt_rbeats(c_rb),.cnt_cmd_stall(c_cs),.cnt_wd_stall(c_ws),
    .lat_sum(l_sum),.lat_samples(l_n),.lat_max(latmax),.ck_wr(ckw),.ck_rd(ckr),.ck_exp(cke),
    .ck_wr_match(wr_ok),.ck_rd_match(rd_ok),
    .app_cmd(cmd),.app_cmd_en(ce),.app_addr(addr),.app_cmd_ready(cr),.app_write_data(wd),.app_write_en(we),
    .app_write_end(wend),.app_write_mask(wmask),.app_write_ready(wrdy),.app_read_data(rd),
    .app_read_valid(rv),.app_read_end(re));
// total deadline classification: ready never high, TIMEOUT longer than TOTAL
reg dl_start=0; wire dl_done; wire [7:0] dl_err;
mem_bw #(.TIMEOUT_CYCLES(100),.TOTAL_TIMEOUT_CYCLES(64'd5),.CALIBRATION_SETTLE_CYCLES(0),.PAIRED_WRITE(PAIRED)) dl(
    .clk(clk),.reset_n(rst),.calibrated(1'b1),.start(dl_start),.cancel(1'b0),.mode(2'd0),.pattern(3'd0),.region_log2(5'd23),
    .mix_w(8'd1),.mix_r(8'd1),.base_byte(32'b0),.beat_count(32'd1),.seed(32'b0),.job_id(32'd9),.burst_log2(3'd0),.run_len(16'd1),.stride(24'd1),
    .done(dl_done),.error_code(dl_err),.app_cmd_ready(1'b0),.app_write_ready(1'b0),
    .app_read_data(128'b0),.app_read_valid(1'b0),.app_read_end(1'b0));

// ---------------- shim state ----------------
integer sh=0;        // 0 ideal, 1 stall+jitter, 2 no cmd ready, 3 reads never returned, 4 one spurious valid, 6 read end low
integer lat=6,corr_at=-1;
integer pc=0,scen=0;
integer bL;   // beats per command in the monitor (follows blg while a job runs)
integer nw_cmd=0,nr_cmd=0,nw_dat=0,nrv=0,ncommit=0;
integer first_pc=-1,last_pc=-1,last_cmd_pc=-1,low_cr=0,low_wr=0,snap_cr=0,snap_wr=0,spur_done=0;
reg [26:0] lw_addr[0:8191]; reg [26:0] lr_addr[0:8191]; reg [26:0] wc_addr[0:8191]; reg [127:0] wdat[0:16383];
reg [26:0] qaddr[0:8191]; integer qdue[0:8191]; integer qh=0,qt=0;
reg [31:0] wh=32'h811c9dc5,rh=32'h811c9dc5;   // FNV-1a style running hash of command byte addresses (compared with the Python model)
reg [22:0] hk[0:16383]; reg [127:0] hv[0:16383]; reg hu[0:16383];
integer hi;
initial for(hi=0;hi<16384;hi=hi+1)begin hu[hi]=0;hk[hi]=0;hv[hi]=0;end
integer dupseen=0;
task hclear; integer q; begin for(q=0;q<16384;q=q+1)hu[q]=0;dupseen=0;$display("BWCLR"); end endtask
function integer hfind; input [22:0] k; integer s,n;
begin s=(k^(k>>7)^(k>>14))&16383;n=0;
  while(hu[s] && hk[s]!==k && n<16384)begin s=(s+1)&16383;n=n+1;end
  hfind=s; end endfunction
// native address -> byte address, written from the layout description, independent of the DUT
function [26:0] decode; input [26:0] a; reg [12:0] row; reg [2:0] bank; reg [9:0] col; reg [25:0] l;
begin row=a[22:10];col=a[9:0];bank=ROWPAD?a[26:24]:a[25:23];l={row,bank,col};decode={l,1'b0};end endfunction

always @(posedge clk) if(rst) begin : mon
 integer s,k; reg [26:0] dba; reg [31:0] wsum;
 pc=pc+1;bL=1<<blg;
 if(sh==1 && first_pc>=0)begin if(!cr)low_cr=low_cr+1; if(!wrdy)low_wr=low_wr+1; end
 if((ce&&!cr)||(we&&!wrdy))$fatal(1,"enable without native ready");
 if(PAIRED&&((ce&&cmd==0&&!we)||(we&&!(ce&&cmd==0)&&(nw_dat%bL)==0)))$fatal(1,"paired write: command and data not in the same cycle");
 if(ce&&cmd==0&&(nw_dat%bL)!=0)$fatal(1,"write command before the previous burst finished its data");
 if(we&&(wmask!=0||!wend))$fatal(1,"write mask/end");
 if(ce&&cmd!=0&&cmd!=1)$fatal(1,"bad command code");
 if(ce&&(ROWPAD?addr[23]:addr[26]))$fatal(1,"pad/rank bit must be zero");
 dba=decode(addr);
 if(ce&&dba[3:0]!=0)$fatal(1,"unaligned beat address");
 if(ce)begin
   if(first_pc<0)begin first_pc=pc;low_cr=0;low_wr=0;end
   last_cmd_pc=pc;snap_cr=low_cr;snap_wr=low_wr;
   if(bnum!=bL-1)$fatal(1,"app_burst_number %0d expected %0d",bnum,bL-1);
   if(cmd==0)begin lw_addr[nw_cmd]=decode(addr);wc_addr[nw_cmd]=decode(addr);nw_cmd=nw_cmd+1;wh=(wh^decode(addr))*32'h01000193;end
   else begin lr_addr[nr_cmd]=decode(addr);rh=(rh^decode(addr))*32'h01000193;
     for(k=0;k<bL;k=k+1)begin qaddr[qt%8192]=decode(addr)+(k<<4);
       qdue[qt%8192]=pc+lat+k+((sh==1)?(nr_cmd%4):0);qt=qt+1;end
     nr_cmd=nr_cmd+1;end
 end
 if(we)begin wdat[nw_dat]=wd;nw_dat=nw_dat+1;last_pc=pc;end
 if(rv)begin last_pc=pc;end
 if(bL==1)begin if(nw_cmd-nw_dat>1||nw_dat-nw_cmd>1)$fatal(1,"command/data skew above one beat");end
 else if(nw_dat>nw_cmd*bL||(nw_cmd>0&&nw_dat<(nw_cmd-1)*bL+1))$fatal(1,"burst command/data skew");
 while((ncommit>>blg)<nw_cmd&&ncommit<nw_dat)begin
   wsum=wc_addr[ncommit>>blg]+((ncommit&(bL-1))<<4);
   s=hfind(wsum[26:0]>>4);if(hu[s])dupseen=1;hu[s]=1;hk[s]=wsum[26:0]>>4;hv[s]=wdat[ncommit];ncommit=ncommit+1;end
end
always @(negedge clk) begin
 rv=0;re=(sh!=6);
 case(sh)
  0:begin cr=1;wrdy=1;end
  1:begin cr=(pc%5!=0);wrdy=(pc%7<3);end
  2:begin cr=0;wrdy=1;end
  default:begin cr=1;wrdy=1;end
 endcase
 if(!rst)begin qh=0;qt=0; end
 else begin
  if(sh==4&&busy&&!spur_done)begin rv=1;rd=128'h0123;spur_done=1;end
  else if(qh!=qt&&sh!=3&&qdue[qh%8192]<=pc+1)begin : ret
   integer s;
   s=hfind(qaddr[qh%8192]>>4);
   rd=hu[s]?hv[s]:{4{32'hdeadbeef}};
   if(nrv==corr_at)rd=rd^128'h1;
   rv=1;qh=qh+1;nrv=nrv+1;
  end
 end
end

// ---------------- independent reference models ----------------
function [26:0] ea; input [2:0] p; input integer i; input [31:0] b; input [4:0] k; input [31:0] s;
 integer j,row,bank,colg,L,ib; reg [31:0] x,t; reg [22:0] m; reg [26:0] q; reg [63:0] big;
 begin
  L=1<<blg;ib=i*L;
  m=(23'd1<<k)-1;q=0;
  case(p)
   0: q=ib*16;
   1: begin bank=ib%8;colg=(ib/8)%128;row=ib/1024;q=row*16384+bank*2048+colg*16;end
   2: begin row=ib%8192;q=row*16384+(ib/8192)*16;end
   3: begin x=(s==0)?32'h2545F491:s;
        for(j=0;j<i;j=j+1)begin t=x^(x<<13);t=t^(t>>17);x=t^(t<<5);end
        big=((x>>9)&m)&~(L-1);q=big*16;end
   4: begin big=i;big=big*64'h4F1BBD;big=(big[22:0]&(m>>blg))<<blg;q=big*16;end
   default: begin big=i/runl;big=big*strd+(i%runl)*L;q=(big&64'h7fffff)*16;end
  endcase
  ea=q+b[26:0];
 end endfunction
reg [127:0] ed[0:4095]; reg [127:0] tck;
task gen_exp; input [31:0] s; input integer n; integer j;
 reg [31:0] x0,x1,x2,x3,t;
 begin
  x0=s^32'h9E3779B9;if(x0==0)x0=32'h9E3779B9;
  x1=s^32'h243F6A88;if(x1==0)x1=32'h243F6A88;
  x2=s^32'hB7E15162;if(x2==0)x2=32'hB7E15162;
  x3=s^32'h85EBCA6B;if(x3==0)x3=32'h85EBCA6B;
  for(j=0;j<n;j=j+1)begin
   ed[j]={x3,x2,x1,x0};
   t=x0^(x0<<13);t=t^(t>>17);x0=t^(t<<5);
   t=x1^(x1<<13);t=t^(t>>17);x1=t^(t<<5);
   t=x2^(x2<<13);t=t^(t>>17);x2=t^(t<<5);
   t=x3^(x3<<13);t=t^(t>>17);x3=t^(t<<5);
  end
  begin : cs
   reg [63:0] a,b,f;
   a=0;b=0;
   for(j=0;j<n;j=j+1)begin f=ed[j][127:64]^ed[j][63:0];a=a+f;b={b[62:0],b[63]}^f;end
   tck={b,a};
  end
 end endtask

// ---------------- helpers ----------------
// one machine-readable line per job; fpga/mem/tests/bw_model.py recomputes every field independently
task report; input [8*24:1] nm;
 begin
  $display("BWRES nm=%0s sh=%0d lat=%0d paired=%0d rowpad=%0d mode=%0d pat=%0d blg=%0d run=%0d stride=%0d rl=%0d mixw=%0d mixr=%0d count=%0d base=%0d seed=%0d first=%0d last=%0d cyc=%0d cmds=%0d wb=%0d rb=%0d cs=%0d ws=%0d latmax=%0d latsum=%0d latn=%0d ckw=%h ckr=%h cke=%h wrok=%0d rdok=%0d wh=%h rh=%h err=%0d",
   nm,sh,lat,PAIRED,ROWPAD,mode,pat,blg,runl,strd,rl,mixw,mixr,count,base,seed,first_pc,last_pc,c_cyc,c_cmd,c_wb,c_rb,c_cs,c_ws,latmax,l_sum,l_n,ckw,ckr,cke,wr_ok,rd_ok,wh,rh,err);
 end endtask
task newjob; begin wh=32'h811c9dc5;rh=32'h811c9dc5;nw_cmd=0;nr_cmd=0;nw_dat=0;nrv=0;ncommit=0;first_pc=-1;last_pc=-1;last_cmd_pc=-1;spur_done=0;qh=0;qt=0;low_cr=0;low_wr=0;end endtask
task reset; begin @(negedge clk);rst=0;start=0;cancel=0;newjob;repeat(3)@(negedge clk);rst=1;end endtask
task launch; begin newjob;@(negedge clk);start=1;@(negedge clk);start=0;repeat(4)@(negedge clk);end endtask
task finish; integer n; begin n=0;while(!done&&n<600000)begin @(negedge clk);n=n+1;end
 if(!done)$fatal(1,"test deadline");repeat(3)@(negedge clk);end endtask
task check_addrs; input integer nw,nr; integer i; reg [26:0] e;
 begin
  if(nw_cmd!=nw||nr_cmd!=nr)$fatal(1,"command counts shim %0d/%0d expected %0d/%0d",nw_cmd,nr_cmd,nw,nr);
  for(i=0;i<nw;i=i+1)begin e=ea(pat,i,base,rl,seed);
    if(lw_addr[i]!==e)$fatal(1,"write addr pat%0d i=%0d got %h exp %h",pat,i,lw_addr[i],e);end
  for(i=0;i<nr;i=i+1)begin e=ea(pat,i,base,rl,seed);
    if(lr_addr[i]!==e)$fatal(1,"read addr pat%0d i=%0d got %h exp %h",pat,i,lr_addr[i],e);end
 end endtask
function integer has_dup; input integer n; integer i,j;
 begin has_dup=0;for(i=1;i<n;i=i+1)for(j=0;j<i;j=j+1)if(lw_addr[i]==lw_addr[j])has_dup=1;end endfunction
task chk_mem; input integer n; integer i,s; reg [31:0] a;
 begin for(i=0;i<n;i=i+1)begin a=ea(pat,i>>blg,base,rl,seed)+((i&((1<<blg)-1))<<4);s=hfind(a[26:0]>>4);
   if(!hu[s]||hv[s]!==ed[i])$fatal(1,"memory content beat %0d",i);end end endtask
task ok_end; begin if(faulted||err!==0||busy||!done)$fatal(1,"job ended with fault/err=%0d",err);end endtask

// write -> read -> mixed round trip for one pattern
task roundtrip; input integer pt,n; input [31:0] b; input [4:0] r; input integer expect_match;
 integer dup,mxc;
 begin
  pat=pt;count=n;base=b;rl=r;gen_exp(seed,n);
  hclear;
  mode=0;launch;finish;ok_end;report("rt_w");
  check_addrs(n,0);dup=has_dup(n);
  if(c_cmd!=n||c_wb!=n||c_rb!=0)$fatal(1,"write counters pat%0d",pt);
  if(c_cyc!=last_pc-first_pc+1)$fatal(1,"write total cycles dut %0d tb %0d",c_cyc,last_pc-first_pc+1);
  if(ckw!==tck||cke!==tck||!wr_ok||rd_ok)$fatal(1,"write checksums pat%0d",pt);
  if(!dup)chk_mem(n);
  mode=1;launch;finish;ok_end;report("rt_r");
  check_addrs(0,n);
  if(c_cmd!=n||c_rb!=n||c_wb!=0||c_cs!=0||c_ws!=0)$fatal(1,"read counters pat%0d",pt);
  if(c_cyc!=last_pc-first_pc+1)$fatal(1,"read total cycles dut %0d tb %0d",c_cyc,last_pc-first_pc+1);
  if(expect_match&&!dup)begin if(ckr!==tck||!rd_ok||cke!==tck)$fatal(1,"read checksum pat%0d",pt);end
  if(!expect_match&&(rd_ok||ckr===cke))$fatal(1,"checksum must flag collisions pat%0d",pt);
  if(l_n==0||latmax!=lat||l_sum!=lat*l_n)$fatal(1,"ideal latency stats max %0d sum %0d n %0d",latmax,l_sum,l_n);
  if(PAIRED)begin
  // mixed on an empty memory: reads must trail their writes
  hclear;
  mode=2;mixw=4;mixr=4;launch;finish;ok_end;report("rt_m");
  check_addrs(n,n);
  if(c_cmd!=2*n||c_wb!=n||c_rb!=n)$fatal(1,"mixed counters pat%0d %0d %0d %0d",pt,c_cmd,c_wb,c_rb);
  if(!dup&&expect_match)begin if(!wr_ok||!rd_ok||ckr!==tck||ckw!==tck)$fatal(1,"mixed checksum pat%0d (RAW ordering or data)",pt);end
  end
  scen=scen+1;
 end endtask

integer i,n,cyc_meas;
initial begin
 reset;
 // ===== 1. ideal memory throughput =====
 sh=0;lat=6;seed=32'h1234abcd;pat=0;base=0;count=4096;gen_exp(seed,4096);hclear;
 mode=0;launch;finish;ok_end;report("ideal_w");
 if(c_cmd!=4096||c_wb!=4096||c_rb!=0||c_cs!=0||c_ws!=0)$fatal(1,"ideal write counters");
 if(c_cyc!=4096)$fatal(1,"ideal write_stream must take exactly N cycles, got %0d",c_cyc);
 if(accid!=1||ckw!==tck||cke!==tck||!wr_ok)$fatal(1,"ideal write checksum");
 check_addrs(4096,0);chk_mem(4096);
 $display("INFO paired=%0d rowpad=%0d ideal write_stream N=4096: total_cycles=%0d (%0d beat/cycle)",PAIRED,ROWPAD,c_cyc,1);
 scen=scen+1;
 mode=1;launch;finish;ok_end;report("ideal_r");
 if(c_cmd!=4096||c_rb!=4096||c_wb!=0||c_cs!=0||c_ws!=0)$fatal(1,"ideal read counters");
 if(c_cyc!=4096+lat)$fatal(1,"ideal read_stream must take N+latency cycles, got %0d",c_cyc);
 if(ckr!==tck||!rd_ok)$fatal(1,"ideal read checksum");
 if(latmax!=lat||l_sum!=lat*l_n||l_n!=(4096+lat)/(lat+1))$fatal(1,"read latency stats max=%0d sum=%0d n=%0d",latmax,l_sum,l_n);
 $display("INFO ideal read_stream N=4096 latency=%0d: total_cycles=%0d samples=%0d lat_max=%0d",lat,c_cyc,l_n,latmax);
 scen=scen+1;
 // checksum round trip must catch a single flipped bit
 corr_at=1234;mode=1;launch;finish;ok_end;corr_at=-1;
 if(rd_ok||ckr===cke||ckr===tck||cke!==tck)$fatal(1,"checksum did not flag corrupted read");
 scen=scen+1;
 // ===== 2. address patterns, round trips, mixed =====
 roundtrip(0,300,32'h0,5'd23,1);
 roundtrip(0,300,32'h0004_0010,5'd23,1);
 roundtrip(1,2500,32'h0,5'd23,1);
 roundtrip(2,300,32'h0,5'd23,1);
 roundtrip(2,9000>4096?4096:9000,32'h0,5'd23,1);
 roundtrip(3,400,32'h0,5'd23,1);
 roundtrip(3,300,32'h0000_0100,5'd8,0);   // 300 draws from 256 slots: collisions, checksum must flag
 roundtrip(4,400,32'h0,5'd23,1);
 roundtrip(4,256,32'h0100_0000,5'd8,1);   // exactly region size: still collision free
 seed=32'h0;roundtrip(0,64,32'h0,5'd23,1);seed=32'hdeadbeef;roundtrip(1,64,32'h20,5'd23,1);seed=32'h1234abcd;
 // address wrap at the 128 MiB end
 roundtrip(0,8,32'h7ffffc0,5'd23,1);
 // mixed ratios
 if(PAIRED)begin
 pat=0;count=200;base=0;gen_exp(seed,200);hclear;mode=2;mixw=3;mixr=1;launch;finish;ok_end;report("mix_3_1");
 if(c_cmd!=400||!wr_ok||!rd_ok||ckr!==tck)$fatal(1,"mixed 3:1");
 hclear;mixw=1;mixr=5;launch;finish;ok_end;report("mix_1_5");
 if(c_cmd!=400||!rd_ok||ckr!==tck)$fatal(1,"mixed 1:5");
 $display("INFO ideal mixed N=200 pairs: total_cycles=%0d for %0d commands",c_cyc,c_cmd);
 if(c_cyc>2*c_cmd+lat+16)$fatal(1,"mixed overhead above the stated 2 cycles/command");
 scen=scen+1;
 // ===== 3. stalling shim =====
 end
 sh=1;lat=5;pat=0;base=0;count=1024;gen_exp(seed,1024);hclear;mode=0;launch;finish;ok_end;report("stall_w");
 cyc_meas=last_pc-first_pc+1;
 if(c_cyc!=cyc_meas||c_cmd!=1024||c_wb!=1024)$fatal(1,"stall write counters");
 if(c_cs==0||c_ws==0||c_cyc<1024+c_ws)$fatal(1,"stall counters write cs=%0d ws=%0d",c_cs,c_ws);
 if(PAIRED&&(c_cs!=snap_cr||c_ws!=snap_wr))$fatal(1,"stall counters vs independent count: dut %0d/%0d tb %0d/%0d",c_cs,c_ws,snap_cr,snap_wr);
 if(ckw!==tck||!wr_ok)$fatal(1,"stall write checksum");
 $display("INFO stalling shim write N=1024: total_cycles=%0d cmd_stall=%0d wd_stall=%0d",c_cyc,c_cs,c_ws);
 scen=scen+1;
 mode=1;launch;finish;ok_end;report("stall_r");
 cyc_meas=last_pc-first_pc+1;
 if(c_cyc!=cyc_meas||c_cmd!=1024||c_rb!=1024||c_ws!=0||c_cs==0)$fatal(1,"stall read counters");
 if(c_cs!=snap_cr)$fatal(1,"read cmd_stall dut %0d tb %0d",c_cs,snap_cr);
 if(ckr!==tck||!rd_ok||latmax<lat||l_sum<lat*l_n||l_n==0)$fatal(1,"stall read results");
 $display("INFO stalling shim read N=1024: total_cycles=%0d cmd_stall=%0d lat_max=%0d samples=%0d",c_cyc,c_cs,latmax,l_n);
 scen=scen+1;
 if(PAIRED)begin
 hclear;mode=2;mixw=4;mixr=4;count=512;gen_exp(seed,512);launch;finish;ok_end;
 if(c_cmd!=1024||c_wb!=512||c_rb!=512||!wr_ok||!rd_ok)$fatal(1,"stall mixed");
 scen=scen+1;
 end
 sh=0;lat=6;
 // ===== 4. error / timeout classification =====
 reset;count=0;mode=0;launch;finish;if(err!=2||faulted||nw_cmd)$fatal(1,"zero count");
 count=64;base=1;launch;finish;if(err!=2)$fatal(1,"unaligned base");
 base=32'h0800_0000;launch;finish;if(err!=2)$fatal(1,"base beyond 128MiB");
 base=0;count=32'd8388609;launch;finish;if(err!=2)$fatal(1,"count above 2^23");
 count=64;mode=3;launch;finish;if(err!=2)$fatal(1,"mode 3");
 mode=0;pat=6;launch;finish;if(err!=2)$fatal(1,"pattern 6");pat=7;launch;finish;if(err!=2)$fatal(1,"pattern 7");
 pat=3;rl=0;launch;finish;if(err!=2)$fatal(1,"region_log2 0");
 pat=4;rl=24;launch;finish;if(err!=2)$fatal(1,"region_log2 24");
 pat=0;rl=23;mode=2;mixw=0;launch;finish;if(err!=2)$fatal(1,"mix_w 0");
 mixw=4;if(PAIRED)begin mixr=0;launch;finish;if(err!=2)$fatal(1,"mix_r 0");mixr=4;end
 else begin launch;finish;if(err!=2)$fatal(1,"mixed needs PAIRED_WRITE");end
 pat=4;rl=8;count=300;mode=0;launch;finish;if(err!=2||faulted||nw_cmd||busy)$fatal(1,"scatter beyond region");
 pat=0;rl=23;count=16;mode=0;launch;finish;ok_end;if(c_cmd!=16)$fatal(1,"engine usable after config errors");
 reset;count=16;cal=0;launch;finish;if(err!=1||nw_cmd||faulted)$fatal(1,"uncalibrated");cal=1;
 reset;sh=2;count=64;launch;finish;if(err!=3||!faulted)$fatal(1,"no command ready -> error 3 (got %0d)",err);
 mode=0;launch;repeat(5)@(negedge clk);if(busy)$fatal(1,"fault rearmed without reset");
 reset;sh=3;count=64;mode=1;launch;finish;if(err!=4||!faulted)$fatal(1,"reads never returned -> error 4 (got %0d)",err);
 reset;sh=4;count=64;mode=0;launch;finish;if(err!=5||!faulted)$fatal(1,"unsolicited read data (got %0d)",err);
 reset;sh=6;count=4;mode=1;launch;finish;if(err!=5||!faulted)$fatal(1,"read end low (got %0d)",err);
 reset;sh=0;count=4096;mode=0;launch;repeat(50)@(negedge clk);cancel=1;@(negedge clk);cancel=0;
 if(ce||we)$fatal(1,"enable after cancel");finish;
 if(err!=7||!faulted||ce||we)$fatal(1,"cancel");
 reset;count=4096;launch;repeat(50)@(negedge clk);cal=0;finish;if(err!=8||!faulted)$fatal(1,"calibration loss");cal=1;
 reset;count=4096;launch;repeat(50)@(negedge clk);rst=0;#1;if(ce||we)$fatal(1,"outputs after reset");
 reset;@(negedge clk);dl_start=1;@(negedge clk);dl_start=0;
 repeat(12)@(negedge clk);if(!dl_done||dl_err!=9)$fatal(1,"total deadline classification (got %0d)",dl_err);
 scen=scen+1;

 // ===== 5. strided runs (pattern 5), burst length (burst_log2), error classes of the new fields =====
 reset;sh=0;lat=6;blg=0;
 runl=128;strd=128;roundtrip(5,512,32'h0,5'd23,1);          // == sequential
 runl=4;strd=1024;roundtrip(5,512,32'h0,5'd23,1);           // 4 beats then 16 KiB further: same bank, next row
 runl=1;strd=1024;roundtrip(5,256,32'h0,5'd23,1);           // pure 16 KiB stride
 runl=16;strd=64;roundtrip(5,256,32'h0,5'd23,1);
 runl=3;strd=100;roundtrip(5,300,32'h0000_0040,5'd23,1);
 runl=128;strd=1152;roundtrip(5,1024,32'h0,5'd23,1);        // page-sized runs, 128 beats gap (rotating banks)
 runl=1;strd=3;roundtrip(5,4096,32'h0,5'd23,1);             // small odd stride
 // burst length on the ideal shim: write N cycles, read N+latency; the memory content must be the written stream
 if(!PAIRED)begin : unpaired_burst
  reset;pat=0;rl=23;mode=0;base=0;count=64;blg=3;launch;finish;if(err!=2||nw_cmd)$fatal(1,"burst write needs PAIRED_WRITE");blg=0;
 end
 if(PAIRED)begin : bursts
  integer bi,bn,bpt; reg [31:0] bb; reg [4:0] brl; integer ok_match;
  for(bi=0;bi<12;bi=bi+1)begin
   case(bi)
    0:begin blg=1;bpt=0;bn=512;bb=0;brl=23;end
    1:begin blg=3;bpt=0;bn=1024;bb=32'h0000_0080;brl=23;end
    2:begin blg=6;bpt=0;bn=1024;bb=32'h0000_0400;brl=23;end
    3:begin blg=3;bpt=1;bn=1024;bb=0;brl=23;end
    4:begin blg=2;bpt=2;bn=256;bb=0;brl=23;end
    5:begin blg=3;bpt=3;bn=256;bb=32'h0000_0000;brl=12;end
    6:begin blg=3;bpt=4;bn=512;bb=32'h0001_0000;brl=12;end
    7:begin blg=3;bpt=5;bn=512;bb=0;brl=23;runl=4;strd=64;end
    8:begin blg=3;bpt=5;bn=512;bb=0;brl=23;runl=1;strd=1024;end        // 8-beat bursts, one per 16 KiB row
    9:begin blg=4;bpt=0;bn=1024;bb=0;brl=23;end
    10:begin blg=5;bpt=4;bn=1024;bb=32'h0010_0000;brl=14;end
    default:begin blg=0;bpt=0;bn=64;bb=0;brl=23;end
   endcase
   pat=bpt;count=bn;base=bb;rl=brl;gen_exp(seed,bn);hclear;
   mode=0;launch;finish;ok_end;report("burst_w");
   check_addrs(bn>>blg,0);
   if(c_cmd!=(bn>>blg)||c_wb!=bn||c_rb!=0||c_cs!=0||c_ws!=0)$fatal(1,"burst write counters bi=%0d cmds %0d wb %0d",bi,c_cmd,c_wb);
   if(c_cyc!=bn)$fatal(1,"ideal burst write must take exactly N=%0d cycles, got %0d (bi=%0d)",bn,c_cyc,bi);
   if(c_cyc!=last_pc-first_pc+1||ckw!==tck||cke!==tck||!wr_ok)$fatal(1,"burst write checksum/cycles bi=%0d",bi);
   if(!dupseen)chk_mem(bn);
   mode=1;launch;finish;ok_end;report("burst_r");
   check_addrs(0,bn>>blg);
   if(c_cmd!=(bn>>blg)||c_rb!=bn||c_wb!=0||c_cs!=0)$fatal(1,"burst read counters bi=%0d",bi);
   if(c_cyc!=bn+lat||c_cyc!=last_pc-first_pc+1)$fatal(1,"ideal burst read must take N+latency, got %0d bi=%0d",c_cyc,bi);
   if(!dupseen&&(ckr!==tck||!rd_ok))$fatal(1,"burst read checksum bi=%0d",bi);
   if(dupseen&&rd_ok)$fatal(1,"collisions in a burst job must be flagged by the checksum bi=%0d",bi);
   scen=scen+1;
  end
  blg=0;runl=1;strd=1;
 end
 // stalling shim with bursts: functional result and the DUT/independent stall counts
 if(PAIRED)begin
 sh=1;lat=5;pat=0;base=0;count=512;blg=3;gen_exp(seed,512);hclear;mode=0;launch;finish;ok_end;report("stall_burst_w");
 if(c_cyc!=last_pc-first_pc+1||c_cmd!=64||c_wb!=512||ckw!==tck||!wr_ok)$fatal(1,"stall burst write");
 mode=1;launch;finish;ok_end;report("stall_burst_r");
 if(c_cyc!=last_pc-first_pc+1||c_cmd!=64||c_rb!=512||ckr!==tck||!rd_ok)$fatal(1,"stall burst read");
 if(c_cs!=snap_cr)$fatal(1,"stall burst read cmd_stall dut %0d tb %0d",c_cs,snap_cr);
 scen=scen+1;
 end
 sh=0;lat=6;blg=0;
 // new error classes (configuration is rejected without touching the bus)
 reset;pat=0;rl=23;mode=0;base=0;count=64;runl=1;strd=1;
 blg=7;launch;finish;if(err!=2||nw_cmd)$fatal(1,"burst_log2 7");
 blg=3;count=12;launch;finish;if(err!=2||nw_cmd)$fatal(1,"count not a multiple of L");
 count=64;base=32'h10;launch;finish;if(err!=2||nw_cmd)$fatal(1,"base not 16*L aligned");
 base=0;mode=2;mixw=2;mixr=2;launch;finish;if(err!=2||nw_cmd)$fatal(1,"mixed with burst");
 mode=0;pat=5;runl=0;strd=64;launch;finish;if(err!=2||nw_cmd)$fatal(1,"run_len 0");
 runl=2;strd=0;launch;finish;if(err!=2||nw_cmd)$fatal(1,"stride 0");
 strd=12;launch;finish;if(err!=2||nw_cmd)$fatal(1,"stride not a multiple of L");
 strd=24'h800000;launch;finish;if(err!=2||nw_cmd)$fatal(1,"stride >= 2^23");
 strd=64;blg=0;count=16;launch;finish;ok_end;if(c_cmd!=16)$fatal(1,"usable after burst config errors");
 scen=scen+1;
 $display("PASS mem_bw%s%s %0d scenario groups: ideal 1 beat/cycle (write N cycles, read N+latency), address patterns incl. strided runs and burst length vs independent model, checksum round trip, mixed, stalls vs independent count, error classification",
          PAIRED?" paired":" unpaired",ROWPAD?" rowpad":"",scen);
 $finish;
end
endmodule
