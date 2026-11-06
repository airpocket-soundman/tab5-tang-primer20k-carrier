"""DDR Conv scheduler oracle with fake tagged adapter/staging RAM; no board IO."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
TB=r'''
`timescale 1ns/1ps
module tb_ddr_loader;
 localparam CAP=262144;
 reg clk=0,reset_n=0,memory_ready=0,start=0,abort=0,clear=0;
 wire start_ready,busy,block_done,result_valid,error,quarantined;
 reg[4:0]cfg_ic=0,cfg_oh=0,cfg_ow=0;reg[3:0]cfg_oc=0;reg[1:0]cfg_kernel=0,cfg_stride=0;reg first_block=0,final_block=0;
 reg[15:0]input_full_h=0,input_full_w=0;reg signed[31:0]input_origin_y=0,input_origin_x=0;
 reg[31:0]input_base=0,input_row_pitch=0,input_channel_pitch=0,weight_base=0,weight_oc_stride=0,output_base=0,output_row_pitch=0,output_channel_pitch=0;reg output_tail_owned=0;
 wire[3:0]error_code,mem_status;wire[31:0]total_cycles,ddr_wait_cycles,read_beats,write_beats,kernel_cycles;
 wire req_t,cancel_t;wire[1:0]h_op;wire[31:0]h_addr,h_arg;wire[15:0]h_beats;wire[23:0]h_tag;
 reg done_t=0;reg[23:0]r_tag=0;reg[3:0]r_status=0;reg[15:0]r_beats=0;
 wire w_we;wire[7:0]w_addr,r_addr;wire[127:0]w_data;reg[127:0]r_data=0;
 reg[7:0]mem[0:CAP-1],shadow[0:CAP-1];reg[127:0]write_stage[0:255],read_stage[0:255];
 integer actor=0,mode=0,active_mode=0,delay_count=0,beat=0,requests=0,reads=0,writes=0;
 reg req_ref=0,cancel_ref=0;reg[1:0]saved_op;reg[31:0]saved_addr,saved_arg;reg[15:0]saved_beats;reg[23:0]saved_tag;reg[3:0]pending_status;reg[15:0]pending_beats;reg bad_sent=0;
 integer z,t;
 always #18.5 clk=~clk;
 npu_ddr_tile_loader #(.CAPACITY(CAP),.MEMORY_TIMEOUT(200),.DRAIN_TIMEOUT(100)) dut(.*);
 always @(posedge clk)begin
  if(w_we)write_stage[w_addr]<=w_data;r_data<=read_stage[r_addr];
  if(!reset_n)begin actor<=0;req_ref<=0;cancel_ref<=0;done_t<=0;r_tag<=0;r_status<=0;r_beats<=0;requests<=0;reads<=0;writes<=0;mode<=0;bad_sent<=0;end
  else begin
   if(actor!=0 && {h_op,h_addr,h_beats,h_arg,h_tag}!={saved_op,saved_addr,saved_beats,saved_arg,saved_tag})$fatal(1,"metadata changed before adapter drain");
   if(actor!=0 && req_t!=req_ref)$fatal(1,"overlapping memory request");
   if(actor!=0 && cancel_t!=cancel_ref && active_mode!=3 && active_mode!=7)begin
    cancel_ref<=cancel_t;pending_status<=8;pending_beats<=beat;actor<=3;
   end else case(actor)
    0:if(req_t!=req_ref)begin
     if(h_addr[3:0]!=0 || h_beats<1 || h_beats>256 || {1'b0,h_addr}+h_beats*16>CAP || h_op>1)$fatal(1,"invalid adapter request addr%h beats%d op%d",h_addr,h_beats,h_op);
     req_ref<=req_t;cancel_ref<=cancel_t;saved_op<=h_op;saved_addr<=h_addr;saved_beats<=h_beats;saved_arg<=h_arg;saved_tag<=h_tag;requests<=requests+1;beat<=0;bad_sent<=0;
     if(mode==5 && h_op!=1)active_mode<=0;else begin active_mode<=mode;mode<=0;end
     delay_count<=mode==4?50:5;actor<=1;
    end
    1:if(active_mode==3)begin end
      else if(delay_count!=0)delay_count<=delay_count-1;
      else if(active_mode==1)begin pending_status<=4;pending_beats<=0;actor<=3;end
      else actor<=2;
    2:begin
     if(saved_op==0)begin for(z=0;z<16;z=z+1)read_stage[beat][z*8+:8]<=mem[saved_addr+beat*16+z];reads<=reads+1;end
     else begin for(z=0;z<16;z=z+1)mem[saved_addr+beat*16+z]<=write_stage[beat][z*8+:8];writes<=writes+1;end
     beat<=beat+1;
     if(active_mode==5)begin pending_status<=4;pending_beats<=beat+1;actor<=3;end
     else if(beat+1==saved_beats)begin pending_status<=0;pending_beats<=active_mode==6?0:beat+1;actor<=3;end
    end
    3:begin
     done_t<=~done_t;r_status<=pending_status;r_beats<=pending_beats;
     if((active_mode==2 || active_mode==7) && !bad_sent)begin r_tag<=saved_tag^1;bad_sent<=1;actor<=4;end
     else begin r_tag<=saved_tag;actor<=0;end
    end
    4:begin end
   endcase
  end
 end
 integer f,rc,jobs,j,i,c,y,x,a,n,segments,exp_reads,no,timeout,before_requests,before_reads,before_writes,good_jobs=0;
 reg signed[31:0]expected[0:2047];
 task tick;begin @(posedge clk);#1;end endtask
 task launch;begin @(negedge clk);start=1;tick();@(negedge clk);start=0;end endtask
 task clear_fault;begin @(negedge clk);clear=1;tick();@(negedge clk);clear=0;tick();if(error || quarantined || busy)$fatal(1,"clear failed err%d quarantine%d busy%d",error_code,quarantined,busy);end endtask
 task wait_finish;input integer expect_error;begin
 timeout=0;while(busy && timeout<1500000)begin tick();timeout=timeout+1;end
 if(timeout>=1500000 || error_code!==expect_error || error!==(expect_error!=0))$fatal(1,"finish status job%d code%d expected%d state%d",j,error_code,expect_error,dut.state);
 end endtask
 task setup_small;begin
 cfg_ic=1;cfg_oc=1;cfg_oh=1;cfg_ow=1;cfg_kernel=1;cfg_stride=1;first_block=1;final_block=1;input_full_h=1;input_full_w=1;input_origin_y=0;input_origin_x=0;
 input_base=32'h1005;input_row_pitch=16;input_channel_pitch=16;weight_base=32'h18003;weight_oc_stride=16;output_base=32'h30000;output_row_pitch=16;output_channel_pitch=16;output_tail_owned=1;
 mem[input_base]=3;mem[weight_base]=8'hf9;for(t=0;t<16;t=t+1)mem[output_base+t]=8'ha5;
 end endtask
 task expect_bad_descriptor;begin before_requests=requests;launch();wait_finish(1);if(requests!=before_requests || result_valid)$fatal(1,"bad descriptor touched DDR/published");clear_fault();end endtask
 initial begin
 tick();tick();@(negedge clk);reset_n=1;memory_ready=1;tick();tick();tick();
 f=$fopen("VECTORS","r");if(!f)$fatal(1,"vectors unavailable");rc=$fscanf(f,"%d",jobs);
 for(j=0;j<jobs;j=j+1)begin
 rc=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d",cfg_ic,cfg_oc,cfg_oh,cfg_ow,cfg_kernel,cfg_stride,first_block,final_block,input_full_h,input_full_w,input_origin_y,input_origin_x,input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch,output_tail_owned,segments,exp_reads,no);
 if(rc!=24)$fatal(1,"bad vector header %d rc%d",j,rc);
 if(first_block)for(i=0;i<CAP;i=i+1)mem[i]=8'ha5;
 for(c=0;c<segments;c=c+1)begin rc=$fscanf(f,"%d %d",a,n);for(i=0;i<n;i=i+1)begin rc=$fscanf(f,"%d",t);mem[a+i]=t;end end
 for(i=0;i<no;i=i+1)rc=$fscanf(f,"%d",expected[i]);
 for(i=0;i<CAP;i=i+1)shadow[i]=mem[i];before_reads=reads;before_writes=writes;
 if(!start_ready)$fatal(1,"not ready before valid job");launch();wait_finish(0);if(result_valid!==final_block)$fatal(1,"partial output publication");
 if(read_beats!==exp_reads || read_beats!==reads-before_reads)$fatal(1,"read stats job%d got%d expected%d fake%d",j,read_beats,exp_reads,reads-before_reads);
 if(kernel_cycles!==cfg_oc*cfg_oh*cfg_ow*(2*cfg_ic*cfg_kernel*cfg_kernel+3))$fatal(1,"kernel cycles");
 if(final_block)begin
 n=0;for(c=0;c<cfg_oc;c=c+1)for(y=0;y<cfg_oh;y=y+1)begin
 a=output_base+c*output_channel_pitch+y*output_row_pitch;
 for(x=0;x<cfg_ow;x=x+1)begin for(t=0;t<4;t=t+1)shadow[a+x*4+t]=(expected[n]>>(8*t))&255;n=n+1;end
 for(x=cfg_ow*4;x<((cfg_ow+3)/4)*16;x=x+1)shadow[a+x]=0;
 end
 if(write_beats!==cfg_oc*cfg_oh*((cfg_ow+3)/4) || write_beats!==writes-before_writes)$fatal(1,"write stats");
 end else if(write_beats!==0 || writes!=before_writes)$fatal(1,"nonfinal wrote DDR");
 for(i=0;i<CAP;i=i+1)if(mem[i]!==shadow[i])$fatal(1,"DDR/guard mismatch job%d address%h got%h expected%h",j,i,mem[i],shadow[i]);
 good_jobs=good_jobs+1;
 end
 $fclose(f);
 // Full-range/pitch/overlap checks happen before a single DMA request.
 setup_small();output_base=32'h30001;expect_bad_descriptor();setup_small();cfg_ow=5;output_row_pitch=32;output_channel_pitch=32;output_tail_owned=0;expect_bad_descriptor();
 setup_small();input_channel_pitch=32'hffffffff;expect_bad_descriptor();setup_small();input_base=CAP;expect_bad_descriptor();setup_small();output_base=32'h1000;expect_bad_descriptor();
 setup_small();first_block=0;expect_bad_descriptor();setup_small();weight_oc_stride=0;expect_bad_descriptor();
 setup_small();memory_ready=0;before_requests=requests;launch();wait_finish(5);if(requests!=before_requests)$fatal(1,"uncalibrated DMA");clear_fault();memory_ready=1;tick();
 // A mismatched continuation is rejected before any DMA and kills partials.
 setup_small();final_block=0;launch();wait_finish(0);if(result_valid)$fatal(1,"nonfinal published");first_block=0;final_block=1;input_base=input_base+1;expect_bad_descriptor();
 // A normal run succeeds after rejected descriptors. No inferred CPU fallback.
 setup_small();launch();wait_finish(0);if({mem[output_base+3],mem[output_base+2],mem[output_base+1],mem[output_base]}!==-32'sd21)$fatal(1,"normal recovery");
 // Calibration loss at idle invalidates published DDR and partial context.
 memory_ready=0;tick();if(result_valid)$fatal(1,"idle cal loss left published output");memory_ready=1;tick();
 setup_small();mode=1;launch();wait_finish(6);if(mem_status!==4 || result_valid)$fatal(1,"adapter failure published");clear_fault();
 setup_small();mode=6;launch();wait_finish(6);if(result_valid)$fatal(1,"wrong beat count published");clear_fault();
 // Unexpected done tag triggers cancel/drain; matching cancel ACK releases it.
 setup_small();mode=2;launch();wait_finish(9);if(quarantined || actor!=0 || result_valid)$fatal(1,"badtag cancel did not drain");clear_fault();
 // Calibration loss while a request is in flight must cancel and drain.
 setup_small();mode=4;launch();timeout=0;while(actor==0 && timeout<100)begin tick();timeout=timeout+1;end
 memory_ready=0;wait_finish(9);if(quarantined || result_valid)$fatal(1,"cal-loss drain");clear_fault();memory_ready=1;tick();
 // Explicit cancellation while request in flight.
 setup_small();mode=4;launch();timeout=0;while(actor==0 && timeout<100)begin tick();timeout=timeout+1;end
 @(negedge clk);abort=1;tick();@(negedge clk);abort=0;wait_finish(8);if(quarantined || result_valid)$fatal(1,"abort drain");clear_fault();
 // A partial write may have changed one beat but may never publish success.
 setup_small();cfg_ow=8;input_full_w=8;input_row_pitch=16;input_channel_pitch=16;output_row_pitch=32;output_channel_pitch=32;for(i=0;i<8;i=i+1)mem[input_base+i]=i+1;mode=5;launch();wait_finish(6);if(result_valid || write_beats!==1 || mem_status!==4)$fatal(1,"partial write treated as complete");clear_fault();
 // Wrong tag and no matching cancel ACK quarantines until coordinated reset.
 setup_small();mode=7;launch();wait_finish(9);if(!quarantined || result_valid || start_ready)$fatal(1,"missing cancel ACK not quarantined");
 @(negedge clk);clear=1;tick();@(negedge clk);clear=0;tick();if(!quarantined || start_ready)$fatal(1,"clear escaped quarantine");
 @(negedge clk);reset_n=0;memory_ready=0;repeat(5)tick();@(negedge clk);reset_n=1;memory_ready=1;repeat(5)tick();setup_small();launch();wait_finish(0);if(!result_valid)$fatal(1,"reset recovery");
 // Abort a running kernel without any memory request outstanding.
 setup_small();cfg_ic=16;cfg_kernel=3;input_full_h=3;input_full_w=3;input_row_pitch=16;input_channel_pitch=48;weight_oc_stride=144;
 before_writes=writes;launch();timeout=0;while(dut.state!=16 && timeout<5000)begin tick();timeout=timeout+1;end
 if(dut.state!=16)$fatal(1,"kernel did not start");@(negedge clk);abort=1;tick();@(negedge clk);abort=0;wait_finish(8);if(writes!=before_writes || result_valid || quarantined)$fatal(1,"kernel abort publication");clear_fault();
 // A silent adapter hits both finite deadlines and cannot escape via clear.
 setup_small();mode=3;launch();wait_finish(7);if(!quarantined || result_valid || start_ready)$fatal(1,"silent adapter quarantine");
 @(negedge clk);clear=1;tick();@(negedge clk);clear=0;tick();if(!quarantined || start_ready)$fatal(1,"timeout clear escaped quarantine");
 @(negedge clk);reset_n=0;memory_ready=0;repeat(5)tick();@(negedge clk);reset_n=1;memory_ready=1;repeat(5)tick();setup_small();launch();wait_finish(0);if(!result_valid)$fatal(1,"timeout reset recovery");
 $display("PASS DDR Conv loader jobs=%0d signedhalo/unalignedgather/ICblocks, fullDDRguard, typedfaults/cancel/badtag/quarantine/reset",good_jobs);$finish;
 end
 initial begin #300000000;$fatal(1,"global timeout");end
endmodule
'''
def fixtures(path):
 rng=np.random.default_rng(20261107);jobs=[]
 configs=[(1,3,3,5,3,1,4,5,-1,-2),(16,8,16,16,3,2,35,36,1,2),(2,2,2,3,1,2,2,3,-3,-4),(19,3,2,3,3,1,4,5,-1,-1),(3,2,1,1,3,2,3,3,0,0),(16,8,16,16,1,1,16,16,0,0),
 (2,2,1,3,1,1,1,40000,0,39999),(2,2,1,1,3,1,6000,1,5999,0),
 (1,1,1,1,3,1,2,2,-2147483648,-2147483648),(1,1,1,1,3,1,2,2,2147483647,2147483647)]
 for _ in range(24):
  full_ic=int(rng.choice([1,2,16,17,19,33]));oc=int(rng.integers(1,9));oh=int(rng.integers(1,9));ow=int(rng.integers(1,9));k=int(rng.choice([1,3]));stride=int(rng.choice([1,2]));h=int(rng.integers(1,41));w=int(rng.integers(1,41));oy=int(rng.integers(-4,h+3));ox=int(rng.integers(-4,w+3));configs.append((full_ic,oc,oh,ow,k,stride,h,w,oy,ox))
 for full_ic,oc,oh,ow,k,s,h,w,oy,ox in configs:
  ip=w+3;cp=ip*h+11;ws=full_ic*k*k+7;op=((ow*4+15)//16)*16+16;ocp=op*oh+16;ib=0x1005;wb=0x18003;ob=0x30000
  inp=rng.integers(-128,128,(full_ic,h,w),dtype=np.int16).astype(np.int8);weights=rng.integers(-128,128,(oc,full_ic,k,k),dtype=np.int16).astype(np.int8)
  ispan=(full_ic-1)*cp+(h-1)*ip+w;wspan=(oc-1)*ws+full_ic*k*k;idata=np.full(ispan,0xa5,dtype=np.uint8);wdata=np.full(wspan,0x5a,dtype=np.uint8)
  for c in range(full_ic):
   for y in range(h):idata[c*cp+y*ip:c*cp+y*ip+w]=inp[c,y].view(np.uint8)
  for c in range(oc):wdata[c*ws:c*ws+full_ic*k*k]=weights[c].ravel().view(np.uint8)
  accum=np.zeros((oc,oh,ow),dtype=np.int64)
  for ic0 in range(0,full_ic,16):
   ic=min(16,full_ic-ic0);fi=int(ic0==0);la=int(ic0+ic==full_ic);ih=(oh-1)*s+k;iw=(ow-1)*s+k;expected_reads=0
   for c in range(ic):
    for yy in range(ih):
     sy=oy+yy;left=min(iw,max(0,-ox));sx=max(0,ox);copy=min(iw-left,max(0,w-sx))
     if 0<=sy<h and copy:
      addr=ib+(ic0+c)*cp+sy*ip+sx;expected_reads+=((addr&15)+copy+15)//16
   for c in range(oc):
    addr=wb+c*ws+ic0*k*k;expected_reads+=((addr&15)+ic*k*k+15)//16
   for c in range(oc):
    for y in range(oh):
     for x in range(ow):
      for ci in range(ic):
       for ky in range(k):
        for kx in range(k):
         sy=oy+y*s+ky;sx=ox+x*s+kx
         if 0<=sy<h and 0<=sx<w:accum[c,y,x]+=int(inp[ic0+ci,sy,sx])*int(weights[c,ic0+ci,ky,kx])
   segs=[(ib,idata),(wb,wdata)] if fi else []
   header=[ic,oc,oh,ow,k,s,fi,la,h,w,oy,ox,ib+ic0*cp,ip,cp,wb+ic0*k*k,ws,ob,op,ocp,1,len(segs),expected_reads,accum.size if la else 0]
   jobs.append((header,segs,accum.copy() if la else None))
 with path.open('w') as f:
  f.write(str(len(jobs))+'\n')
  for header,segs,arr in jobs:
   f.write(' '.join(map(str,header))+'\n')
   for base,data in segs:f.write(f'{base} {len(data)}\n'+' '.join(map(str,data.tolist()))+'\n')
   if arr is not None:f.write(' '.join(map(str,arr.ravel().tolist()))+'\n')
 return len(jobs)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.output=a.output.resolve();vec=a.output/'vectors.txt';count=fixtures(vec);tb=a.output/'tb_ddr_loader.v';tb.write_text(TB.replace('VECTORS',vec.as_posix()));env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');logs=[];result={'passed':False,'jobs':count,'device_access':'none','scope':'fakeDDR adapter and RTL only, not DDR PHY or board'};binary=a.output/'test.vvp'
 try:
  for cmd in [[a.iverilog,'-g2012','-Wall','-s','tb_ddr_loader','-o',str(binary),str(ROOT/'npu/rtl/npu_ddr_tile_loader.v'),str(ROOT/'npu/rtl/conv_tile_engine.v'),str(tb)],[a.vvp,str(binary)]]:
   r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=300);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
  result.update(passed=True,output=logs[-1],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [ROOT/'npu/rtl/npu_ddr_tile_loader.v',ROOT/'npu/rtl/conv_tile_engine.v']})
 except Exception as e:result['error']=str(e);raise
 finally:(a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(logs[-1])
if __name__=='__main__':main()
