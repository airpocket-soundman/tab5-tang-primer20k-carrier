"""Pin-level NPU DDR framer checks with a mock bridge, staging RAM and Conv.
Does not instantiate a DDR controller, execute Conv arithmetic or access devices.
"""
from pathlib import Path
import argparse,hashlib,json,os,random,shutil,struct,subprocess,sys

ROOT=Path(__file__).resolve().parents[2]

TB=r'''
`timescale 1ns/1ps
module tb_npu_ddr_sys;
 reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
 reg[7:0]host_data=0;wire[7:0]data_o;wire data_oe,ready;
 wire[7:0]bus_data=host_oe?host_data:data_oe?data_o:8'bz;
 reg memory_ready=1;reg[15:0]generation=16'h1234;reg arbiter_fault=0,force_active=0;
 wire conv_start,conv_abort,conv_clear;wire[415:0]descriptor;
 reg conv_running=0,conv_done=0,conv_error=0,conv_quarantined=0;
 reg[3:0]conv_error_code=0;reg force_busy=0,force_not_ready=0,conv_fail=0,conv_quarantine=0,conv_hold=0;
 wire conv_busy=conv_running||force_busy;
 wire conv_start_ready=!conv_busy&&!force_not_ready&&!conv_quarantined;
 reg[415:0]expected_descriptor=0;integer conv_delay=0,conv_launches=0,conv_aborts=0,conv_clears=0;
 wire req_t,cancel_t;wire[1:0]h_op;wire[31:0]h_addr,h_arg;wire[15:0]h_beats;wire[23:0]h_tag;
 reg done_t=0;reg[23:0]r_tag=0;reg[3:0]r_status=0;reg[15:0]r_beats=0;
 wire w_we;wire[7:0]w_addr,r_addr;wire[127:0]w_data;
 reg[127:0]r_q=0,r_data=0,stage[0:255];reg[7:0]memory[0:8191];
 reg req_ref=0,cancel_ref=0,mem_pending=0;integer mem_delay=0,latency=7;
 reg[23:0]pending_tag=0;reg[15:0]pending_beats=0;
 reg bad_tag=0,bad_beats=0,mem_hold=0;reg[3:0]bad_status=0;
 wire arbiter_active=mem_pending||force_active;
 integer memory_requests=0,memory_writes=0,stage_writes=0,memory_cancels=0;
 integer i,j,k,n,save_requests,save_stage,save_writes,save_conv,save_aborts,save_cancels;
 reg[7:0]q[0:4095],r[0:2047],expected[0:1023];integer qlen,frames=0;
 reg[15:0]check_crc;
 always #5 clk=~clk;
 npu_ddr_sys #(.TIMEOUT(20000)) dut(
  .clk(clk),.reset_n(reset_n),.arm(arm),.bus_clk(bus_clk),.dir(dir),.data_i(bus_data),
  .data_o(data_o),.data_oe(data_oe),.ready(ready),
  .memory_ready(memory_ready),.generation(generation),.arbiter_fault(arbiter_fault),.arbiter_active(arbiter_active),
  .conv_start(conv_start),.conv_abort(conv_abort),.conv_clear(conv_clear),.descriptor(descriptor),
  .conv_start_ready(conv_start_ready),.conv_busy(conv_busy),.conv_done(conv_done),.conv_error(conv_error),.conv_quarantined(conv_quarantined),.conv_error_code(conv_error_code),
  .kernel_cycles(32'h12345678),.ddr_wait_cycles(32'h23456789),.total_cycles(32'h3456789a),
  .req_t(req_t),.cancel_t(cancel_t),.h_op(h_op),.h_addr(h_addr),.h_arg(h_arg),.h_beats(h_beats),.h_tag(h_tag),
  .done_t(done_t),.r_tag(r_tag),.r_status(r_status),.r_beats(r_beats),
  .w_we(w_we),.w_addr(w_addr),.w_data(w_data),.r_addr(r_addr),.r_data(r_data));
 always @(posedge clk)begin
  r_q<=stage[r_addr];r_data<=r_q;
  if(w_we)begin stage[w_addr]<=w_data;stage_writes<=stage_writes+1;end
  // Mirrors the top-level requirement: command bridge/arbiter drop work and
  // adopt toggles on memory readiness loss. This is not physical DDR behavior.
  if(!reset_n||!arm||!memory_ready)begin req_ref<=req_t;cancel_ref<=cancel_t;mem_pending<=0;mem_delay<=0;end
  else begin
   if(req_t!=req_ref)begin
    if(mem_pending)$fatal(1,"new request overwrote an outstanding held bundle");
    req_ref<=req_t;mem_pending<=1;mem_delay<=latency;pending_tag<=h_tag;pending_beats<=h_beats;memory_requests<=memory_requests+1;
    if(h_addr[3:0]!=0||h_beats<1||h_beats>127||h_arg!=0)$fatal(1,"bad bridge request metadata");
    if(h_op==0)for(j=0;j<h_beats;j=j+1)for(k=0;k<16;k=k+1)stage[j][k*8+:8]<=memory[(h_addr+j*16+k)&8191];
    else if(h_op==1)begin for(j=0;j<h_beats;j=j+1)for(k=0;k<16;k=k+1)memory[(h_addr+j*16+k)&8191]<=stage[j][k*8+:8];memory_writes<=memory_writes+1;end
    else $fatal(1,"unsupported bridge operation");
   end
   if(cancel_t!=cancel_ref)begin
    cancel_ref<=cancel_t;memory_cancels<=memory_cancels+1;
    if(mem_pending)begin r_tag<=pending_tag;r_status<=9;r_beats<=0;done_t<=~done_t;mem_pending<=0;end
   end else if(mem_pending&&!mem_hold)begin
    if(mem_delay)mem_delay<=mem_delay-1;
    else begin r_tag<=pending_tag^(bad_tag?24'd1:24'd0);r_status<=bad_status;r_beats<=pending_beats+(bad_beats?1:0);done_t<=~done_t;mem_pending<=0;end
   end
  end
 end
 always @(posedge clk)begin
  conv_done<=0;
  if(!reset_n||!arm||!memory_ready)begin conv_running<=0;conv_error<=0;conv_quarantined<=0;conv_error_code<=0;conv_delay<=0;end
  else if(conv_abort)begin conv_running<=0;conv_aborts<=conv_aborts+1;end
  else if(conv_clear)begin conv_error<=0;conv_quarantined<=0;conv_error_code<=0;conv_clears<=conv_clears+1;end
  else if(conv_start)begin
   if(!conv_start_ready||descriptor!==expected_descriptor)$fatal(1,"bad or reordered descriptor/start");
   conv_running<=1;conv_delay<=13;conv_launches<=conv_launches+1;
  end else if(conv_running&&!conv_hold)begin
   if(conv_delay)conv_delay<=conv_delay-1;
   else begin conv_running<=0;conv_done<=1;conv_error<=conv_fail;conv_quarantined<=conv_quarantine;conv_error_code<=conv_fail?4'd3:4'd0;end
  end
 end
 always @(posedge clk)if(host_oe&&data_oe)$fatal(1,"bus contention");
 function[15:0]crcbyte;input[15:0]c;input[7:0]b;reg[15:0]v;integer t;begin v=c^{b,8'd0};for(t=0;t<8;t=t+1)v=v[15]?(v<<1)^16'h1021:v<<1;crcbyte=v;end endfunction
 task tick;begin @(posedge clk);#1;end endtask
 task idle;input integer count;integer t;begin for(t=0;t<count;t=t+1)tick();end endtask
 task pulse;begin #50;bus_clk=1;#150;bus_clk=0;#100;end endtask
 task send;input integer count;integer t;begin
  dir=0;#100;host_oe=1;
  for(t=0;t<count;t=t+1)begin host_data=q[t];pulse();end
  host_oe=0;#100;
 end endtask
 task receive;input[7:0]status;input[15:0]value;input integer count;integer t,waited,total;reg[15:0]c;begin
  waited=0;while(!ready&&waited<40000)begin tick();waited=waited+1;end
  if(!ready)$fatal(1,"missing response frame=%0d status=%0d",frames,status);
  #100;dir=1;#100;if(!data_oe)$fatal(1,"response OE missing");
  total=count?8+count+2:8;
  for(t=0;t<total;t=t+1)begin r[t]=bus_data;pulse();end
  dir=0;#100;if(ready||data_oe)$fatal(1,"reply not retired");
  c=16'hffff;for(t=0;t<6;t=t+1)c=crcbyte(c,r[t]);
  if(r[0]!==8'h5a||r[1]!==status||r[2]!==q[2]||r[3]!==2||{r[5],r[4]}!==value||{r[7],r[6]}!==c)$fatal(1,"response header/status/sequence/value/CRC frame=%0d gotstatus=%0d value=%04x wantedstatus=%0d value=%04x",frames,r[1],{r[5],r[4]},status,value);
  if(count)begin
   for(t=0;t<count;t=t+1)begin if(r[8+t]!==expected[t])$fatal(1,"read payload endian/order byte%0d frame%0d got%02x wanted%02x",t,frames,r[8+t],expected[t]);c=crcbyte(c,r[8+t]);end
   if({r[9+count],r[8+count]}!==c)$fatal(1,"response payload CRC");
  end
  frames=frames+1;
 end endtask
 task silence;input integer count;integer t;begin dir=1;for(t=0;t<count;t=t+1)begin tick();if(ready||data_oe)$fatal(1,"unexpected reply after incomplete/timed-out frame");end dir=0;#100;end endtask
 task reset_endpoint;begin
  @(negedge clk);reset_n=0;arm=0;dir=0;host_oe=0;bus_clk=0;memory_ready=1;arbiter_fault=0;force_active=0;force_busy=0;force_not_ready=0;conv_fail=0;conv_quarantine=0;conv_hold=0;bad_tag=0;bad_status=0;bad_beats=0;mem_hold=0;
  idle(8);@(negedge clk);reset_n=1;arm=1;idle(12);if(ready||data_oe)$fatal(1,"reset/ARM phantom response");
 end endtask
 initial begin
  for(i=0;i<8192;i=i+1)memory[i]=((i*37)^(i>>3)^8'h5a)&255;
  for(i=0;i<256;i=i+1)stage[i]=0;
  reset_endpoint();
'''

def crc16(data):
    value=0xffff
    for byte in data:
        value^=byte<<8
        for _ in range(8):value=((value<<1)^0x1021 if value&0x8000 else value<<1)&0xffff
    return value

class Generate:
    def __init__(self):self.lines=[];self.sequence=0;self.exchanges=0;self.memory=bytearray(((i*37)^(i>>3)^0x5a)&255 for i in range(8192))
    def emit(self,line):self.lines.append(line)
    def packet(self,op,payload=b'',corrupt_header=False,corrupt_tail=False,declared=None):
        self.sequence=(self.sequence+1)&255;length=len(payload) if declared is None else declared
        head=bytes([0xa5,op,self.sequence,2,length&255,length>>8]);hcrc=crc16(head)^(1 if corrupt_header else 0)
        data=head+struct.pack('<H',hcrc)+payload
        if payload:data+=struct.pack('<H',crc16(head+payload)^(1 if corrupt_tail else 0))
        self.emit(f'qlen={len(data)};')
        self.lines.extend(f"q[{i}]=8'h{x:02x};"for i,x in enumerate(data))
        return len(data)
    def exchange(self,op,payload=b'',status=0,value=0,expected=b'',**kwargs):
        n=self.packet(op,payload,**kwargs)
        self.lines.extend(f"expected[{i}]=8'h{x:02x};"for i,x in enumerate(expected))
        self.emit(f"send({n});receive(8'd{status},16'h{value:04x},{len(expected)});");self.exchanges+=1
    def bind(self,token=0xcafebeef):self.exchange(0x75,struct.pack('<I',token))
    def read(self,addr,count,status=0,reserved=0):
        payload=struct.pack('<IHH',addr,count,reserved)
        expected=bytes(self.memory[(addr+i)&8191]for i in range(count)) if not status else b''
        self.exchange(0x70,payload,status,count if not status else 0,expected)
    def write(self,addr,data,status=0,**kwargs):
        payload=struct.pack('<IHH',addr,len(data),0)+data
        self.exchange(0x71,payload,status,**kwargs)
        if not status:
            for i,x in enumerate(data):self.memory[(addr+i)&8191]=x
    def generate(self):
        self.exchange(1,value=0x5054);self.exchange(0x50,value=0x4e20);self.exchange(0x64,value=1);self.exchange(0x74,value=0x1234)
        self.read(0,16,status=9);self.write(0,bytes(16),status=9)
        desc=bytes([3,5,7,9,3,2,7,0])+struct.pack('<HHiiIIIIIIII',31,41,-1,3,0x1000,48,1536,0x10000,288,0x20000,48,336)
        assert len(desc)==52
        self.exchange(0x68,desc,status=9)
        self.bind();self.exchange(0x64,value=0x8001);self.exchange(0x76,value=0xbeef);self.exchange(0x77,value=0xcafe)
        self.read(0,16);self.read(0x7fffff0,16)
        rng=random.Random(20261107)
        for i,count in enumerate([16,32,64,240,256,512,1008,1024,2032]):
            addr=0x100+i*256;data=bytes(rng.randrange(256)for _ in range(count));self.write(addr,data)
            for offset in range(0,count,1024):self.read(addr+offset,min(1024,count-offset))
        # Tail CRC cannot expose even one byte through staging-write or DDR request.
        self.emit('save_requests=memory_requests;save_stage=stage_writes;save_writes=memory_writes;')
        self.write(0x700,bytes(range(64)),status=1,corrupt_tail=True)
        self.emit('if(memory_requests!=save_requests||stage_writes!=save_stage||memory_writes!=save_writes)$fatal(1,"bad payload CRC performed writes");')
        self.read(0x700,64)
        self.emit('save_requests=memory_requests;save_stage=stage_writes;')
        count=self.packet(0x71,struct.pack('<IHH',0x800,32,0)+bytes(32));self.emit(f'send({count-12});silence(100);')
        self.emit('if(memory_requests!=save_requests||stage_writes!=save_stage)$fatal(1,"truncated payload reached staging/DDR");')
        self.exchange(1,value=0x5054)
        # Header CRC and tagged requests are rejected before any memory activity.
        self.exchange(1,status=1,corrupt_header=True);self.exchange(0x81,status=1)
        self.exchange(0x72,status=2);self.exchange(0x50,b'x',status=3)
        self.emit('save_requests=memory_requests;save_stage=stage_writes;')
        for addr,count in [(0,0),(0,15),(0,17),(1,16),(0x8000000,16),(0x7fffff0,32),(0xfffffff0,16),(0,1040)]:self.read(addr,count,status=3)
        self.read(0,16,status=3,reserved=1)
        self.exchange(0x70,bytes(7),status=3)
        self.exchange(0x71,struct.pack('<IHH',0,32,0)+bytes(16),status=3)
        self.exchange(0x71,struct.pack('<IHH',0,16,1)+bytes(16),status=3)
        self.packet(0x71,declared=2052);self.emit('send(8);receive(3,0,0);');self.exchanges+=1
        self.emit('if(memory_requests!=save_requests||stage_writes!=save_stage)$fatal(1,"invalid range/length touched memory");')
        # active ownership blocks bind, memory and Conv metadata replacement.
        self.emit('force_active=1;save_requests=memory_requests;save_conv=conv_launches;')
        self.exchange(0x75,struct.pack('<I',0x11112222),status=3);self.read(0,16,status=4);self.exchange(0x68,desc,status=4)
        self.emit('if(memory_requests!=save_requests||conv_launches!=save_conv)$fatal(1,"busy arbiter accepted new job");force_active=0;')
        self.emit('force_busy=1;');self.read(0,16,status=4);self.exchange(0x75,struct.pack('<I',0x11112222),status=3);self.emit('force_busy=0;')
        # Descriptor byte layout is independently fixed by the Python structure.
        self.emit(f"expected_descriptor=416'h{int.from_bytes(desc,'little'):0104x};")
        self.exchange(0x68,desc)
        for op,value in [(0x65,0x5678),(0x66,0x1234),(0x69,0x6789),(0x6a,0x2345),(0x6b,0x789a),(0x6c,0x3456)]:self.exchange(op,value=value)
        self.emit('save_conv=conv_launches;')
        for offset,value in [(0,0),(0,17),(1,9),(2,17),(3,0),(4,2),(5,0),(6,8),(7,1)]:
            invalid=bytearray(desc);invalid[offset]=value;self.exchange(0x68,invalid,status=3)
        self.exchange(0x68,desc[:-1],status=3);self.exchange(0x68,desc+b'x',status=3);self.exchange(0x68,desc,status=1,corrupt_tail=True)
        self.emit('if(conv_launches!=save_conv)$fatal(1,"invalid descriptor started Conv");')
        self.emit('conv_fail=1;');self.exchange(0x68,desc,status=5);self.emit('conv_fail=0;save_aborts=conv_aborts;')
        self.exchange(0x67);self.emit('idle(5);if(conv_error||conv_aborts<=save_aborts||conv_clears==0)$fatal(1,"abort/clear failed");')
        self.exchange(0x68,desc)
        # Calibration loss clears session/token; top-level bridge reset drops work.
        self.emit('memory_ready=0;generation=generation+1;idle(10);')
        self.exchange(0x64,value=0);self.exchange(0x76,value=0);self.exchange(0x77,value=0);self.read(0,16,status=9);self.exchange(0x75,struct.pack('<I',1),status=3)
        self.emit('memory_ready=1;idle(20);');self.exchange(0x64,value=1);self.exchange(0x74,value=0x1235);self.read(0,16,status=9)
        self.bind(0xabcdef01);self.exchange(0x76,value=0xef01);self.exchange(0x77,value=0xabcd)
        # Loss while a mock memory operation is outstanding: error/no payload.
        self.emit('mem_hold=1;')
        n=self.packet(0x70,struct.pack('<IHH',0,16,0));self.emit(f'send({n});idle(10);if(!mem_pending)$fatal(1,"expected outstanding read");memory_ready=0;generation=generation+1;receive(8,0,0);mem_hold=0;idle(10);')
        self.exchanges+=1;self.emit('memory_ready=1;idle(20);');self.read(0,16,status=9);self.bind()
        # Generation mismatch is checked even before the bridge completes.
        self.emit('mem_hold=1;');n=self.packet(0x70,struct.pack('<IHH',0,16,0));self.emit(f'send({n});idle(10);generation=generation+1;receive(8,0,0);mem_hold=0;idle(30);');self.exchanges+=1
        # Typed bridge failures are not published as successful data.
        for flag in ['bad_tag','bad_beats']:
            self.emit(f'{flag}=1;');self.read(0,16,status=7);self.emit(f'{flag}=0;')
        self.emit('bad_status=9;');self.read(0,16,status=7);self.emit('bad_status=0;')
        # Conv readiness loss and failed/quarantined completion.
        self.emit('conv_hold=1;');n=self.packet(0x68,desc);self.emit(f'send({n});idle(10);memory_ready=0;generation=generation+1;receive(8,0,0);conv_hold=0;idle(10);memory_ready=1;idle(20);');self.exchanges+=1
        self.read(0,16,status=9);self.bind();self.emit('conv_quarantine=1;');self.exchange(0x68,desc,status=7);self.exchange(0x67,status=7)
        # RESET clears the binding even when external calibration stays ready.
        self.emit('reset_endpoint();');self.exchange(0x64,value=1);self.exchange(0x76,value=0);self.exchange(0x77,value=0);self.read(0,16,status=9);self.bind()
        # Endpoint timeout produces no false response and requests cancellation.
        self.emit('save_cancels=memory_cancels;mem_hold=1;');n=self.packet(0x70,struct.pack('<IHH',0,16,0));self.emit(f'send({n});silence(22000);mem_hold=0;idle(40);if(memory_cancels<=save_cancels)$fatal(1,"timeout did not cancel memory");')
        self.exchange(1,value=0x5054)
        self.emit('save_aborts=conv_aborts;conv_hold=1;');n=self.packet(0x68,desc);self.emit(f'send({n});silence(22000);conv_hold=0;idle(10);if(conv_aborts<=save_aborts)$fatal(1,"timeout did not abort Conv");')
        self.exchange(1,value=0x5054)
        self.emit('arbiter_fault=1;');self.exchange(0x75,struct.pack('<I',1),status=3);self.read(0,16,status=4);self.exchange(0x67,status=7);self.emit('reset_endpoint();');self.read(0,16,status=9)
        # Raw ARM and reset remove OE before the next SYS edge.
        n=self.packet(0x50);self.emit(f'send({n});idle(10);dir=1;idle(4);if(!data_oe)$fatal(1,"expected reply OE before disarm");arm=0;#1;if(data_oe||ready)$fatal(1,"ARM drop did not remove OE");idle(5);arm=1;dir=0;idle(10);')
        self.read(0,16,status=9)
        self.emit(f'$display("PASS npu_ddr_sys exchanges=%0d generated={self.exchanges} memreq=%0d writes=%0d staged=%0d conv=%0d; stagedCRC/ranges/descriptor/session/timeout",frames,memory_requests,memory_writes,stage_writes,conv_launches);$finish;')
        self.emit('end initial begin #100000000;$fatal(1,"global timeout");end endmodule')
        return TB+'\n'.join(self.lines)+'\n',self.exchanges

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--output',type=Path,default=ROOT/'build/npu-ddr-sys-test');a=p.parse_args()
    compiler=shutil.which(a.iverilog);runtime=shutil.which(a.vvp)
    if not compiler or not runtime:p.error('Existing Icarus/vvp required; no tool installation attempted')
    a.output.mkdir(parents=True,exist_ok=True);source=ROOT/'npu/rtl/npu_ddr_sys.v';tb=a.output/'tb_npu_ddr_sys.v';text,exchanges=Generate().generate();tb.write_text(text);binary=a.output/'test.vvp';env=dict(os.environ);env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
    report={'passed':False,'hardware_access':False,'memory_model':'mock held-toggle bridge and modulo8KiB storage; shared staging2cycle SYS read; not physical DDR or Conv','exchanges':exchanges,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(tb.read_bytes()).hexdigest(),'commands':[]};logs=[]
    try:
        for cmd in [[compiler,'-g2012','-Wall','-s','tb_npu_ddr_sys','-o',str(binary),str(source),str(tb)],[runtime,str(binary)]]:
            report['commands'].append(cmd);r=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=180);logs.append(r.stdout+r.stderr)
            if r.returncode:raise RuntimeError(f'Command exited {r.returncode}: '+logs[-1])
        report['passed']=True;report['output']=logs[-1];print(logs[-1],flush=True)
    except Exception as error:report['error']=str(error);print(str(error),file=sys.stderr)
    (a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
