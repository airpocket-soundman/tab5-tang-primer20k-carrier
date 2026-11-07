"""Isolated asynchronous RX phase sweep; production RTL is never edited.
Compare current raw DATA sampling with DATA2FF aligned to cs[1]. Endpoint real
LINKv2 CRC/header/payload+packet RAM are exercised; no DDR/device/PHY access.
"""
import argparse,collections,difflib,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def crc(data,seed=0xffff):
 for byte in data:
  seed^=byte<<8
  for _ in range(8):seed=((seed<<1)^0x1021)&65535 if seed&0x8000 else(seed<<1)&65535
 return seed
TB=r'''
`timescale 1ps/1ps
module tb;
 reg clk=0;always begin #18518;clk=1;#18519;clk=0;end
 reg reset_n=0,arm=0,bus_clk=0,dir=0;reg[7:0]data_i=0;
 wire[7:0]bo,ao;wire be,ae,br,ar;
 PORTS
 integer f,rc,tests,id,freq,mode,phase,delay_data,half,n,j,k,waited,scount_b,scount_a,bad_b,bad_a,first_b,first_a,bstat,astat,bh,ah,packet_b,packet_a;
 reg[7:0]frame[0:2063],rb[0:7],ra[0:7];reg recording=0;
 function[15:0]crcbyte;input[15:0]c;input[7:0]b;reg[15:0]v;integer z;begin v=c^{b,8'd0};for(z=0;z<8;z=z+1)v=v[15]?(v<<1)^16'h1021:v<<1;crcbyte=v;end endfunction
 reg[15:0]bc,ac;
 always @(posedge clk)if(recording&&reset_n&&arm)begin
  if(baseline.state==0&&baseline.rise&&!dir&&!baseline.ds[1])begin if(scount_b>=n||data_i!==frame[scount_b])begin bad_b=bad_b+1;if(first_b<0)first_b=scount_b;end scount_b=scount_b+1;end
  if(aligned.state==0&&aligned.rise&&!dir&&!aligned.ds[1])begin if(scount_a>=n||aligned.data_capture!==frame[scount_a])begin bad_a=bad_a+1;if(first_a<0)first_a=scount_a;end scount_a=scount_a+1;end
 end
 initial begin
 f=$fopen("VECTORS","r");rc=$fscanf(f,"%d",tests);
 for(id=0;id<tests;id=id+1)begin
  rc=$fscanf(f,"%d %d %d %d %d %d",freq,mode,phase,delay_data,half,n);if(rc!=6)$fatal(1,"vector header");
  for(j=0;j<n;j=j+1)begin rc=$fscanf(f,"%d",k);frame[j]=k;end
  recording=0;reset_n=0;arm=0;bus_clk=0;dir=0;data_i=8'h7e;repeat(5)@(posedge clk);#123;reset_n=1;arm=1;repeat(5)@(posedge clk);
  scount_b=0;scount_a=0;bad_b=0;bad_a=0;first_b=-1;first_a=-1;recording=1;
  @(posedge clk);#(phase);if(mode==0)data_i=frame[0];
  #(half);
  for(j=0;j<n;j=j+1)begin
   bus_clk=1;
   if(mode==1)begin #(delay_data);data_i=frame[j];#(half-delay_data);end else #(half);
   bus_clk=0;
   if(mode==0)begin #(delay_data);data_i=j+1<n?frame[j+1]:8'h7e;#(half-delay_data);end else #(half);
  end
  #500000;recording=0;packet_b=1;packet_a=1;
  for(j=0;j<n-18;j=j+1)begin if(baseline.packet[j]!==frame[j+16])packet_b=0;if(aligned.packet[j]!==frame[j+16])packet_a=0;end
  dir=1;waited=0;while((!br||!ar)&&waited<100)begin #37037;waited=waited+1;end
  bstat=255;astat=255;bh=0;ah=0;
  for(j=0;j<8;j=j+1)begin
   #1000000;rb[j]=br?bo:8'hxx;ra[j]=ar?ao:8'hxx;bus_clk=1;#1000000;bus_clk=0;
  end
  if(rb[0]===8'h5a)bstat=rb[1];if(ra[0]===8'h5a)astat=ra[1];bc=16'hffff;ac=16'hffff;
  for(j=0;j<6;j=j+1)begin bc=crcbyte(bc,rb[j]);ac=crcbyte(ac,ra[j]);end
  if({rb[7],rb[6]}===bc)bh=1;if({ra[7],ra[6]}===ac)ah=1;
  $display("CASE %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",id,freq,mode,phase,delay_data,n,bstat,astat,bh,ah,scount_b,scount_a,bad_b,bad_a,packet_b,packet_a);
  dir=0;#2000000;
 end
 $display("DONE %0d",tests);$finish;
 end
 initial begin #10000000000000;$fatal(1,"global timeout");end
endmodule
'''
def ports(module,instance,prefix):
 return f'''{module} #(.TIMEOUT(27000000)) {instance}(.clk(clk),.reset_n(reset_n),.arm(arm),.bus_clk(bus_clk),.dir(dir),.data_i(data_i),.data_o({prefix}o),.data_oe({prefix}e),.ready({prefix}r),.memory_ready(1'b1),.generation(16'd0),.arbiter_fault(1'b0),.arbiter_active(1'b0),.conv_start_ready(1'b1),.conv_busy(1'b0),.conv_done(1'b0),.conv_error(1'b0),.conv_quarantined(1'b0),.conv_error_code(4'd0),.kernel_cycles(32'd0),.ddr_wait_cycles(32'd0),.total_cycles(32'd0),.done_t(1'b0),.r_tag(24'd0),.r_status(4'd0),.r_beats(16'd0),.r_data(128'd0));'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--quick',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 original=(ROOT/'npu/rtl/npu_ddr_sys.v').read_bytes();source=original.decode().replace("\r\n","\n");baseline=source.replace('module npu_ddr_sys #','module npu_ddr_sys_baseline #',1);candidate=source.replace('module npu_ddr_sys #','module npu_ddr_sys_aligned #',1)
 if 'parameter REQUEST_DATA_PIPELINE' not in source:
  i=candidate.index(' localparam');candidate=candidate[:i]+candidate[i:].replace('data_i','data_capture');candidate=candidate.replace('reg[3:0] state;reg[2:0] cs;', 'reg[7:0] data_meta,data_capture;reg[3:0] state;reg[2:0] cs;').replace('state<=RX;cs<=0;','state<=RX;data_meta<=0;data_capture<=0;cs<=0;').replace('cs<={cs[1:0],bus_clk};','data_meta<=data_i;data_capture<=data_meta;cs<={cs[1:0],bus_clk};')

 (out/'baseline.v').write_text(baseline,newline='\n');(out/'aligned.v').write_text(candidate,newline='\n');(out/'candidate.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True),candidate.replace('module npu_ddr_sys_aligned #','module npu_ddr_sys #',1).splitlines(True),fromfile='production',tofile='isolated-data2ff')))
 frequencies=[500000,1000000,2000000,5000000,8000000,10000000]if a.quick else[500000,1000000,2000000,4000000,5000000,8000000,10000000,12000000,14000000,16000000,20000000];phases=range(0,37,5)if a.quick else range(37);payloads=[64]if a.quick else[16,256,2032];delays=[2000]if a.quick else[0,2000,5000];cases=[]
 for freq in frequencies:
  for mode in (0,1):
   for phase in phases:
    for delay in delays:
     for size in payloads:
      payload=(0x1000).to_bytes(4,'little')+size.to_bytes(2,'little')+bytes(2)+bytes((j*37+(j>>3)*11+phase*13)&255 for j in range(size));h=bytes([0xa5,0x71,(len(cases)*19)&255,2])+len(payload).to_bytes(2,'little');hc=crc(h);tail=crc(payload,hc);frame=h+hc.to_bytes(2,'little')+payload+tail.to_bytes(2,'little');cases.append((freq,mode,phase*1001+137,delay,round(5e11/freq),frame))
 vectors=out/'vectors.txt'
 with vectors.open('w')as f:
  f.write(str(len(cases))+'\n')
  for freq,mode,phase,delay,half,frame in cases:f.write(f'{freq} {mode} {phase} {delay} {half} {len(frame)}\n'+' '.join(map(str,frame))+'\n')
 port_text=ports('npu_ddr_sys_baseline','baseline','b')+ports('npu_ddr_sys_aligned','aligned','a')
 if 'parameter REQUEST_DATA_PIPELINE' in source:port_text=port_text.replace('npu_ddr_sys_baseline #(.TIMEOUT(27000000))','npu_ddr_sys_baseline #(.TIMEOUT(27000000),.REQUEST_DATA_PIPELINE(0))').replace('npu_ddr_sys_aligned #(.TIMEOUT(27000000))','npu_ddr_sys_aligned #(.TIMEOUT(27000000),.REQUEST_DATA_PIPELINE(1))')
 tb=out/'tb.v';tb.write_text(TB.replace('PORTS',port_text).replace('VECTORS',vectors.as_posix()));exe=out/'test.vvp';env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');logs=[];commands=[];result={'passed':False,'cases':len(cases),'scope':'Ideal digital phase sweep only; no metastability/PHY/jumper/device claim','production_parameter_proof':'parameter REQUEST_DATA_PIPELINE'in source,'production_sha256':hashlib.sha256(original).hexdigest(),'candidate_sha256':hashlib.sha256(candidate.encode()).hexdigest()};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 try:
  for cmd in [[a.iverilog,'-g2012','-Wall','-s','tb','-o',str(exe),str(out/'baseline.v'),str(out/'aligned.v'),str(tb)],[a.vvp,str(exe)]]:
   r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=1800);commands.append({'command':cmd,'returncode':r.returncode});logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1][-4000:]
  rows=[];summary={}
  for line in logs[-1].splitlines():
   if not line.startswith('CASE '):continue
   values=list(map(int,line.split()[1:]));keys=['id','frequency_hz','mode','phase_ps','data_delay_ps','wire_bytes','baseline_status','aligned_status','baseline_reply_crc','aligned_reply_crc','baseline_samples','aligned_samples','baseline_bad_bytes','aligned_bad_bytes','baseline_packet_equal','aligned_packet_equal'];row=dict(zip(keys,values));row['baseline_pass']=row['baseline_status']==9 and row['baseline_reply_crc']==1 and row['baseline_samples']==row['wire_bytes']and row['baseline_bad_bytes']==0 and row['baseline_packet_equal']==1;row['aligned_pass']=row['aligned_status']==9 and row['aligned_reply_crc']==1 and row['aligned_samples']==row['wire_bytes']and row['aligned_bad_bytes']==0 and row['aligned_packet_equal']==1;rows.append(row)
  assert len(rows)==len(cases)
  for freq in frequencies:
   for mode in (0,1):
    group=[r for r in rows if r['frequency_hz']==freq and r['mode']==mode];summary[f'{freq}/{"positive_fall_launch"if mode==0 else"inverted_rise_launch"}']={'cases':len(group),'baseline_pass':sum(r['baseline_pass']for r in group),'aligned_pass':sum(r['aligned_pass']for r in group)}
  positive=[r for r in rows if r['mode']==0];assert all(r['aligned_pass']for r in positive if r['frequency_hz']<=10000000),'alignedpositive<=10MHzfailed';assert all(r['baseline_pass']for r in positive if r['frequency_hz']<=2000000),'legacypositive<=2MHzregression';assert any(not r['baseline_pass']for r in positive if r['frequency_hz']==5000000),'5MHzlatenextbytefaultnotreproduced'
  if not a.quick:assert any(not r['aligned_pass']for r in positive if r['frequency_hz']>=14000000),'aliasceilingnotexercised'
  assert (ROOT/'npu/rtl/npu_ddr_sys.v').read_bytes()==original,'productionchangedconcurrently';result.update(passed=True,summary=summary);(out/'cases.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(summary,indent=2))
 finally:(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');(out/'run.log').write_text('\n'.join(logs));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
if __name__=='__main__':main()

