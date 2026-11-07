"""Independent NumPy float32 oracle, actual RTL, bounded finite profile."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,random,struct
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
def bits(f):return struct.unpack('<I',np.float32(f).tobytes())[0]
def val(u):return np.frombuffer(struct.pack('<I',u),dtype=np.float32)[0]
def bad(u):return (u>>23&255)==255 or (u>>23&255)==0 and (u&0x7fffff)!=0
def oracle(i,a,b,alpha,bias,enable):
 if any(bad(u) for u in [a,b,alpha]+([bias] if enable else [])):return 0,1
 def op(x,y,add=False):
  exact=float(x)+float(y) if add else float(x)*float(y)
  if exact!=0 and abs(exact)<float(np.finfo(np.float32).tiny):raise ValueError(3)
  with np.errstate(all='ignore'):z=np.add(x,y,dtype=np.float32) if add else np.multiply(x,y,dtype=np.float32)
  if not np.isfinite(z):raise ValueError(2)
  return z
 try:
  z=op(np.float32(i),op(val(a),val(b)));z=op(z,val(alpha))
  if enable:z=op(z,val(bias),True)
  return bits(z),0
 except ValueError as e:return 0,e.args[0]
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,abort=0,in_valid=0,out_ready=0,bias_enable=0;
reg signed[31:0] accumulator;reg[31:0] row_scale,column_scale,alpha,bias;
wire in_ready,out_valid,error;wire[31:0] result;wire[3:0] error_code;
npu_fp32_epilogue dut(clk,reset_n,abort,in_valid,in_ready,accumulator,row_scale,column_scale,alpha,bias,bias_enable,out_valid,out_ready,result,error,error_code);
integer f,scan,id,expected_error,en,n=0,t;reg[31:0] expected,saved;reg[3:0] saved_error;
task cycle;begin @(posedge clk);#1;end endtask
initial begin
 repeat(2)cycle;@(negedge clk);reset_n=1;
 f=$fopen("VECTORS","r");if(!f)$fatal(1,"vectors missing");
 while(!$feof(f))begin
  scan=$fscanf(f,"%d %h %h %h %h %h %d %h %d\n",id,accumulator,row_scale,column_scale,alpha,bias,en,expected,expected_error);
  if(scan==9)begin
   bias_enable=en;
   // Abort dominates acceptance, even with both handshake inputs high.
   if(id%97==0)begin
    @(negedge clk);abort=1;in_valid=1;out_ready=1;cycle;
    if(out_valid||in_ready)$fatal(1,"abort input dominance");
    @(negedge clk);abort=0;in_valid=0;out_ready=0;cycle;
    if(out_valid)$fatal(1,"stale output after abort");
   end
   @(negedge clk);in_valid=1;cycle;if(!dut.state&&!out_valid)$fatal(1,"not accepted");
   @(negedge clk);in_valid=0;
   // Abort each in-flight phase, then retry the same vector.
   if(id%101==0)begin
    repeat(id%4)cycle;
    @(negedge clk);abort=1;out_ready=1;in_valid=1;cycle;
    if(out_valid)$fatal(1,"abort pending dominance");
    @(negedge clk);abort=0;out_ready=0;in_valid=0;cycle;
    if(out_valid)$fatal(1,"abort stale");
    @(negedge clk);in_valid=1;cycle;@(negedge clk);in_valid=0;
   end
   if(id%107==0)begin
    cycle;@(negedge clk);reset_n=0;in_valid=1;out_ready=1;cycle;
    if(out_valid||in_ready)$fatal(1,"reset pending dominance");
    @(negedge clk);reset_n=1;in_valid=0;out_ready=0;cycle;
    if(out_valid)$fatal(1,"reset pending stale");
    @(negedge clk);in_valid=1;cycle;@(negedge clk);in_valid=0;
   end
   t=0;while(!out_valid&&t<12)begin cycle;t=t+1;end
   if(!out_valid||error_code!==expected_error||error!==(expected_error!=0)||result!==expected)
    $fatal(1,"case %0d result %h expected %h error %0d expected %0d",id,result,expected,error_code,expected_error);
   saved=result;saved_error=error_code;
   repeat(3)begin cycle;if(!out_valid||in_ready||result!==saved||error_code!==saved_error)$fatal(1,"backpressure unstable");end
   if(id%103==0)begin
    @(negedge clk);reset_n=0;in_valid=1;out_ready=1;cycle;
    if(out_valid||in_ready)$fatal(1,"reset publication dominance");
    @(negedge clk);reset_n=1;in_valid=0;out_ready=0;cycle;if(out_valid)$fatal(1,"reset stale");
   end else begin @(negedge clk);out_ready=1;cycle;@(negedge clk);out_ready=0;end
   n=n+1;
  end
 end
 $display("PASS FP32 epilogue vectors=%0d RNE/profile/backpressure/abort/reset",n);$finish;
end
initial begin #100000000;$fatal(1,"timeout");end
endmodule
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'fpga/build/npu-fp32-epilogue');p.add_argument('--iverilog',default='D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/iverilog.exe');p.add_argument('--vvp',default='D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/vvp.exe');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 rng=random.Random(0x4e23);cases=[]
 def put(i,x=0x3f800000,y=0x3f800000,z=0x3f800000,b=0,en=0):cases.append((i,x,y,z,b,en))
 for i in [0,1,-1,2**31-1,-2**31,2**24-1,2**24+1,2**24+3,-2**24-1]:
  for x in [0,0x80000000,0x3f800000,0xbf800000,0x3f000000,0x00800000,0x7f7fffff]:
   for b in [0,0x80000000,0x3f800000,0xbf800000,0x33800000,0xb3800000,0x00800000,0x80800000]:put(i,x,b=b,en=1)
 for u in [1,0x807fffff,0x7f800000,0xff800000,0x7fc00001]:
  for slot in range(4):
   v=[0x3f800000]*4;v[slot]=u;put(1,*v,1)
  put(1,b=u,en=0)
 # Exact cancellation, half ULP ties, exponent alignment boundaries, near-underflow.
 for e in range(1,255):
  x=e<<23
  put(1,x,b=x^0x80000000,en=1)
  for d in [1,23,24,25,26,31,32,63,64,100]:
   if e>d:
    for sign in [0,0x80000000]:put(1,x,b=((e-d)<<23)|sign,en=1)
 for _ in range(24000):
  i=rng.randrange(-2**31,2**31)
  def operand():return (rng.randrange(2)<<31)|(rng.randrange(1,255)<<23)|rng.getrandbits(23)
  put(i,operand(),operand(),rng.choice([0x3f800000,0x3e000000,operand()]),operand(),rng.randrange(2))
 lines=[];errors={}
 for n,c in enumerate(cases):
  expected,err=oracle(*c);errors[err]=errors.get(err,0)+1
  i,x,y,z,b,en=c;lines.append(f'{n} {i&0xffffffff:08x} {x:08x} {y:08x} {z:08x} {b:08x} {en} {expected:08x} {err}')
 (out/'vectors.txt').write_text('\n'.join(lines)+'\n');(out/'tb.v').write_text(TB.replace('VECTORS',(out/'vectors.txt').as_posix()))
 rtl=ROOT/'fpga/npu/rtl/npu_fp32_epilogue.v';env=os.environ.copy();env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');commands=[]
 for cmd in [[a.iverilog,'-g2012','-s','tb','-o',str(out/'test.vvp'),str(rtl),str(out/'tb.v')],[a.vvp,str(out/'test.vvp')]]:
  r=subprocess.run(cmd,env=env,capture_output=True,text=True);commands.append({'command':cmd,'returncode':r.returncode,'output':r.stdout+r.stderr});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(r.stdout+r.stderr);assert r.returncode==0
 (out/'result.json').write_text(json.dumps({'passed':True,'cases':len(cases),'outcome_counts':errors,'oracle':'NumPy FP32 operations with independent float64 tiny-range guard; no RTL arithmetic port','source_sha256':hashlib.sha256(rtl.read_bytes()).hexdigest(),'hardware_access':False},indent=2)+'\n')
if __name__=='__main__':main()
