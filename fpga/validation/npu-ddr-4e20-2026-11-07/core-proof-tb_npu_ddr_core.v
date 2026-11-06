
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
 reg[7:0]mem[0:262143];reg read_pending=0,write_cmd_pending=0,write_data_pending=0;reg[31:0]native_read_addr,native_write_addr;reg[127:0]native_write_data;
 integer cal_count=0,read_delay=0,reads=0,writes=0,z;
 function[31:0]decode_native;input[26:0]a;reg[25:0]lw;begin lw={a[22:10],a[26:24],a[9:0]};decode_native={5'd0,lw,1'b0};end endfunction
 function[31:0]mapped;input[31:0]a;begin if(a<32'h30000)mapped=a;else if(a>=32'h07ff0000&&a<32'h08000000)mapped=32'h30000+(a&65535);else mapped=32'hffffffff;end endfunction
 npu_ddr_core #(.RESET_HOLD_INIT(8),.RECAL_HOLD(8)) dut(
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

 integer vectors,opn,len,expect_status,expect_value,nbytes,write_delta,bad_tail,ops,bw,br,token_low,gen0,timeout;
 reg[7:0]expect_bytes[0:1023],golden_out[0:335],saved_first_desc[0:51],saved_last_desc[0:51],cached_input[0:2047],cached_weight[0:2047],cached_output[0:2047];
 integer cached_input_len,cached_weight_len,cached_output_len;
 task wait_memory;begin timeout=0;while(!dut.memory_ready && timeout<100000)begin @(posedge clk);#1;timeout=timeout+1;end if(!dut.memory_ready)$fatal(1,"calibration/settle timeout");end endtask
 task bind_session;input[31:0]token;begin payload[0]=token[7:0];payload[1]=token[15:8];payload[2]=token[23:16];payload[3]=token[31:24];command(8'h75,4,0,0);end endtask
 task small_write;input[31:0]addr;input integer bias;begin payload[0]=addr[7:0];payload[1]=addr[15:8];payload[2]=addr[23:16];payload[3]=addr[31:24];payload[4]=16;payload[5]=0;payload[6]=0;payload[7]=0;for(i=0;i<16;i=i+1)payload[8+i]=(bias+i)&255;command(8'h71,24,0,0);end endtask
 task small_read;input[31:0]addr;input integer bias,status;begin payload[0]=addr[7:0];payload[1]=addr[15:8];payload[2]=addr[23:16];payload[3]=addr[31:24];payload[4]=16;payload[5]=0;payload[6]=0;payload[7]=0;command(8'h70,8,status?0:16,status);if(!status)for(i=0;i<16;i=i+1)if(r[8+i]!==((bias+i)&255))$fatal(1,"small read mismatch");end endtask
 initial begin
 for(i=0;i<262144;i=i+1)mem[i]=8'ha5;
 #200;reset_n=1;arm=1;#1000;
 // Identity/status remain reachable while DDR/controller is not ready.
 command(1,0,0,0);if(got_value!==16'h5054)$fatal(1,"identity");command(8'h50,0,0,0);if(got_value!==16'h4e20)$fatal(1,"caps");command(8'h64,0,0,0);if(got_value!==0)$fatal(1,"premature memory_ready");
 payload[0]=1;payload[1]=2;payload[2]=3;payload[3]=4;command(8'h75,4,0,3);
 pll_lock=1;ip_user_reset=0;wait_memory();
 vectors=$fopen("D:/GitHub/airpocket-soundman/tab5-tang-primer20k-carrier-resume-20261106/fpga/build/npu-ddr-core-extended/vectors.txt","r");if(!vectors)$fatal(1,"vectors missing");rc=$fscanf(vectors,"%d",ops);
 for(j=0;j<ops;j=j+1)begin
 rc=$fscanf(vectors,"%d %d %d %d %d %d %d",opn,len,expect_status,expect_value,nbytes,write_delta,bad_tail);if(rc!=7)$fatal(1,"vector header %d",j);
 for(i=0;i<len;i=i+1)begin rc=$fscanf(vectors,"%d",v);payload[i]=v;end
 for(i=0;i<nbytes;i=i+1)begin rc=$fscanf(vectors,"%d",v);expect_bytes[i]=v;end
 if(opn==8'h68)for(i=0;i<52;i=i+1)begin if(payload[6]&1)saved_first_desc[i]=payload[i];else saved_last_desc[i]=payload[i];end
 if(opn==8'h71 && {payload[3],payload[2],payload[1],payload[0]}==32'h1000)begin cached_input_len=len;for(i=0;i<len;i=i+1)cached_input[i]=payload[i];end
 if(opn==8'h71 && {payload[3],payload[2],payload[1],payload[0]}==32'h8000)begin cached_weight_len=len;for(i=0;i<len;i=i+1)cached_weight[i]=payload[i];end
 if(opn==8'h71 && {payload[3],payload[2],payload[1],payload[0]}==32'h10000)begin cached_output_len=len;for(i=0;i<len;i=i+1)cached_output[i]=payload[i];end
 if(opn==8'h70 && {payload[3],payload[2],payload[1],payload[0]}==32'h10000)for(i=0;i<nbytes;i=i+1)golden_out[i]=expect_bytes[i];
 bw=writes;send_request(opn,len,0,bad_tail);read_response(nbytes);
 if(got_status!==expect_status || (expect_value>=0 && got_value!==expect_value))$fatal(1,"status/value command%d op%h got%d value%h",j,opn,got_status,got_value);
 if(write_delta>=0 && writes-bw!=write_delta)$fatal(1,"write effect command%d delta%d expected%d",j,writes-bw,write_delta);
 for(i=0;i<nbytes;i=i+1)if(r[8+i]!==expect_bytes[i])$fatal(1,"wire numeric command%d offset%d got%h expected%h",j,i,r[8+i],expect_bytes[i]);
 end
 $fclose(vectors);
 // Calibration loss with the Conv master in flight invalidates the private
 // IC context. A new token cannot resurrect that partial; re-upload/restart.
 bw=writes;native_hold=1;for(i=0;i<52;i=i+1)payload[i]=saved_first_desc[i];payload[6]=7;send_request(8'h68,52,0,0);
 timeout=0;while(!dut.arbiter_active && timeout<1000)begin @(posedge clk);#1;timeout=timeout+1;end
 if(!dut.arbiter_active || !dut.conv_busy)$fatal(1,"Conv request not outstanding");cal_override=1;read_response(0);if(got_status!==8 || got_value!==0 || writes!=bw)$fatal(1,"Conv cal loss publication");
 cal_override=0;native_hold=0;wait_memory();bind_session(32'h8899aabb);
 for(i=0;i<52;i=i+1)payload[i]=saved_last_desc[i];command(8'h68,52,0,5);command(8'h67,0,0,0);
 for(i=0;i<cached_input_len;i=i+1)payload[i]=cached_input[i];command(8'h71,cached_input_len,0,0);
 for(i=0;i<cached_weight_len;i=i+1)payload[i]=cached_weight[i];command(8'h71,cached_weight_len,0,0);
 for(i=0;i<cached_output_len;i=i+1)payload[i]=cached_output[i];command(8'h71,cached_output_len,0,0);
 for(i=0;i<52;i=i+1)payload[i]=saved_first_desc[i];command(8'h68,52,0,0);
 for(i=0;i<52;i=i+1)payload[i]=saved_last_desc[i];command(8'h68,52,0,0);
 payload[0]=0;payload[1]=0;payload[2]=1;payload[3]=0;payload[4]=80;payload[5]=1;payload[6]=0;payload[7]=0;command(8'h70,8,336,0);for(i=0;i<336;i=i+1)if(r[8+i]!==golden_out[i])$fatal(1,"Conv reupload/restart mismatch");
 // Truncated staged WRITE never reaches DDR or changes binding.
 small_write(32'h22000,71);bw=writes;payload[0]=0;payload[1]=32'h20;payload[2]=2;payload[3]=0;payload[4]=16;payload[5]=0;payload[6]=0;payload[7]=0;for(i=0;i<16;i=i+1)payload[8+i]=8'hff;
 make_request(8'h71,24,0,0);dir=0;#1000;host_oe=1;for(i=0;i<24;i=i+1)begin host_data=q[i];pulse();end host_oe=0;#1000;dir=1;#3000;if(ready||data_oe||writes!=bw)$fatal(1,"truncated WRITE effects");dir=0;#1000;small_read(32'h22000,71,0);
 // Hold native admission and lose calibration with a HOST request in flight.
 command(8'h74,0,0,0);gen0=got_value;br=reads;bw=writes;native_hold=1;
 payload[0]=0;payload[1]=32'h20;payload[2]=2;payload[3]=0;payload[4]=16;payload[5]=0;payload[6]=0;payload[7]=0;
 send_request(8'h70,8,0,0);if(!dut.arbiter_active)$fatal(1,"host request was not outstanding");cal_override=1;read_response(0);if(got_status!==8||got_value!==0)$fatal(1,"cal-loss did not cancel host frame");
 command(8'h76,0,0,0);if(got_value!==0)$fatal(1,"stale bound token retained");command(8'h77,0,0,0);if(got_value!==0)$fatal(1,"stale high token retained");command(8'h74,0,0,0);if(got_value!==((gen0+1)&65535))$fatal(1,"cal generation");
 cal_override=0;native_hold=0;wait_memory();if(reads!=br||writes!=bw)$fatal(1,"old operation replayed after cal reset");small_read(32'h22000,71,9);
 bind_session(32'hc013beef);small_write(32'h22000,93);small_read(32'h22000,93,0);
 // ARM resets controller/session but does not reset generation itself.
 command(8'h74,0,0,0);gen0=got_value;send_request(1,0,0,0);arm=0;#1;if(ready||data_oe)$fatal(1,"ARM OE release");dir=0;#1000;arm=1;wait_memory();command(8'h74,0,0,0);if(got_value!==((gen0+1)&65535))$fatal(1,"ARM generation reset/replay");command(8'h76,0,0,0);if(got_value!==0)$fatal(1,"ARM session survived");
 // Physical reset is the only operation that resets generation to zero.
 send_request(1,0,0,0);reset_n=0;#1;if(ready||data_oe)$fatal(1,"physical reset OE release");dir=0;#1000;reset_n=1;wait_memory();command(8'h74,0,0,0);if(got_value!==0)$fatal(1,"physical generation reset");command(8'h50,0,0,0);if(got_value!==16'h4e20)$fatal(1,"postreset caps");bind_session(32'haabbccdd);small_write(32'h22000,17);small_read(32'h22000,17,0);
 $display("PASS NPU DDR core commands=%0d pins+realCDC/adapter, CRCWRITE/READ/ConvICDMA,128Mboundary,session/cal-loss/no-replay/ARM/reset",packets);$finish;
 end
 initial begin #1000000000;$fatal(1,"global timeout");end
endmodule
