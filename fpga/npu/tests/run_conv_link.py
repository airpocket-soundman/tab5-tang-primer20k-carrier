"""NPU-CONV-v1 pin-level packet/kernel test; independent NumPy INT64 oracle."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
TB=r'''
`timescale 1ns/1ps
module tb_conv_link;
 reg clk=0,reset_n=0,arm=0,bus_clk=0,dir=0,host_oe=0;
 reg[7:0]host_data=0;wire[7:0]data_o;wire data_oe,ready;wire[7:0]bus_data=host_oe?host_data:data_oe?data_o:8'bz;
 reg[7:0]q[0:2059],r[0:1033],payload[0:2050];reg[15:0]crc,tail;integer seq=0,packets=0;
 integer i,j,k,f,rc,jobs,ci,co,ho,wo,ks,st,fi,la,ni,nw,no,v,base,count,kind,chunk;
 reg[7:0]inputs[0:17423],weights[0:1151];reg signed[31:0]expected[0:2047],actual;
 reg[15:0]got_value;integer got_status;reg[31:0]cycles;
 always #18.5 clk=~clk;
 npu_conv_link #(.TIMEOUT(700000)) dut(clk,reset_n,arm,bus_clk,dir,bus_data,data_o,data_oe,ready);
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
 if(!ready)$fatal(1,"response timeout packet %d state %d",packets,dut.state);
 #1000;if(!data_oe)$fatal(1,"ready without OE");n=8;
 for(t=0;t<8;t=t+1)begin r[t]=bus_data;pulse();end
 c=16'hffff;for(t=0;t<6;t=t+1)c=crcbyte(c,r[t]);
 if(r[0]!==8'h5a || r[2]!==seq[7:0] || r[3]!==2 || r[6]!==c[7:0] || r[7]!==c[15:8])$fatal(1,"header/CRC/sequence packet %d",packets);
 got_status=r[1];got_value={r[5],r[4]};
 if(words && !got_status)begin
 if(got_value!==words)$fatal(1,"read count %d vs %d",got_value,words);
 n=8+words*4+2;for(t=8;t<n;t=t+1)begin r[t]=bus_data;pulse();end
 for(t=8;t<n-2;t=t+1)c=crcbyte(c,r[t]);if(r[n-2]!==c[7:0] || r[n-1]!==c[15:8])$fatal(1,"tail CRC packet %d",packets);
 end
 dir=0;#1000;if(ready || data_oe)$fatal(1,"response not released packet %d",packets);packets=packets+1;
 end endtask
 task command;input integer op,len,words,status;begin send_request(op,len,0,0);read_response(words);if(got_status!==status)$fatal(1,"status opcode %h got %d expected %d packet %d",op,got_status,status,packets);end endtask
 task configure;input integer c,o,h,w,kern,stride,flags;
 begin payload[0]=c;payload[1]=o;payload[2]=h;payload[3]=w;payload[4]=kern;payload[5]=stride;payload[6]=(h-1)*stride+kern;payload[7]=(w-1)*stride+kern;payload[8]=flags;command(8'h60,9,0,0);end endtask
 task upload;input integer typ,addr,n,bad;
 begin payload[0]=typ;payload[1]=addr&255;payload[2]=(addr>>8)&255;for(k=0;k<n;k=k+1)payload[3+k]=typ?weights[addr+k]:inputs[addr+k];send_request(8'h61,n+3,0,bad);read_response(0);if(got_status!==(bad?1:0))$fatal(1,"upload status got %d packet %d",got_status,packets);end endtask
 initial begin
 #200;reset_n=1;#200;arm=1;#200;
 command(1,0,0,0);if(got_value!==16'h5054)$fatal(1,"ID");command(8'h50,0,0,0);if(got_value!==16'h4e10)$fatal(1,"CAPS");
 f=$fopen("VECTORS","r");if(!f)$fatal(1,"vectors unavailable");rc=$fscanf(f,"%d",jobs);
 for(j=0;j<jobs;j=j+1)begin
 rc=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d",ci,co,ho,wo,ks,st,fi,la,ni,nw);if(rc!=10)$fatal(1,"vector header");no=co*ho*wo;
 for(i=0;i<ni;i=i+1)begin rc=$fscanf(f,"%d",v);inputs[i]=v;end
 for(i=0;i<nw;i=i+1)begin rc=$fscanf(f,"%d",v);weights[i]=v;end
 if(la)for(i=0;i<no;i=i+1)rc=$fscanf(f,"%d",expected[i]);
 configure(ci,co,ho,wo,ks,st,fi|la*2);
 // A CRC-bad staged input packet must not change engine upload counters/RAM.
 upload(0,0,ni>2048?2048:ni,1);
 for(kind=0;kind<2;kind=kind+1)begin
 count=kind?nw:ni;base=0;
 while(base<count)begin chunk=count-base;if(chunk>2048)chunk=2048;upload(kind,base,chunk,0);base=base+chunk;end
 end
 command(8'h62,0,0,0);command(8'h64,0,0,0);if(got_value!==(la?2:0))$fatal(1,"result flags %d",got_value);
 command(8'h65,0,0,0);cycles=got_value;command(8'h66,0,0,0);cycles=cycles|({16'd0,got_value}<<16);if(cycles!==no*(2*ci*ks*ks+3))$fatal(1,"cycles");
 if(la)begin
 base=0;while(base<no)begin count=no-base;if(count>256)count=256;payload[0]=base&255;payload[1]=(base>>8)&255;payload[2]=count&255;payload[3]=(count>>8)&255;command(8'h63,4,count,0);
 for(i=0;i<count;i=i+1)begin actual={r[8+4*i+3],r[8+4*i+2],r[8+4*i+1],r[8+4*i]};if(actual!==expected[base+i])$fatal(1,"oracle job %d index %d got %d expected %d",j,base+i,actual,expected[base+i]);end base=base+count;end
 end
 end
 $fclose(f);
 // Invalid high config fields must be rejected before narrowing (no wrap).
 payload[0]=32;payload[1]=1;payload[2]=1;payload[3]=1;payload[4]=1;payload[5]=1;payload[6]=1;payload[7]=1;payload[8]=3;command(8'h60,9,0,3);
 command(8'h64,0,0,0);if(got_value!==2)$fatal(1,"invalid cfg mutated published result");
 // Engine dimension mismatch is INVALID_PARAM, not a successful CFG ACK.
 payload[0]=1;payload[1]=1;payload[2]=1;payload[3]=1;payload[4]=1;payload[5]=1;payload[6]=0;payload[7]=1;payload[8]=3;command(8'h60,9,0,3);
 command(8'h64,0,0,0);if(got_value!==16'h0024)$fatal(1,"invalid halo did not fault/invalidate");command(8'h67,0,0,0);
 // Bad header CRC and unknown op return status without numeric results.
 send_request(8'h50,0,1,0);read_response(0);if(got_status!==1 || got_value!==0)$fatal(1,"bad header accepted");command(8'h7f,0,0,2);if(got_value!==0)$fatal(1,"unknown numeric result");
 // A truncated upload and a direction change must not run any staged data.
 configure(1,1,1,1,1,1,3);make_request(8'h61,4,0,0);host_oe=1;dir=0;for(i=0;i<10;i=i+1)begin host_data=q[i];pulse();end host_oe=0;#1000;dir=1;#1000;if(ready || data_oe)$fatal(1,"truncated response");dir=0;#1000;
 inputs[0]=3;weights[0]=-7;upload(0,0,1,0);upload(1,0,1,0);command(8'h62,0,0,0);payload[0]=0;payload[1]=0;payload[2]=1;payload[3]=0;command(8'h63,4,1,0);if({r[11],r[10],r[9],r[8]}!==-32'sd21)$fatal(1,"truncated packet mutated state");
 // Timeout with reply pending must drop OE and invalidate the tile.
 send_request(8'h50,0,0,0);#30000000;if(ready || data_oe)$fatal(1,"timeout OE");dir=0;#1000;command(8'h64,0,0,0);if(got_value!==0)$fatal(1,"timeout retained tile");
 // Physical reset/DISARM removes OE without waiting for the next SYS edge.
 send_request(1,0,0,0);#1000;arm=0;#1;if(data_oe || ready)$fatal(1,"DISARM OE");#200;dir=0;arm=1;#200;command(8'h50,0,0,0);
 send_request(1,0,0,0);#1000;reset_n=0;#1;if(data_oe || ready)$fatal(1,"reset OE");#200;dir=0;reset_n=1;#200;command(8'h50,0,0,0);
 command(8'h67,0,0,0);command(8'h64,0,0,0);if(got_value!==0)$fatal(1,"ABORT");
 $display("PASS NPU-CONV pin-level jobs=%0d packets=%0d max2048 uploads/256word reads, independent INT64, CRC/truncation/timeout/reset/OE",jobs,packets);$finish;
 end
 initial begin #1000000000;$fatal(1,"global timeout");end
endmodule
'''
def vectors(path):
 rng=np.random.default_rng(20261107);jobs=[]
 for k,s,ic,oc,oh,ow in [(1,1,1,1,1,1),(3,2,2,3,2,3),(3,2,16,8,16,16),(1,2,16,8,16,16)]:
  ih=(oh-1)*s+k;iw=(ow-1)*s+k;x=rng.integers(-128,128,(ic,ih,iw),dtype=np.int16).astype(np.int8);w=rng.integers(-128,128,(oc,ic,k,k),dtype=np.int16).astype(np.int8);patch=np.lib.stride_tricks.sliding_window_view(x,(k,k),axis=(1,2))[:,::s,::s];y=np.einsum('iyxkl,oikl->oyx',patch.astype(np.int64),w.astype(np.int64),optimize=False);jobs.append((k,s,ic,oc,oh,ow,1,1,x,w,y))
 acc=None
 for idx,ic in enumerate([16,3]):
  k,s,oc,oh,ow=3,1,3,2,3;ih=(oh-1)*s+k;iw=(ow-1)*s+k;x=rng.integers(-128,128,(ic,ih,iw),dtype=np.int16).astype(np.int8);w=rng.integers(-128,128,(oc,ic,k,k),dtype=np.int16).astype(np.int8);patch=np.lib.stride_tricks.sliding_window_view(x,(k,k),axis=(1,2))[:,::s,::s];y=np.einsum('iyxkl,oikl->oyx',patch.astype(np.int64),w.astype(np.int64),optimize=False);acc=y if acc is None else acc+y;jobs.append((k,s,ic,oc,oh,ow,int(idx==0),int(idx==1),x,w,acc.copy()))
 with path.open('w') as f:
  f.write(str(len(jobs))+'\n')
  for k,s,ic,oc,oh,ow,fi,la,x,w,y in jobs:
   f.write(f'{ic} {oc} {oh} {ow} {k} {s} {fi} {la} {x.size} {w.size}\n');f.write(' '.join(map(str,x.ravel().tolist()))+'\n');f.write(' '.join(map(str,w.ravel().tolist()))+'\n')
   if la:f.write(' '.join(map(str,y.ravel().tolist()))+'\n')
 return len(jobs)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.output=a.output.resolve();v=a.output/'vectors.txt';count=vectors(v);tb=a.output/'tb_conv_link.v';tb.write_text(TB.replace('VECTORS',v.as_posix()));env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');logs=[];result={'passed':False,'jobs':count,'device_access':'none'};binary=a.output/'test.vvp'
 try:
  for cmd in [[a.iverilog,'-g2012','-Wall','-s','tb_conv_link','-o',str(binary),str(ROOT/'npu/rtl/npu_conv_link.v'),str(ROOT/'npu/rtl/conv_tile_engine.v'),str(tb)],[a.vvp,str(binary)]]:
   r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=300);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
  result.update(passed=True,output=logs[-1],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [ROOT/'npu/rtl/npu_conv_link.v',ROOT/'npu/rtl/conv_tile_engine.v']})
 except Exception as e:result['error']=str(e);raise
 finally:(a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(logs[-1])
if __name__=='__main__':main()
