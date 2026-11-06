"""Independent INT64 Conv oracle vs synchronous-RAM RTL; no device access."""
import argparse,json,os,subprocess,hashlib,itertools
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
TB=r'''
`timescale 1ns/1ps
module tb_conv_tile;
 reg clk=0,reset=1,abort=0,load_start=0,start=0;
 reg [4:0] cfg_ic=0,cfg_oh=0,cfg_ow=0;reg[3:0]cfg_oc=0;
 reg[1:0]cfg_kernel=0,cfg_stride=0;reg[5:0]cfg_input_h=0,cfg_input_w=0;
 reg first_block=0,final_block=0,upload_valid=0,upload_kind=0;
 reg[14:0]upload_address=0;reg signed[7:0]upload_data=0;
 wire upload_ready,busy,block_done,output_valid,error;wire[2:0]error_code;wire[31:0]compute_cycles;
 reg read_enable=0;reg[10:0]read_address=0;wire read_valid;wire signed[31:0]read_data;
 integer f,rc,jobs,j,i,ni,nw,no,v,first,last,ci,co,ho,wo,k,s,hi,wi,expected_cycles,timeout,expected_error;
 reg signed[31:0]expected[0:2047];
 always #5 clk=~clk;
 conv_tile_engine_8oc dut(.*);
 task tick;begin @(posedge clk);#1;end endtask
 task clear;begin @(negedge clk);abort=1;tick();@(negedge clk);abort=0;tick();if(error || busy || output_valid || read_valid)$fatal(1,"abort failed");end endtask
 task pulse_load;begin @(negedge clk);load_start=1;tick();@(negedge clk);load_start=0;end endtask
 task put;input integer kind,address,value;
 begin @(negedge clk);upload_kind=kind;upload_address=address;upload_data=value;upload_valid=1;
 if(!upload_ready)$fatal(1,"upload not ready");tick();@(negedge clk);upload_valid=0;end endtask
 task launch;begin @(negedge clk);start=1;tick();@(negedge clk);start=0;end endtask
 task wait_done;
 begin timeout=0;while(!block_done && !error && timeout<1000000)begin tick();timeout=timeout+1;end
 if(!block_done || error)$fatal(1,"compute failed job %d status %d timeout %d",j,error_code,timeout);
 end endtask
 task get;input integer address,value;
 begin @(negedge clk);read_address=address;read_enable=1;tick();
 if(!read_valid || read_data!==value)$fatal(1,"read mismatch job %d word %d got %d expected %d",j,address,read_data,value);
 @(negedge clk);read_enable=0;tick();if(read_valid || read_data!==0)$fatal(1,"read publication leaked");end endtask
 initial begin
 tick();tick();@(negedge clk);reset=0;tick();
 f=$fopen("VECTORS","r");if(!f)$fatal(1,"vectors unavailable");rc=$fscanf(f,"%d",jobs);
 for(j=0;j<jobs;j=j+1)begin
 rc=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d %d",ci,co,ho,wo,k,s,first,last,ni,nw,expected_error);if(rc!=11)$fatal(1,"bad header %d",j);
 hi=(ho-1)*s+k;wi=(wo-1)*s+k;no=co*ho*wo;
 @(negedge clk);cfg_ic=ci;cfg_oc=co;cfg_oh=ho;cfg_ow=wo;cfg_kernel=k;cfg_stride=s;cfg_input_h=hi;cfg_input_w=wi;first_block=first;final_block=last;
 pulse_load();if(error || output_valid)$fatal(1,"load failed %d",j);
 // Config is latched at load_start, not read later during upload/compute.
 cfg_ic=0;cfg_oc=0;cfg_oh=0;cfg_ow=0;cfg_kernel=0;cfg_stride=0;cfg_input_h=0;cfg_input_w=0;first_block=0;final_block=0;
 for(i=0;i<ni;i=i+1)begin rc=$fscanf(f,"%d",v);if(rc!=1)$fatal(1,"missing input");put(0,i,v);end
 for(i=0;i<nw;i=i+1)begin rc=$fscanf(f,"%d",v);if(rc!=1)$fatal(1,"missing weight");put(1,i,v);end
 if(last && !expected_error)for(i=0;i<no;i=i+1)begin rc=$fscanf(f,"%d",expected[i]);if(rc!=1)$fatal(1,"missing oracle");end
 launch();
 if(expected_error)begin
 timeout=0;while(!error && timeout<1000000)begin tick();timeout=timeout+1;end
 if(!error || error_code!=expected_error || output_valid || read_valid || read_data!==0)$fatal(1,"real accumulated overflow not rejected");clear();
 end else begin
 wait_done();
 expected_cycles=ho*wo*(2*ci*k*k+3);if(compute_cycles!==expected_cycles)$fatal(1,"cycle counter job %d got %d expected %d",j,compute_cycles,expected_cycles);
 if(output_valid!==last[0])$fatal(1,"partial result published %d",j);
 if(last)begin for(i=0;i<no;i=i+1)get(i,expected[i]); for(i=no-1;i>=0;i=i-1)get(i,expected[i]); end
 end
 end
 $fclose(f);
 // Invalid configurations, missing data, sequential upload, invalid reads.
 clear();cfg_ic=1;cfg_oc=1;cfg_oh=1;cfg_ow=1;cfg_kernel=2;cfg_stride=1;cfg_input_h=2;cfg_input_w=2;first_block=1;final_block=1;pulse_load();if(!error || error_code!=1)$fatal(1,"bad kernel accepted");
 clear();cfg_kernel=1;cfg_input_h=1;cfg_input_w=1;pulse_load();launch();if(!error || error_code!=2)$fatal(1,"missing data accepted");
 clear();pulse_load();put(0,1,3);if(!error || error_code!=2)$fatal(1,"upload hole accepted");
 clear();pulse_load();put(0,0,3);put(0,0,4);if(!error || error_code!=2)$fatal(1,"duplicate upload accepted");
 clear();first_block=0;pulse_load();if(!error || error_code!=4)$fatal(1,"no partial accepted");
 clear();@(negedge clk);read_enable=1;tick();if(!error || error_code!=4 || read_valid || read_data!==0)$fatal(1,"invalid read published");@(negedge clk);read_enable=0;
 // Abort during a nonfinal tile discards partial output and clears faults.
 clear();cfg_ic=1;cfg_oc=1;cfg_oh=1;cfg_ow=1;cfg_kernel=1;cfg_stride=1;cfg_input_h=1;cfg_input_w=1;first_block=1;final_block=0;pulse_load();put(0,0,-128);put(1,0,127);launch();tick();clear();first_block=0;pulse_load();if(!error || error_code!=4)$fatal(1,"aborted partial reused");
 // Force a 32-bit boundary only as a fault-injection test. No successful
 // numerical comparison relies on internal state or this injected value.
 clear();first_block=1;final_block=0;pulse_load();put(0,0,127);put(1,0,127);launch();wait_done();
 dut.lanes[0].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);put(1,0,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_valid || read_data!==0)$fatal(1,"overflow exposed output");clear();
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[1].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 1 overflow published");clear();cfg_oc=1;
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[2].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 2 overflow published");clear();cfg_oc=1;
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[3].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 3 overflow published");clear();cfg_oc=1;
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[4].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 4 overflow published");clear();cfg_oc=1;
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[5].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 5 overflow published");clear();cfg_oc=1;
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[6].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 6 overflow published");clear();cfg_oc=1;
 clear();cfg_oc=8;first_block=1;final_block=0;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();wait_done();
 dut.lanes[7].memory[0]=32'sh7fffffff;first_block=0;final_block=1;pulse_load();put(0,0,1);for(i=0;i<8;i=i+1)put(1,i,1);launch();timeout=0;while(!error && timeout<100)begin tick();timeout=timeout+1;end
 if(!error || error_code!=3 || output_valid || read_data!==0)$fatal(1,"lane 7 overflow published");clear();cfg_oc=1;

 // Continuous valid obeys ready; odd-OC RMW must preserve the even lane.
 clear();cfg_ic=1;cfg_oc=8;cfg_oh=1;cfg_ow=1;cfg_kernel=1;cfg_stride=1;cfg_input_h=1;cfg_input_w=1;first_block=1;final_block=1;
 pulse_load();put(0,0,-7);i=0;
 @(negedge clk);upload_valid=1;upload_kind=1;upload_address=0;upload_data=-4;
 while(i<8)begin
   if(upload_ready)begin tick();i=i+1;end else tick();
   @(negedge clk);upload_address=i;upload_data=i-4;
 end
 // start immediately on the edge that commits the last pending byte.
 upload_valid=0;start=1;tick();@(negedge clk);start=0;wait_done();
 for(i=0;i<8;i=i+1)get(i,-7*(i-4));
 // Abort an upload before its deferred write. No partial or result survives.
 clear();first_block=1;final_block=0;pulse_load();put(0,0,1);
 @(negedge clk);upload_valid=1;upload_kind=1;upload_address=0;upload_data=127;tick();
 @(negedge clk);upload_valid=0;abort=1;tick();@(negedge clk);abort=0;tick();
 if(error || busy || output_valid || read_data!==0)$fatal(1,"pending upload abort failed");
 first_block=0;pulse_load();if(!error || error_code!=4)$fatal(1,"aborted upload continued");clear();cfg_oc=1;
 // Start/load during active compute is rejected and invalidates partials.
 first_block=1;final_block=1;pulse_load();put(0,0,1);put(1,0,1);launch();launch();if(!error || error_code!=4 || output_valid)$fatal(1,"busy start accepted");clear();
 $display("PASS conv_tile_8oc jobs=%0d independent INT64, maximum shapes, partial IC blocks, latch/holes/abort/overflow",jobs);$finish;
 end
 initial begin #2000000000;$fatal(1,"global timeout");end
endmodule
'''
def make_vectors(path,quick=False):
 rng=np.random.default_rng(20261106);jobs=[]
 configs=list(itertools.product((1,3),(1,2),(1,2,16),tuple(range(1,9)),(1,2,16),(1,3,16)))
 if quick:configs=[(1,1,1,1,1,1),(3,2,2,3,2,3),(3,2,16,8,16,16)]
 for k,s,ic,oc,oh,ow in configs:
  ih=(oh-1)*s+k;iw=(ow-1)*s+k
  x=rng.integers(-128,128,(ic,ih,iw),dtype=np.int16).astype(np.int8);w=rng.integers(-128,128,(oc,ic,k,k),dtype=np.int16).astype(np.int8)
  patches=np.lib.stride_tricks.sliding_window_view(x,(k,k),axis=(1,2))[:,::s,::s]
  y=np.einsum('iyxkl,oikl->oyx',patches.astype(np.int64),w.astype(np.int64),optimize=False)
  jobs.append((k,s,ic,oc,oh,ow,1,1,x,w,y,0))
 # Accumulate several differently sized IC blocks, retaining only same shape.
 acc=None
 for idx,ic in enumerate([16,16,3]):
  k,s,oc,oh,ow=3,2,3,2,5;ih=(oh-1)*s+k;iw=(ow-1)*s+k
  x=rng.integers(-128,128,(ic,ih,iw),dtype=np.int16).astype(np.int8);w=rng.integers(-128,128,(oc,ic,k,k),dtype=np.int16).astype(np.int8)
  patches=np.lib.stride_tricks.sliding_window_view(x,(k,k),axis=(1,2))[:,::s,::s]
  y=np.einsum('iyxkl,oikl->oyx',patches.astype(np.int64),w.astype(np.int64),optimize=False);acc=y if acc is None else acc+y
  jobs.append((k,s,ic,oc,oh,ow,int(idx==0),int(idx==2),x,w,acc.copy(),0))
 # Real signed-boundary overflow after many legal IC blocks (no state injection).
 if not quick:
  for weight in (-128,127):
   x=np.full((16,3,3),-128,dtype=np.int8);w=np.full((1,16,3,3),weight,dtype=np.int8);delta=int(-128)*weight*144;total=0;idx=0
   while True:
    total+=delta;fault=3 if total<-(2**31) or total>=2**31 else 0
    jobs.append((3,1,16,1,1,1,int(idx==0),int(bool(fault)),x,w,np.array([[[total]]],dtype=np.int64),fault));idx+=1
    if fault:break
 with path.open('w') as f:
  f.write(str(len(jobs))+'\n')
  for k,s,ic,oc,oh,ow,first,last,x,w,y,fault in jobs:
   assert fault or np.all((y>=-2**31)&(y<2**31));f.write(f'{ic} {oc} {oh} {ow} {k} {s} {first} {last} {x.size} {w.size} {fault}\n')
   f.write(' '.join(map(str,x.ravel().tolist()))+'\n');f.write(' '.join(map(str,w.ravel().tolist()))+'\n')
   if last and not fault:f.write(' '.join(map(str,y.ravel().tolist()))+'\n')
 return len(jobs)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--quick',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.output=a.output.resolve()
 vectors=a.output/'vectors.txt';count=make_vectors(vectors,a.quick);tb=a.output/'tb_conv_tile.v';tb.write_text(TB.replace('VECTORS',vectors.as_posix()));binary=a.output/'conv_tile.vvp';env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');logs=[]
 result={'passed':False,'jobs':count,'scope':'RTL simulation only; no hardware'}
 (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 try:
  for cmd in [[a.iverilog,'-g2012','-Wall','-s','tb_conv_tile','-o',str(binary),str(ROOT/'npu/rtl/conv_tile_engine_8oc.v'),str(tb)],[a.vvp,str(binary)]]:
   r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=300);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
  result={'passed':True,'jobs':count,'scope':'RTL simulation only; no hardware','source_sha256':hashlib.sha256((ROOT/'npu/rtl/conv_tile_engine_8oc.v').read_bytes()).hexdigest(),'vector_sha256':hashlib.sha256(vectors.read_bytes()).hexdigest(),'output':logs[-1]}
 except Exception as exc:
  result['error']=str(exc);raise
 finally:
  (a.output/'run.log').write_text('\n'.join(logs))
  (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(logs[-1])
if __name__=='__main__':main()
