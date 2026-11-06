"""Full NPU DDR core pin-level test with actual CDC/adapter and mock native DDR."""
from pathlib import Path
import argparse,json,hashlib,os,subprocess,struct
import numpy as np
from run_conv_link import TB as OLD_TB
ROOT=Path(__file__).resolve().parents[2]
NATIVE=r'''
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
'''
MAIN=r'''
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
 vectors=$fopen("VECTORS","r");if(!vectors)$fatal(1,"vectors missing");rc=$fscanf(vectors,"%d",ops);
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
'''
def vectors(path):
 rng=np.random.default_rng(20261107);cmds=[]
 def cmd(op,payload=b'',status=0,value=0,reply=b'',writes=0,bad=0):cmds.append((op,bytes(payload),status,value,bytes(reply),writes,bad))
 def memdesc(addr,n):return struct.pack('<IH2x',addr,n)
 def write(addr,data,status=0,bad=0):cmd(0x71,memdesc(addr,len(data))+data,status,writes=0 if status else len(data)//16,bad=bad)
 def read(addr,data):cmd(0x70,memdesc(addr,len(data)),value=len(data),reply=data)
 cmd(0x70,memdesc(0x1000,16),status=9)
 token=0x19b7c3a5;cmd(0x75,struct.pack('<I',token));cmd(0x76,value=token&65535);cmd(0x77,value=token>>16);cmd(0x64,value=0x8001)
 pattern=bytes((i*37+11)&255 for i in range(2032));write(0x3ff0,pattern);read(0x3ff0,pattern[:1024]);read(0x43f0,pattern[1024:]);write(0x3ff0,b'\xff'*16,status=1,bad=1);read(0x3ff0,pattern[:16])
 end=bytes(range(16));write(0x07fffff0,end);read(0x07fffff0,end);write(0x07fffff0,bytes(32),status=3);read(0x07fffff0,end);cmd(0x70,memdesc(0x08000000,16),status=3);cmd(0x70,memdesc(0x1001,16),status=3)
 full_ic,oc,h,w,oh,ow,k,s=19,3,6,8,3,5,3,2;ib,ip,cp,wb,ws,ob,op,ocp=0x1005,16,96,0x8003,171,0x10000,32,112;oy,ox=-1,-1
 x=rng.integers(-128,128,(full_ic,h,w),dtype=np.int16).astype(np.int8);wt=rng.integers(-128,128,(oc,full_ic,k,k),dtype=np.int16).astype(np.int8)
 inp=bytearray([0xa5]*1840);weights=bytearray([0x5a]*528);out=bytearray([0xa5]*(oc*ocp));expected=out.copy()
 for c in range(full_ic):
  for y in range(h):inp[5+c*cp+y*ip:5+c*cp+y*ip+w]=x[c,y].tobytes()
 for c in range(oc):weights[3+c*ws:3+c*ws+full_ic*k*k]=wt[c].tobytes()
 write(0x1000,inp);write(0x8000,weights);write(ob,out)
 acc=np.zeros((oc,oh,ow),dtype=np.int64)
 for ic0,nic in [(0,16),(16,3)]:
  flags=(1 if ic0==0 else 2)|4
  desc=bytes([nic,oc,oh,ow,k,s,flags,0])+struct.pack('<HHiiIIIIIIII',h,w,oy,ox,ib+ic0*cp,ip,cp,wb+ic0*k*k,ws,ob,op,ocp);assert len(desc)==52
  cmd(0x68,desc,writes=0 if ic0==0 else oc*oh*((ow+3)//4))
  if ic0==0:read(ob,out)
  for c in range(oc):
   for yy in range(oh):
    for xx in range(ow):
     for ci in range(nic):
      for ky in range(k):
       for kx in range(k):
        sy=oy+yy*s+ky;sx=ox+xx*s+kx
        if 0<=sy<h and 0<=sx<w:acc[c,yy,xx]+=int(x[ic0+ci,sy,sx])*int(wt[c,ic0+ci,ky,kx])
  if ic0:
   for c in range(oc):
    for yy in range(oh):
     base=c*ocp+yy*op
     for xx in range(ow):expected[base+xx*4:base+xx*4+4]=struct.pack('<i',int(acc[c,yy,xx]))
     expected[base+ow*4:base+((ow+3)//4)*16]=bytes(((ow+3)//4)*16-ow*4)
   read(ob,expected)
  cycles=oc*oh*ow*(2*nic*k*k+3);cmd(0x65,value=cycles&65535);cmd(0x66,value=cycles>>16);cmd(0x64,value=0x8001)
 cmd(0x67);cmd(0x64,value=0x8001)
 with path.open('w') as f:
  f.write(str(len(cmds))+'\n')
  for op,payload,status,value,reply,writes,bad in cmds:
   f.write(f'{op} {len(payload)} {status} {value} {len(reply)} {writes} {bad}\n');f.write(' '.join(map(str,payload))+'\n');f.write(' '.join(map(str,reply))+'\n')
 return len(cmds)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.output=a.output.resolve();vec=a.output/'vectors.txt';count=vectors(vec)
 text=OLD_TB.split(' initial begin')[0]
 # The byte-wide bus is a real inout now; the CORE owns its tri-state driver.
 text=text.replace("wire[7:0]bus_data=host_oe?host_data:data_oe?data_o:8'bz;","wire[7:0]bus_data;assign bus_data=host_oe?host_data:8'bz;")
 text=text.replace(' npu_conv_link #(.TIMEOUT(700000)) dut(clk,reset_n,arm,bus_clk,dir,bus_data,data_o,data_oe,ready);',NATIVE)
 text=text.replace('n=8+words*4+2','n=8+words+2').replace('dut.state','dut.link.state')
 text+=MAIN;tb=a.output/'tb_npu_ddr_core.v';tb.write_text(text.replace('VECTORS',vec.as_posix()));binary=a.output/'test.vvp';env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');logs=[]
 sources=[ROOT/'npu/rtl'/n for n in ['npu_ddr_core.v','npu_ddr_sys.v','npu_ddr_arbiter.v','npu_ddr_tile_loader.v','conv_tile_engine.v']]+[ROOT/'mem/rtl'/n for n in ['memv1_bridge.v','mem_adapter.v','memv1_crc32b.v']]
 result={'passed':False,'vector_commands':count,'device_access':'none','scope':'Full core pins, actual arbiter/CDC/adapter, mock native DDR only; no PHY/board'}
 try:
  for c in [[a.iverilog,'-g2012','-Wall','-s','tb_conv_link','-o',str(binary),*map(str,sources),str(tb)],[a.vvp,str(binary)]]:
   r=subprocess.run(c,env=env,capture_output=True,text=True,timeout=300);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
  result.update(passed=True,output=logs[-1],source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest()for x in sources})
 except Exception as e:result['error']=str(e);raise
 finally:(a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(logs[-1])
if __name__=='__main__':main()
