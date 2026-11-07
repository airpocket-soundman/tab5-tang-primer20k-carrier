"""Isolated RTL descriptor/fault proof + independent INT64 Conv oracle. No device IO."""
from pathlib import Path
import argparse,hashlib,json,os,random,struct,subprocess
ROOT=Path(__file__).resolve().parents[3]
TOOLS=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin')
def align(n):return (n+15)//16*16
def job(ic=17,oc=3,oh=3,ow=19,k=3,s=2,ih=8,iw=37,oy=-1,ox=-1):
    arp=align(iw);acp=arp*ih;bp=align(ic*k*k);crp=align(ow*4)
    return [ic,oc,oh,ow,k,s,ih,iw,oy&0xffffffff,ox&0xffffffff,0x2000000,arp,acp,0x2800000,bp,0x5000000,crp,crp*oh]
def signed(x):return x-(1<<32) if x>>31 else x
def oracle(j):
    ic,oc,oh,ow,k,s,ih,iw,oy,ox,ab,arp,acp,bb,bp,cb,crp,ccp=j
    for x in range(0,ow,16):
        for i in range(0,ic,16):
            b=bytearray(52);b[:7]=bytes([min(16,ic-i),oc,oh,min(16,ow-x),k,s,4+(i==0)+2*(i+16>=ic)])
            struct.pack_into('<HH',b,8,ih,iw)
            struct.pack_into('<10I',b,12,oy,(ox+x*s)&0xffffffff,ab+i*acp,arp,acp,bb+i*k*k,bp,cb+x*4,crp,ccp)
            yield bytes(b)
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,abort=0,clear=0,memory_ready=1,job_valid=0,out_ready=0;
reg[575:0]job=0;
wire job_ready,busy,out_valid,result_valid,error,quarantined,tile_abort,descriptor_valid;
wire[3:0]error_code;wire[31:0]accepted_tiles,completed_tiles,expected_tiles;wire[415:0]descriptor;
reg descriptor_ready=0,tile_busy=0,tile_done=0,tile_error=0,tile_quarantined=0,tile_result_valid=0;
npu_ddr_conv_strip_sequencer #(.TILE_TIMEOUT(40),.DRAIN_TIMEOUT(12))dut(.*);
integer mode=0,cycle=0,timer=0,sticky=0,seen=0,ci=0,f,fd,rc,t,holdn,public_accepts=0,before_accepts;reg saved_final;
reg stalled=0;reg[415:0]snapshot;
always @(negedge clk)begin
 cycle=cycle+1;descriptor_ready=mode!=1&&(cycle%5!=0)&&(cycle%7!=0);
 if(!reset_n)begin tile_busy=0;tile_done=0;tile_error=0;tile_quarantined=0;tile_result_valid=0;timer=0;sticky=0;seen=0;end
 else if(tile_abort&&mode!=2)begin tile_busy=0;timer=0;if(sticky>0)begin sticky=sticky-1;if(!sticky)tile_done=0;end end
 else if(tile_busy)begin
  if(mode==2)begin end
  else begin timer=timer-1;if(timer==0)begin tile_busy=0;tile_done=1;sticky=2+(cycle%4);tile_result_valid=saved_final&&mode!=8;
   if(mode==4)tile_error=1;if(mode==7)tile_quarantined=1;
  end end
 end else if(tile_done)begin sticky=sticky-1;if(!sticky)tile_done=0;end
 if(reset_n&&seen>0&&mode==6)memory_ready=0;
 if(reset_n&&seen>0&&mode==9)abort=1;
end
always @(posedge clk)begin
 // Independent consumer: only standard valid&&ready, not a private consumer gate.
 if(reset_n&&out_valid&&out_ready)begin
  public_accepts=public_accepts+1;
  if(abort||!memory_ready)$fatal(1,"public result handshake during abort/cal-loss");
 end
 if((abort||!memory_ready)&&(out_valid||result_valid))$fatal(1,"exported valid not combinationally suppressed");
 if(!reset_n)stalled<=0;
 else begin
  if(stalled&&descriptor_valid&&snapshot!==descriptor)$fatal(1,"descriptor changed under backpressure");
  stalled<=descriptor_valid&&!descriptor_ready;snapshot<=descriptor;
  if(abort&&descriptor_valid)$fatal(1,"descriptor visible during abort");
  if(descriptor_valid&&descriptor_ready)begin
   if(tile_busy||tile_done)$fatal(1,"overlapping/stale completion");
   $fdisplay(fd,"D %0d %0104h",ci,descriptor);seen=seen+1;saved_final=descriptor[49];tile_busy<=1;timer=2+(cycle%8);
  end
 end
end
initial begin
 f=$fopen("jobs.txt","r");fd=$fopen("trace.txt","w");
 while(!$feof(f))begin
  @(negedge clk);reset_n=0;abort=0;clear=0;job_valid=0;out_ready=0;memory_ready=1;
  repeat(4)@(negedge clk);reset_n=1;
  rc=$fscanf(f,"%d %h\n",mode,job);if(rc!=2)$fatal(1,"input parse");
  job_valid=1;if(mode==5)abort=1;
  @(posedge clk);#1;
  @(negedge clk);job_valid=0;job=0;
  if(mode==5)begin
   repeat(10)@(negedge clk);if(busy||out_valid||seen)$fatal(1,"abort did not dominate accept");
   $fdisplay(fd,"R %0d 0 0 0 0 0 0",ci);
  end else begin
   t=0;while(!out_valid&&t<200000)begin @(negedge clk);t=t+1;
    if(mode==6&&dut.out_valid_q)begin memory_ready=1;mode=16;end
    if(mode==9&&dut.out_valid_q)begin abort=0;mode=10;end
   end
   if(!out_valid)$fatal(1,"job did not finish");
   $fdisplay(fd,"R %0d %0d %0d %0d %0d %0d %0d",ci,result_valid,error,error_code,quarantined,accepted_tiles,completed_tiles);
   if(mode==9)begin abort=0;mode=10;end
   // Completion stays stable until consumed, no numeric validity on failure.
   for(holdn=0;holdn<5;holdn=holdn+1)begin @(negedge clk);if(!out_valid||busy||(error&&result_valid))$fatal(1,"completion/backpressure");end
   if((mode==0||mode==15)&&result_valid)begin
    before_accepts=public_accepts;out_ready=1;job_valid=1;
    if(mode==15)memory_ready=0;else abort=1;
    #1;if(out_valid||result_valid)$fatal(1,"same-edge valid gate missing");
    @(negedge clk);job_valid=0;out_ready=0;
    if(public_accepts!=before_accepts||result_valid||out_valid||busy)$fatal(1,"abort/cal-loss accepted stale success");
    abort=0;
   end
  end
  ci=ci+1;
 end
 $display("PASS RTL strip jobs=%0d",ci);$fclose(fd);$finish;
end
endmodule
'''
def value_a(c,y,x):return ((c*17+y*7+x*3)%255)-127
def value_b(o,c,y,x):return ((o*23+c*5+y*3+x*11)%255)-127
def numeric(j,ds):
    ic,oc,oh,ow,k,s,ih,iw,oy,ox,ab,arp,acp,bb,bp,cb,crp,ccp=j;oy=signed(oy);ox=signed(ox)
    # Direct whole-strip reference, independent of descriptor partition/address traversal.
    ref={}
    for o in range(oc):
      for y in range(oh):
       for x in range(ow):
        acc=0
        for c in range(ic):
         for ky in range(k):
          for kx in range(k):
           iy=oy+y*s+ky;ix=ox+x*s+kx
           if 0<=iy<ih and 0<=ix<iw:acc+=value_a(c,iy,ix)*value_b(o,c,ky,kx)
        ref[cb+o*ccp+y*crp+x*4]=acc
    # Interpret accepted RTL descriptors as a fake tile engine, sparse DDR byte gather.
    published={};accum={};writes=[]
    for d in ds:
      ni,no,nh,nw,kk,ss,flags=d[:7];fh,fw=struct.unpack_from('<HH',d,8)
      dy,dx,ia,rp,cp,wb,wp,ob,orp,ocp=struct.unpack_from('<10I',d,12);dy=signed(dy);dx=signed(dx)
      for o in range(no):
       for y in range(nh):
        for x in range(nw):
         key=(o,y,x)
         if flags&1:accum[key]=0
         a=accum[key]
         for c in range(ni):
          for ky in range(kk):
           for kx in range(kk):
            yy=dy+y*ss+ky;xx=dx+x*ss+kx
            if 0<=yy<fh and 0<=xx<fw:
             addr=ia+c*cp+yy*rp+xx;cc,rem=divmod(addr-ab,acp);ay,ax=divmod(rem,arp)
             wa=wb+o*wp+(c*kk+ky)*kk+kx;oo,rem=divmod(wa-bb,bp);wc,rem=divmod(rem,k*k);wy,wx=divmod(rem,k)
             assert oo==o and cc==wc and ay==yy and ax==xx
             a+=value_a(cc,ay,ax)*value_b(oo,wc,wy,wx)
         assert -(1<<31)<=a<(1<<31);accum[key]=a
         if flags&2:
          address=ob+o*ocp+y*orp+x*4;assert address not in published;published[address]=a;writes.append(address)
    assert published==ref,'INT32 strip differs from independent whole Conv'
    assert len(writes)==oc*oh*ow
    return len(ref)

def real_loader(out,env,commands):
    # Reuse the independently existing tagged fake DDR adapter, not its tile stimulus.
    import importlib.util
    sp=importlib.util.spec_from_file_location('loader_proof',Path(__file__).with_name('run_ddr_tile_loader.py'));mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
    tb=mod.TB[:mod.TB.index(' integer f,rc,jobs')]
    tb=tb.replace('start=0,abort=0,clear=0','clear=0')
    # Original module is kept named tb_ddr_loader for a minimal adapter fixture diff.
    begin=tb.index(' reg[4:0]cfg_ic');end=tb.index(' wire[3:0]error_code',begin)
    tb=tb[:begin]+r'''
 wire[4:0]cfg_ic,cfg_oh,cfg_ow;wire[3:0]cfg_oc;wire[1:0]cfg_kernel,cfg_stride;
 wire first_block,final_block,output_tail_owned;
 wire[15:0]input_full_h,input_full_w;wire signed[31:0]input_origin_y,input_origin_x;
 wire[31:0]input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch;
 reg job_valid=0,out_ready=0;reg[575:0]job=0;
 wire job_ready,seq_busy,seq_out,seq_result,seq_error,seq_quarantine,desc_valid,abort;
 wire[3:0]seq_code;wire[31:0]accepted_tiles,completed_tiles,expected_tiles;wire[415:0]descriptor;
 wire start=desc_valid&&start_ready;
 assign cfg_ic=descriptor[0+:8];assign cfg_oc=descriptor[8+:8];assign cfg_oh=descriptor[16+:8];assign cfg_ow=descriptor[24+:8];
 assign cfg_kernel=descriptor[32+:8];assign cfg_stride=descriptor[40+:8];assign first_block=descriptor[48];assign final_block=descriptor[49];assign output_tail_owned=descriptor[50];
 assign input_full_h=descriptor[64+:16];assign input_full_w=descriptor[80+:16];
 assign input_origin_y=descriptor[96+:32];assign input_origin_x=descriptor[128+:32];assign input_base=descriptor[160+:32];
 assign input_row_pitch=descriptor[192+:32];assign input_channel_pitch=descriptor[224+:32];assign weight_base=descriptor[256+:32];
 assign weight_oc_stride=descriptor[288+:32];assign output_base=descriptor[320+:32];assign output_row_pitch=descriptor[352+:32];assign output_channel_pitch=descriptor[384+:32];
 npu_ddr_conv_strip_sequencer #(.CAPACITY(CAP),.TILE_TIMEOUT(500000))seq(
  .clk(clk),.reset_n(reset_n),.abort(1'b0),.clear(clear),.memory_ready(memory_ready),.job_valid(job_valid),.job_ready(job_ready),.job(job),
  .busy(seq_busy),.out_valid(seq_out),.out_ready(out_ready),.result_valid(seq_result),.error(seq_error),.quarantined(seq_quarantine),.error_code(seq_code),
  .accepted_tiles(accepted_tiles),.completed_tiles(completed_tiles),.expected_tiles(expected_tiles),.descriptor_valid(desc_valid),.descriptor_ready(start_ready),.descriptor(descriptor),
  .tile_busy(busy),.tile_done(block_done),.tile_error(error),.tile_quarantined(quarantined),.tile_result_valid(result_valid),.tile_abort(abort));
''' +tb[end:]
    tb=tb.replace('npu_ddr_tile_loader #','npu_ddr_tile_loader_8oc #')
    tb+=r'''
 integer f,j,i,rc,ticks,expected_count;reg[575:0]incoming;
 initial begin
  f=$fopen("real-jobs.txt","r");
  for(j=0;j<REAL_COUNT;j=j+1)begin
   @(negedge clk);reset_n=0;memory_ready=0;job_valid=0;out_ready=0;
   repeat(5)@(negedge clk);
   $readmemh($sformatf("input_%0d.hex",j),mem);$readmemh($sformatf("expected_%0d.hex",j),shadow);
   rc=$fscanf(f,"%h %d\n",incoming,expected_count);if(rc!=2)$fatal(1,"real fixture parse");
   reset_n=1;memory_ready=1;repeat(5)@(negedge clk);
   if(!job_ready)$fatal(1,"seq not ready");job=incoming;job_valid=1;
   @(negedge clk);job_valid=0;job=0;ticks=0;
   while(!seq_out&&ticks<5000000)begin @(negedge clk);ticks=ticks+1;end
   if(!seq_out||!seq_result||seq_error||seq_quarantine||error||quarantined||accepted_tiles!=expected_count||completed_tiles!=expected_count)$fatal(1,"real loader status j%0d seq%0d loader%0d",j,seq_code,error_code);
   for(i=0;i<CAP;i=i+1)if(mem[i]!==shadow[i])$fatal(1,"real DDR mismatch job%0d addr%h got%h expected%h",j,i,mem[i],shadow[i]);
   $display("PASS actual8OC loader strip job%0d tiles%0d",j,completed_tiles);
  end
  $finish;
 end
 initial begin #3000000000;$fatal(1,"real global timeout");end
endmodule
'''
    configs=[(17,3,3,19,3,2),(33,8,2,33,3,1),(16,7,3,17,1,2),(1,1,1,1,3,1)]
    real_jobs=[];values=0
    for index,c in enumerate(configs):
      ic,oc,oh,ow,k,s=c;j=job(*c,ih=oh*s+2,iw=ow*s+1);j[10]=0x1000;j[13]=0x18000;j[15]=0x30000
      ic,oc,oh,ow,k,s,ih,iw,oy,ox,ab,arp,acp,bb,bp,cb,crp,ccp=j;oy=signed(oy);ox=signed(ox)
      data=bytearray([0xa5])*262144
      for ch in range(ic):
       for y in range(ih):
        for x in range(iw):data[ab+ch*acp+y*arp+x]=value_a(ch,y,x)&255
      for o in range(oc):
       for ch in range(ic):
        for ky in range(k):
         for kx in range(k):data[bb+o*bp+(ch*k+ky)*k+kx]=value_b(o,ch,ky,kx)&255
      expected=bytearray(data)
      for o in range(oc):
       for y in range(oh):
        # Loader owns aligned padding only, leaving any larger pitch gaps intact.
        expected[cb+o*ccp+y*crp:cb+o*ccp+y*crp+align(ow*4)]=bytes(align(ow*4))
        for x in range(ow):
         acc=0
         for ch in range(ic):
          for ky in range(k):
           for kx in range(k):
            yy=oy+y*s+ky;xx=ox+x*s+kx
            if 0<=yy<ih and 0<=xx<iw:acc+=value_a(ch,yy,xx)*value_b(o,ch,ky,kx)
         struct.pack_into('<i',expected,cb+o*ccp+y*crp+x*4,acc);values+=1
      for n,content in [('input',data),('expected',expected)]:
       (out/f'{n}_{index}.hex').write_text('\n'.join(f'{v:02x}' for v in content)+'\n')
      real_jobs.append((j,len(list(oracle(j)))))
    (out/'real-jobs.txt').write_text(''.join(f'{sum(v<<(32*i) for i,v in enumerate(j)):0144x} {n}\n' for j,n in real_jobs))
    (out/'real-tb.v').write_text(tb.replace('REAL_COUNT',str(len(real_jobs))))
    paths=[ROOT/'fpga/npu/rtl'/s for s in ['npu_ddr_conv_strip_sequencer.v','npu_ddr_tile_loader_8oc.v','conv_tile_engine_8oc.v']]
    for cmd in [[str(TOOLS/'iverilog.exe'),'-g2012','-s','tb_ddr_loader','-o',str(out/'real.vvp'),*[str(p) for p in paths],str(out/'real-tb.v')],[str(TOOLS/'vvp.exe'),str(out/'real.vvp')]]:
      p=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);commands.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout,p.stderr);assert p.returncode==0
    return dict(cases=len(real_jobs),actual_INT32_values=values,actual_loader_tiles=sum(n for j,n in real_jobs),scope='Actual unchanged8OC loader+MAC, tagged fakeDDR adapter and full256KiB DDR guard comparison; not DDR PHY/board',adapter_template_sha256=hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest(),source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'fpga/build/conv-strip-proof');args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    cases=[]
    def add(j,mode=0,error=0,numeric_case=False):cases.append(dict(job=j,mode=mode,error=error,numeric=numeric_case))
    rng=random.Random(0x4e25)
    for ic,oc,oh,ow,k,s in [(1,1,1,1,1,1),(17,3,3,19,3,2),(33,8,2,33,3,1),(16,7,16,17,1,2),(3,8,16,320,3,2),(768,8,1,1,1,1),(1,1,1,65535,1,1)]:
      j=job(ic,oc,oh,ow,k,s,max(oh*s+2,3),max(min(ow,320)*s+2,3));add(j,numeric_case=ow<=33)
    for _ in range(28):
      ic=rng.choice([1,15,16,17,31,32,33,65]);oc=rng.randint(1,8);oh=rng.randint(1,4);ow=rng.choice([1,7,15,16,17,31,32,33,40]);k=rng.choice([1,3]);s=rng.choice([1,2]);add(job(ic,oc,oh,ow,k,s,oh*s+2,ow*s+1),numeric_case=True)
    base=job()
    add(base.copy(),mode=15,numeric_case=True)
    for index,value,err in [(0,0,1),(0,65536,1),(0,0xffffffff,1),(1,9,1),(2,17,1),(3,65536,1),(4,2,1),(5,3,1),(6,0,1),(7,65536,1),(10,0x2000001,2),(11,16,2),(12,16,2),(14,16,2),(16,16,2),(17,16,2),(15,0x7fffff0,2),(10,0xfffffff0,2),(12,0xfffffff0,2),(9,0x7fffffff,2),(8,0x7fffffff,2),(13,base[10],3)]:
      j=base.copy();j[index]=value;add(j,error=err)
    for mode,err in [(1,6),(2,6),(4,4),(5,0),(6,7),(7,8),(8,9),(9,5)]:add(base.copy(),mode,err)
    # Exact capacity boundary is accepted; pitches include owned gaps.
    j=job(17,3,2,19);j[15]=134217728-j[1]*j[17];add(j,numeric_case=True)
    (out/'jobs.txt').write_text(''.join(f"{c['mode']} {sum(v<<(32*i) for i,v in enumerate(c['job'])):0144x}\n" for c in cases))
    (out/'tb.v').write_text(TB);env=dict(os.environ);env['PATH']=str(TOOLS)+os.pathsep+env.get('PATH','');commands=[]
    src=ROOT/'fpga/npu/rtl/npu_ddr_conv_strip_sequencer.v'
    for cmd in [[str(TOOLS/'iverilog.exe'),'-g2012','-s','tb','-o',str(out/'proof.vvp'),str(src),str(out/'tb.v')],[str(TOOLS/'vvp.exe'),str(out/'proof.vvp')]]:
      p=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);commands.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout,p.stderr);assert p.returncode==0
    traces={i:[] for i in range(len(cases))};results={}
    for line in (out/'trace.txt').read_text().splitlines():
      q=line.split();i=int(q[1])
      if q[0]=='D':traces[i].append(int(q[2],16).to_bytes(52,'little'))
      else:results[i]=list(map(int,q[2:]))
    values=0;total_descriptors=0
    for i,c in enumerate(cases):
      result,err,code,quarantine,accepted,completed=results[i];ds=traces[i];assert accepted==len(ds),(i,accepted,len(ds));total_descriptors+=accepted
      if c['mode']==5:assert results[i]==[0]*6
      elif c['error']:
       assert err and code==c['error'] and not result,(i,results[i]);assert quarantine==(c['mode']in [2,7]),(i,results[i])
       if c['mode']==0:assert accepted==0,'invalid job emitted descriptor'
      else:
       expected=list(oracle(c['job']));assert ds==expected,(i,len(ds),len(expected));assert results[i]==[1,0,0,0,len(ds),len(ds)],(i,results[i])
       if c['numeric']:values+=numeric(c['job'],ds)
    real=real_loader(out,env,commands)
    # Deliberately remove ONLY public valid gates in a build-only copy. The independent
    # consumer uses valid&&ready and must reject this former integration hazard.
    bad=src.read_text().replace('out_valid_q&&!abort&&memory_ready&&reset_n','out_valid_q').replace('result_valid_q&&!abort&&memory_ready&&reset_n','result_valid_q')
    (out/'negative-ungated.v').write_text(bad)
    ntb=TB.replace('#1;if(out_valid||result_valid)$fatal(1,"same-edge valid gate missing");','')
    ntb=ntb.replace('if((abort||!memory_ready)&&(out_valid||result_valid))$fatal(1,"exported valid not combinationally suppressed");','')
    ntb='\n'.join(line.rstrip() for line in ntb.splitlines())+'\n'
    (out/'negative-tb.v').write_text(ntb)
    cmd=[str(TOOLS/'iverilog.exe'),'-g2012','-s','tb','-o',str(out/'negative.vvp'),str(out/'negative-ungated.v'),str(out/'negative-tb.v')]
    p=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);commands.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));assert p.returncode==0
    cmd=[str(TOOLS/'vvp.exe'),str(out/'negative.vvp')];p=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True)
    commands.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,expected_failure=True));print(p.stdout,p.stderr)
    assert p.returncode!=0 and 'public result handshake during abort/cal-loss' in p.stdout
    report=dict(passed=True,implemented='isolated controller only, no protocol/top integration',hardware_access=False,cases=len(cases),accepted_descriptors=total_descriptors,numeric_INT32_values=values,numeric_scope='Actual RTL descriptors interpreted by independent fake tile engine vs direct whole-strip INT64 Conv',public_valid_handshake_observer='PASS abort/cal-loss coincident ready; ungated build-copy negative control intentionally fails observer',actual_loader=real,commands=commands,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [src,Path(__file__).resolve()]})
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='commands'},indent=2))
if __name__=='__main__':main()
