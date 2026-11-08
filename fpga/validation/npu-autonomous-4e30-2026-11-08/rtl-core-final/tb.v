
`timescale 1ns/1ps
module tb_conv_link;
 reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
 reg[7:0]host_data=0;wire[7:0]data_o;wire data_oe,ready;wire[7:0]bus_data;assign bus_data=host_oe?host_data:8'bz;
 reg[7:0]q[0:2059],r[0:1033],payload[0:2050];reg[15:0]crc,tail;integer seq=0,packets=0;
 integer i,j,k,f,rc,jobs,ci,co,ho,wo,ks,st,fi,la,ni,nw,no,v,base,count,kind,chunk;
 reg[7:0]inputs[0:17423],weights[0:1151];reg signed[31:0]expected[0:2047],actual;
 reg[15:0]got_value;integer got_status;reg[31:0]cycles;
 always #18.5 clk=~clk;

 wire[3:0]led;reg pll_lock=0,ip_user_reset=1,calibrated=0,cal_override=0,native_hold=0;
 reg user_clk=0;always #5.022 user_clk=~user_clk;wire controller_reset_n;
 wire[2:0]cmd;wire cmd_en;wire[26:0]address;wire[127:0]wr_data;wire wr_en,wr_end;wire[15:0]mask;reg[127:0]rd_data=0;reg rd_valid=0,rd_end=0;
 reg[7:0]user_count=0;wire cmd_ready=controller_reset_n&&calibrated&&!native_hold&&user_count[2:0]!=2;
 wire wr_ready=controller_reset_n&&calibrated&&!native_hold&&user_count[2:0]!=5;
 reg[7:0]mem[0:524287];reg read_pending=0,write_cmd_pending=0,write_data_pending=0;reg[31:0]native_read_addr,native_write_addr;reg[127:0]native_write_data;
 integer cal_count=0,read_delay=0,reads=0,writes=0,z;
 function[31:0]decode_native;input[26:0]a;reg[25:0]lw;begin lw={a[22:10],a[26:24],a[9:0]};decode_native={5'd0,lw,1'b0};end endfunction
 function[31:0]mapped;input[31:0]a;begin if(a<32'h30000)mapped=a;else if(a>=32'h05000000&&a<32'h05020000)mapped=32'h40000+(a&131071);else if(a>=32'h07fd0000&&a<32'h07fe0000)mapped=32'h60000+(a&65535);else if(a>=32'h07ff0000&&a<32'h08000000)mapped=32'h70000+(a&65535);else mapped=32'hffffffff;end endfunction
 npu_ddr_core_autonomous #(.RESET_HOLD_INIT(8),.RECAL_HOLD(8)) dut(
  .sys_clk(clk),.reset_n(reset_n),.arm_sw(arm),.bus_clk(bus_clk),.dir(dir),.aux(4'd0),.data(bus_data),.ready(ready),.led(led),
  .pll_lock(pll_lock),.user_clk(user_clk),.ip_user_reset(ip_user_reset),.calibrated(calibrated),.controller_reset_n(controller_reset_n),
  .cmd(cmd),.cmd_en(cmd_en),.address(address),.cmd_ready(cmd_ready),.wr_data(wr_data),.wr_en(wr_en),.wr_end(wr_end),.mask(mask),.wr_ready(wr_ready),.rd_data(rd_data),.rd_valid(rd_valid),.rd_end(rd_end));
 assign data_o=dut.data_out;assign data_oe=dut.data_oe;
 always @(posedge user_clk)begin
  if(!controller_reset_n||ip_user_reset||cal_override)begin calibrated<=0;cal_count<=0;end
  else if(cal_count<64)begin cal_count<=cal_count+1;calibrated<=0;end else calibrated<=1;
  if(!reset_n)begin reads<=0;writes<=0;user_count<=0;read_pending<=0;write_cmd_pending<=0;write_data_pending<=0;rd_valid<=0;rd_end<=0;rd_data<=0;read_delay<=0;end
  else begin
   user_count<=user_count+1'b1;rd_valid<=0;rd_end<=0;
   if(!controller_reset_n||!calibrated||ip_user_reset)begin read_pending<=0;write_cmd_pending<=0;write_data_pending<=0;end
   else begin
    if(cmd_en && cmd_ready)begin
     if(address[2:0]!=0 || decode_native(address)+16>32'h08000000 || mapped(decode_native(address))==32'hffffffff)$fatal(1,"native address/map %h ->%h",address,decode_native(address));
     if(cmd==1)begin if(read_pending)$fatal(1,"native read overlap");read_pending<=1;native_read_addr<=decode_native(address);read_delay<=4+user_count[1:0];end
     else if(cmd==0)begin if(write_cmd_pending)$fatal(1,"native write overlap");write_cmd_pending<=1;native_write_addr<=decode_native(address);end
     else $fatal(1,"native opcode");
    end
    if(wr_en && wr_ready)begin if(write_data_pending||mask!=0||!wr_end)$fatal(1,"native pairing/mask");write_data_pending<=1;native_write_data<=wr_data;end
    if(write_cmd_pending && write_data_pending)begin for(z=0;z<16;z=z+1)mem[mapped(native_write_addr)+z]<=native_write_data[z*8+:8];writes<=writes+1;write_cmd_pending<=0;write_data_pending<=0;end
    if(read_pending)begin if(read_delay!=0)read_delay<=read_delay-1;else begin for(z=0;z<16;z=z+1)rd_data[z*8+:8]<=mem[mapped(native_read_addr)+z];rd_valid<=1;rd_end<=1;read_pending<=0;reads<=reads+1;end end
   end
  end
 end

 always @(posedge clk)if(host_oe && data_oe)$fatal(1,"bus contention");
 function[15:0]crcbyte;input[15:0]c;input[7:0]b;reg[15:0]x;integer t;
 begin x=c^{b,8'd0};for(t=0;t<8;t=t+1)x=x[15]?(x<<1)^16'h1021:x<<1;crcbyte=x;end endfunction
 task pulse;begin #1000;bus_clk=1;#1000;bus_clk=0;end endtask
 task make_request;input integer op,len,bad_header,bad_tail;integer t;reg[15:0]c;
 begin
 seq=(seq+1)&255;q[0]=8'ha5;q[1]=op;q[2]=seq;q[3]=2;q[4]=len&255;q[5]=(len>>8)&255;c=16'hffff;
 for(t=0;t<6;t=t+1)c=crcbyte(c,q[t]);q[6]=c[7:0]^bad_header;q[7]=c[15:8];
 if(len)begin for(t=0;t<len;t=t+1)begin q[8+t]=payload[t];c=crcbyte(c,payload[t]);end q[8+len]=c[7:0]^bad_tail;q[9+len]=c[15:8];end
 end endtask
 task send_request;input integer op,len,bad_header,bad_tail;integer t,n;
 begin
 make_request(op,len,bad_header,bad_tail);dir=0;#1000;host_oe=1;n=len?len+10:8;
 for(t=0;t<n;t=t+1)begin host_data=q[t];pulse();end
 host_oe=0;#1000;dir=1;#1000;
 end endtask
 task read_response;input integer words;integer t,n,waited;reg[15:0]c;
 begin
 waited=0;while(!ready && waited<26000)begin #1000;waited=waited+1;end
 if(!ready)$fatal(1,"response timeout packet %d state %d",packets,dut.link.state);
 #1000;if(!data_oe)$fatal(1,"ready without OE");n=8;
 for(t=0;t<8;t=t+1)begin r[t]=bus_data;pulse();end
 c=16'hffff;for(t=0;t<6;t=t+1)c=crcbyte(c,r[t]);
 if(r[0]!==8'h5a || r[2]!==seq[7:0] || r[3]!==2 || r[6]!==c[7:0] || r[7]!==c[15:8])$fatal(1,"header/CRC/sequence packet %d",packets);
 got_status=r[1];got_value={r[5],r[4]};
 if(words && !got_status)begin
 if(got_value!==words)$fatal(1,"read count %d vs %d",got_value,words);
 n=8+words+2;for(t=8;t<n;t=t+1)begin r[t]=bus_data;pulse();end
 for(t=8;t<n-2;t=t+1)c=crcbyte(c,r[t]);if(r[n-2]!==c[7:0] || r[n-1]!==c[15:8])$fatal(1,"tail CRC packet %d",packets);
 end
 dir=0;#1000;if(ready || data_oe)$fatal(1,"response not released packet %d",packets);packets=packets+1;
 end endtask
 task command;input integer op,len,words,status;begin send_request(op,len,0,0);read_response(words);if(got_status!==status)$fatal(1,"status opcode %h got %d expected %d packet %d",op,got_status,status,packets);end endtask
 task configure;input integer c,o,h,w,kern,stride,flags;
 begin payload[0]=c;payload[1]=o;payload[2]=h;payload[3]=w;payload[4]=kern;payload[5]=stride;payload[6]=(h-1)*stride+kern;payload[7]=(w-1)*stride+kern;payload[8]=flags;command(8'h60,9,0,0);end endtask
 task upload;input integer typ,addr,n,bad;
 begin payload[0]=typ;payload[1]=addr&255;payload[2]=(addr>>8)&255;for(k=0;k<n;k=k+1)payload[3+k]=typ?weights[addr+k]:inputs[addr+k];send_request(8'h61,n+3,0,bad);read_response(0);if(got_status!==(bad?1:0))$fatal(1,"upload status got %d packet %d",got_status,packets);end endtask

 always @(posedge clk)if(dut.local_cpu.mmio_ready)begin
  if(dut.local_cpu.native_wstrb==0)$display("CSR read addr%h value%h gen%h",dut.local_cpu.native_addr,dut.local_cpu.native_rdata,dut.generation);
  else if(dut.local_cpu.native_addr[7:0]==12)$display("CSR ABORT PC%h",dut.local_cpu.cpu.reg_pc);
 end
 reg[7:0]program_bytes[0:2683];integer off,take,t,n,timeout;reg[15:0]auto_status;
 task ctrl;input integer action,token,status;begin
  payload[0]=action;payload[1]=0;payload[2]=0;payload[3]=0;
  payload[4]=token;payload[5]=token>>8;payload[6]=token>>16;payload[7]=token>>24;
  command(8'h7e,8,0,status);
 end endtask
 task rd;input integer addr,len;begin
  payload[0]=addr;payload[1]=addr>>8;payload[2]=addr>>16;payload[3]=addr>>24;
  payload[4]=len;payload[5]=len>>8;payload[6]=0;payload[7]=0;command(8'h70,8,len,0);
 end endtask
 function signed[31:0]word;input integer o;begin word={r[8+o+3],r[8+o+2],r[8+o+1],r[8+o]};end endfunction
 task wait_end;begin
  timeout=0;auto_status=2;
  while(auto_status[1]&&timeout<1000)begin ctrl(0,0,0);auto_status=got_value;timeout=timeout+1;end
  if(auto_status[1])$fatal(1,"autonomous timeout state%h CPU%h cache%d",st,dut.local_cpu.cpu.reg_pc,dut.local_cpu.memory.state);
 end endtask
 initial begin
  for(i=0;i<524288;i=i+1)mem[i]=0;
  $readmemh("program.hex",program_bytes);
  #200;reset_n=1;arm=1;pll_lock=1;ip_user_reset=0;
  timeout=0;while(!dut.memory_ready&&timeout<100000)begin @(posedge clk);timeout=timeout+1;end
  if(!dut.memory_ready)$fatal(1,"memory calibration");
  command(8'h50,0,0,0);if(got_value!==16'h4e30)$fatal(1,"wrong capability");
  ctrl(1,32'h735129ab,9);
  payload[0]=8'hab;payload[1]=8'h29;payload[2]=8'h51;payload[3]=8'h73;command(8'h75,4,0,0);
  for(off=0;off<2684;off=off+take)begin
   take=2684-off;if(take>2032)take=2032;n=(take+15)&~15;
   payload[0]=off;payload[1]=off>>8;payload[2]=0;payload[3]=5;
   payload[4]=n;payload[5]=n>>8;payload[6]=0;payload[7]=0;
   for(t=0;t<n;t=t+1)payload[8+t]=t<take?program_bytes[off+t]:0;
   command(8'h71,8+n,0,0);
  end
  ctrl(3,32'h735129ab,0);ctrl(1,32'h735129aa,9);ctrl(1,32'h735129ab,0);
  if(!dut.local_running)$fatal(1,"START did not hold RUN lease");
  payload[0]=0;payload[1]=16;payload[2]=0;payload[3]=0;payload[4]=16;payload[5]=0;payload[6]=0;payload[7]=0;
  command(8'h70,8,0,4);
  for(t=0;t<16;t=t+1)payload[8+t]=8'h5a;command(8'h71,24,0,4);
  command(8'h78,0,0,4);command(8'h67,0,0,4);
  // Unknown monitor and malformed CONTROL reject without touching DDR.
  payload[0]=128;payload[1]=0;payload[2]=0;payload[3]=0;command(8'h7f,4,0,3);
  wait_end();if(!auto_status[2]||auto_status[6:3])$fatal(1,"firmware not complete status%h app%h conv=%d/%d MACstatus=%h CPUfault=%b CPUerr=%h cache=%h state=%d desc=%h",auto_status,dut.cpu_app_error,dut.conv_error,dut.conv_error_code,dut.local_cpu.status_word,dut.cpu_fault,dut.cpu_error_code,dut.local_cpu.memory.error_code,dut.local_cpu.state,dut.cpu_descriptor);
  rd(32'h07ff0000,208);if(word(48)!==4||word(64)!==14||word(80)!==6)$fatal(1,"bad committed mailbox");
  rd(32'h3000,256);
  for(co=0;co<2;co=co+1)for(ho=0;ho<2;ho=ho+1)for(wo=0;wo<2;wo=wo+1)begin
   actual=0;for(ci=0;ci<3;ci=ci+1)actual=actual+(ci*3+ho*2+wo-5)*(co+ci-2);
   if(word(co*128+ho*64+wo*4)!==actual)$fatal(1,"actual Tile integer mismatch");
  end
  rd(32'h6000,128);
  for(co=0;co<2;co=co+1)for(ho=0;ho<3;ho=ho+1)begin
   actual=0;for(ci=0;ci<5;ci=ci+1)actual=actual+(ci*3+ho-7)*(co+ci-3);
   if(word(co*64+ho*4)!==actual)$fatal(1,"actual Matrix integer mismatch");
  end
  command(8'h78,0,0,2);command(8'h79,0,0,2);
  payload[0]=2;payload[1]=0;payload[2]=0;payload[3]=0;command(8'h7f,4,0,0);if(got_value!==14)$fatal(1,"latched node monitor");
  // A finished run cannot restart without CLEAR, then an early abort cannot
  // publish the stale successful result from the preceding firmware run.
  ctrl(1,32'h735129ab,4);ctrl(3,32'h735129ab,0);ctrl(1,32'h735129ab,0);
  ctrl(2,32'h735129ab,0);wait_end();if(auto_status[2]||!auto_status[3]||!auto_status[6])$fatal(1,"abort published old result %h",auto_status);
  $display("PASS autonomous full core: real RV32/cache/8OC+CPU-sequenced-MatMul/CDC/DDR adapter;14 integer outputs, token/BUSY/abort/no-stale-complete guards; packets%0d",packets);$finish;
 end
endmodule
