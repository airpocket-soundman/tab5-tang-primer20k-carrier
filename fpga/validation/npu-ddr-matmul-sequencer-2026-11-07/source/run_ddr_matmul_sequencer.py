"""Standalone descriptor oracle and hostile fake-loader test, no board access."""
from pathlib import Path
import random
import argparse,itertools,json,subprocess,os,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
def descriptors(m,k,n,ab,ap,bb,bp,cb,cp):
 for nb in range(0,n,8):
  for mb in range(0,m,256):
   for kb in range(0,k,16):
    yield [min(16,k-kb),min(8,n-nb),(min(256,m-mb)+15)//16,16,int(kb==0),int(kb+16>=k),(m+15)//16,16,mb//16,0,ab+kb*ap,16,ap,bb+nb*bp+kb,bp,cb+nb*cp+mb*4,64,cp,1]
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,abort=0,clear=0,memory_ready=1,job_valid=0,out_ready=0;
reg[31:0] job_m,job_k,job_n,job_a_base,job_a_pitch,job_b_base,job_b_pitch,job_c_base,job_c_pitch;
wire job_ready,busy,out_valid,result_valid,error,quarantined;wire[3:0] error_code;
wire[31:0] accepted_tiles,completed_tiles,expected_tiles;
wire descriptor_valid;reg descriptor_ready=0;
wire[4:0] cfg_ic,cfg_oh,cfg_ow;wire[3:0] cfg_oc;wire[1:0] cfg_kernel,cfg_stride;
wire first_block,final_block;wire[15:0] input_full_h,input_full_w;
wire signed[31:0] input_origin_y,input_origin_x;
wire[31:0] input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch;
wire output_tail_owned;reg tile_busy=0,tile_done=0,tile_error=0,tile_quarantined=0,tile_result_valid=0;wire tile_abort;
npu_ddr_matmul_sequencer #(.TILE_TIMEOUT(80),.DRAIN_TIMEOUT(12))dut(.*);
integer mode=0,cycle_count=0,timer=0,sticky=0,seen=0;reg saved_final=0;
always @(negedge clk)begin
 cycle_count=cycle_count+1;
 descriptor_ready=mode!=6&&(cycle_count%5!=0)&&(cycle_count%7!=0);
 if(!reset_n)begin tile_busy=0;tile_done=0;tile_error=0;tile_quarantined=0;tile_result_valid=0;timer=0;sticky=0;seen=0;end
 else if(tile_abort&&mode!=3)begin
  tile_busy=0;timer=0;
  if(sticky>0)begin sticky=sticky-1;if(sticky==0)tile_done=0;end
 end else if(tile_busy)begin
  if(mode!=3)begin
   timer=timer-1;
   if(timer==0)begin tile_busy=0;tile_done=1;sticky=3;tile_result_valid=saved_final&&mode!=5;
    if(mode==1)tile_error=1;if(mode==2)tile_quarantined=1;
   end
  end
 end else if(tile_done)begin sticky=sticky-1;if(sticky==0)tile_done=0;end
end
integer observed;
reg stalled=0;reg[511:0] saved_descriptor;
wire[511:0] descriptor_bundle={cfg_ic,cfg_oc,cfg_oh,cfg_ow,cfg_kernel,cfg_stride,first_block,final_block,input_full_h,input_full_w,input_origin_y,input_origin_x,input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch,output_tail_owned};
always @(posedge clk)begin
 if(!reset_n)stalled<=0;
 else begin
  if(descriptor_valid&&!descriptor_ready)begin
   if(stalled&&descriptor_bundle!==saved_descriptor)$fatal(1,"descriptor changed under backpressure");
   saved_descriptor<=descriptor_bundle;stalled<=1;
  end else stalled<=0;
 end
end
integer f,scan,jid,nexp,expected_error,jobs=0,total=0,idx,i,t;reg[31:0] ex[0:18];
reg checking=0;reg[31:0] hold_count;
always @(posedge clk)begin
 if(reset_n&&descriptor_valid&&descriptor_ready)begin
  if(checking)begin
   $fwrite(observed,"%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n",jid,cfg_ic,cfg_oc,cfg_oh,cfg_ow,first_block,final_block,input_full_h,input_full_w,input_origin_y,input_origin_x,input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch,output_tail_owned);
   scan=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",ex[0],ex[1],ex[2],ex[3],ex[4],ex[5],ex[6],ex[7],ex[8],ex[9],ex[10],ex[11],ex[12],ex[13],ex[14],ex[15],ex[16],ex[17],ex[18]);
   if(scan!=19)$fatal(1,"missing expected descriptor");
   if(cfg_ic!==ex[0]||cfg_oc!==ex[1]||cfg_oh!==ex[2]||cfg_ow!==ex[3]||first_block!==ex[4][0]||final_block!==ex[5][0]||input_full_h!==ex[6]||input_full_w!==ex[7]||input_origin_y!==ex[8]||input_origin_x!==ex[9]||input_base!==ex[10]||input_row_pitch!==ex[11]||input_channel_pitch!==ex[12]||weight_base!==ex[13]||weight_oc_stride!==ex[14]||output_base!==ex[15]||output_row_pitch!==ex[16]||output_channel_pitch!==ex[17]||output_tail_owned!==ex[18][0]||cfg_kernel!==1||cfg_stride!==1)
    $fatal(1,"descriptor mismatch job%0d index%0d ic%0d oc%0d oh%0d input%h weight%h output%h",jid,idx,cfg_ic,cfg_oc,cfg_oh,input_base,weight_base,output_base);
  end
  if(tile_busy||tile_done)$fatal(1,"reuse active/sticky loader");
  tile_busy<=1;timer<=2+(cycle_count%4);saved_final<=final_block;seen<=seen+1;idx<=idx+1;
 end
 if(reset_n&&result_valid&&busy)$fatal(1,"early publication");
end
task cycle;begin @(posedge clk);#1;end endtask
task reset_all;begin
 @(negedge clk);reset_n=0;abort=0;clear=0;job_valid=0;out_ready=0;memory_ready=1;repeat(3)cycle;
 @(negedge clk);reset_n=1;cycle;
end endtask
task launch;begin
 t=0;while(!job_ready&&t<20)begin cycle;t=t+1;end
 if(!job_ready)$fatal(1,"job not ready");
 @(negedge clk);job_valid=1;cycle;@(negedge clk);job_valid=0;
end endtask
task wait_output;begin
 t=0;while(!out_valid&&t<2000000)begin cycle;t=t+1;end
 if(!out_valid)$fatal(1,"output timeout state%0d",dut.state);
end endtask
task consume;begin
 hold_count=completed_tiles;repeat(4)begin cycle;if(!out_valid||job_ready||completed_tiles!==hold_count)$fatal(1,"output backpressure");end
 @(negedge clk);out_ready=1;cycle;@(negedge clk);out_ready=0;
end endtask
initial begin
 reset_all;observed=$fopen("OBSERVED","w");f=$fopen("JOBS","r");if(!f)$fatal(1,"jobs missing");
 while(!$feof(f))begin
  scan=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d %d %d\n",jid,job_m,job_k,job_n,job_a_base,job_a_pitch,job_b_base,job_b_pitch,job_c_base,job_c_pitch,nexp,expected_error);
  if(scan==12)begin
   idx=0;checking=1;launch;wait_output;checking=0;
   if(error_code!==expected_error||error!==(expected_error!=0))$fatal(1,"job%0d error%0d expected%0d",jid,error_code,expected_error);
   if(expected_error==0)begin
    if(!result_valid||idx!=nexp||accepted_tiles!=nexp||completed_tiles!=nexp||expected_tiles!=nexp)$fatal(1,"counts/publication job%0d",jid);
   end else if(result_valid||accepted_tiles!=0||idx!=0)$fatal(1,"invalid job published or issued");
   consume;
   if(expected_error!=0)begin
    if(job_ready)$fatal(1,"error not latched");@(negedge clk);clear=1;cycle;@(negedge clk);clear=0;
   end
   jobs=jobs+1;total=total+idx;
  end
 end
 // Hostile loader cases, independent of descriptor file.
 job_m=197;job_k=17;job_n=9;job_a_base=0;job_a_pitch=208;job_b_base=1048576;job_b_pitch=32;job_c_base=2097152;job_c_pitch=832;
 for(i=1;i<=8;i=i+1)begin
  mode=i;reset_all;idx=0;launch;
  if(i==4)begin wait(accepted_tiles==1);@(negedge clk);abort=1;cycle;@(negedge clk);abort=0;end
  if(i==7)begin repeat(5)cycle;@(negedge clk);memory_ready=0;end
  if(i==8)begin repeat(5)cycle;@(negedge clk);abort=1;job_valid=1;out_ready=1;cycle;@(negedge clk);abort=0;job_valid=0;out_ready=0;end
  wait_output;
  if(!error||result_valid)$fatal(1,"faultmode%0d published numeric",i);
  if(i==1&&error_code!=4)$fatal(1,"loader error code");
  if(i==2&&(!quarantined||error_code!=8))$fatal(1,"quarantine lost");
  if(i==3&&(!quarantined||error_code!=6))$fatal(1,"timeout drain quarantine");
  if((i==4||i==8)&&error_code!=5)$fatal(1,"abort lost");
  if(i==5&&error_code!=9)$fatal(1,"missing final result");
  if(i==6&&error_code!=6)$fatal(1,"backpressure timeout");
  if(i==7&&error_code!=7)$fatal(1,"calibration loss");
  consume;
  if(i==2||i==3)begin @(negedge clk);clear=1;cycle;@(negedge clk);clear=0;if(job_ready||!quarantined)$fatal(1,"quarantine cleared without reset");end
 end
 // Recover an aborted validation without resetting the sequencer: no stale multiplier result.
 mode=0;@(negedge clk);clear=1;cycle;@(negedge clk);clear=0;
 launch;wait_output;if(error||!result_valid||completed_tiles!=4)$fatal(1,"restart after cleared validation abort");consume;
 // Validation reset/abort must not allow an old multiply to poison next job.
 mode=0;reset_all;launch;repeat(10)cycle;@(negedge clk);reset_n=0;cycle;@(negedge clk);reset_n=1;cycle;
 if(out_valid||result_valid||accepted_tiles)$fatal(1,"reset stale");
 launch;wait_output;if(error||!result_valid||completed_tiles!=4)$fatal(1,"restart after reset");consume;
 // Stale done must not count as completion or launch a tile.
 reset_all;tile_done=1;sticky=12;launch;repeat(8)cycle;if(accepted_tiles)$fatal(1,"stale done accepted");
 wait_output;if(error||completed_tiles!=4)$fatal(1,"sticky done recovery");consume;
 // A published result becomes invalid on calibration loss.
 reset_all;launch;wait_output;if(!result_valid)$fatal(1,"missing result");
 @(negedge clk);memory_ready=0;cycle;if(result_valid||!error||error_code!=7)$fatal(1,"old result survived calibration loss");
 // Abort dominates simultaneous new job acceptance.
 reset_all;@(negedge clk);abort=1;job_valid=1;out_ready=1;cycle;if(busy||accepted_tiles||out_valid)$fatal(1,"abort input priority");
 @(negedge clk);abort=0;job_valid=0;out_ready=0;
 $display("PASS DDR MatMul sequencer jobs=%0d descriptors=%0d plus8faults/reset/sticky/backpressure",jobs,total);$finish;
end
initial begin #2000000000;$fatal(1,"watchdog");end
endmodule
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'fpga/build/npu-ddr-matmul-sequencer');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);jobs=[]
 for m,k,n in itertools.product([1,197,256,257],[1,16,17,192,768],[1,8,9,197,768]):
  ap=(m+15)//16*16+16;bp=(k+15)//16*16+16;cp=((m+15)//16*16)*4+16
  jobs.append((m,k,n,0,ap,1048576,bp,4194304,cp,0))
 # Capacity edge valid then malformed dimensions/pitches/ranges/overlaps.
 jobs +=[(1,1,1,0,16,16,16,134217664,64,0),(0,1,1,0,16,1024,16,2048,64,1),(65536,1,1,0,65536,1024,16,2097152,262144,1),(1,0,1,0,16,1024,16,2048,64,1),(1,1,0,0,16,1024,16,2048,64,1),(1,1,1,1,16,1024,16,2048,64,2),(197,1,1,0,192,1024,16,2048,832,2),(1,17,1,0,16,1024,16,2048,64,2),(197,1,1,0,208,1024,16,2048,768,2),(1,1,1,0,16,1024,16,134217680,64,2),(1,1,1,0,16,0,16,2048,64,3),(1,1,1,0,16,1024,16,0,64,3),(1,1,1,0,16,1024,16,1024,64,3),(1,1,1,0,4294967280,1024,16,2048,64,2),(0xffffffff,0xffffffff,0xffffffff,0,16,1024,16,2048,64,1)]
 lines=[];total=0
 for j,x in enumerate(jobs):
  m,k,n,ab,ap,bb,bp,cb,cp,err=x;desc=list(descriptors(*x[:-1])) if not err else [];total+=len(desc);lines.append(' '.join(map(str,[j,*x[:-1],len(desc),err])));lines.extend(' '.join(map(str,d)) for d in desc)
 (out/'jobs.txt').write_text('\n'.join(lines)+'\n');(out/'tb.v').write_text(TB.replace('JOBS',(out/'jobs.txt').as_posix()).replace('OBSERVED',(out/'observed.txt').as_posix()))
 tool=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin');env=os.environ.copy();env['PATH']=str(tool)+os.pathsep+env['PATH'];rtl=ROOT/'fpga/npu/rtl/npu_ddr_matmul_sequencer.v';commands=[]
 for cmd in [[str(tool/'iverilog.exe'),'-g2012','-s','tb','-o',str(out/'test.vvp'),str(rtl),str(out/'tb.v')],[str(tool/'vvp.exe'),str(out/'test.vvp')]]:
  r=subprocess.run(cmd,capture_output=True,text=True,env=env);commands.append({'command':cmd,'returncode':r.returncode,'output':r.stdout+r.stderr});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(r.stdout+r.stderr);assert r.returncode==0

 # Numeric reconstruction from ACTUAL emitted descriptors for selected jobs.
 # Dense NumPy A@B is independent of the address-decoding reference below.
 selected={(1,17,9),(197,192,197),(257,17,9),(256,16,8)}
 rng=np.random.default_rng(0x4e24);numeric={};observed={}
 for line in (out/'observed.txt').read_text().splitlines():
  values=list(map(int,line.split()));observed.setdefault(values[0],[]).append(values[1:])
 for j,x in enumerate(jobs):
  m,k,n,ab,ap,bb,bp,cb,cp,err=x
  if (m,k,n) not in selected:continue
  mp=(m+15)//16*16;kp=(k+15)//16*16
  A=rng.integers(-127,128,(k,mp),dtype=np.int32);A[:,m:]=0
  B=rng.integers(-127,128,(n,kp),dtype=np.int32);B[:,k:]=0
  C=np.full((n,mp),-1234567,dtype=np.int64);acc=None
  for d in observed[j]:
   ic,oc,oh,ow,first,final,fh,fw,oy,ox,ib,ip,icp,wb,wcp,ob,op,ocp,tail=d
   if first:acc=np.zeros((oc,oh*ow),dtype=np.int64)
   AA=np.empty((ic,oh*ow),dtype=np.int64);WW=np.empty((oc,ic),dtype=np.int64)
   for z in range(ic):
    for y in range(oh):
     for xx in range(ow):
      off=ib+z*icp+(oy+y)*ip+ox+xx-ab;ci,mi=divmod(off,ap);AA[z,y*ow+xx]=A[ci,mi]
   for z in range(oc):
    for kk in range(ic):
     ni,ki=divmod(wb+z*wcp+kk-bb,bp);WW[z,kk]=B[ni,ki]
   acc+=WW@AA
   if final:
    for z in range(oc):
     for y in range(oh):
      for xx in range(ow):
       ni,mi=divmod(ob+z*ocp+y*op+xx*4-cb,cp);assert mi%4==0;C[ni,mi//4]=acc[z,y*ow+xx]
  expected=B[:,:k].astype(np.int64)@A[:,:m].astype(np.int64)
  assert np.array_equal(C[:,:m],expected) and np.all(C[:,m:]==0)
  numeric[f'{m}x{k}x{n}']={'passed':True,'descriptors':len(observed[j]),'outputs':m*n,'padding_zero':True}
 (out/'result.json').write_text(json.dumps({'passed':True,'jobs':len(jobs),'descriptors':total,'numeric_address_reconstruction':numeric,'source_sha256':hashlib.sha256(rtl.read_bytes()).hexdigest(),'hardware_access':False,'scope':'Actual sequencer descriptors vs independent nested-loop address oracle; hostile fake loader, NOT integrated numeric kernel'},indent=2)+'\n')
if __name__=='__main__':main()
