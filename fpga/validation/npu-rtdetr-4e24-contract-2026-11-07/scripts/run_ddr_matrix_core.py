"""4E24 pin protocol+actualDDR adapter/8OC numeric matrix integration, mock PHY."""
from pathlib import Path
import argparse,sys,hashlib,json,struct
import numpy as np
import run_npu_ddr_core_8oc as base
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/npu-ddr-matrix-core');p.add_argument('--iverilog',default='D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/iverilog.exe');p.add_argument('--vvp',default='D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin/vvp.exe');a=p.parse_args();out=a.output.resolve();snap=out/'source_snapshot';snap.mkdir(parents=True,exist_ok=True)
 names=['npu/rtl/npu_ddr_core_matrix.v','npu/rtl/npu_ddr_sys_matrix.v','npu/rtl/npu_ddr_matmul_sequencer.v','npu/rtl/npu_ddr_arbiter.v','npu/rtl/npu_ddr_tile_loader_8oc.v','npu/rtl/conv_tile_engine_8oc.v','mem/rtl/memv1_bridge.v','mem/rtl/mem_adapter.v','mem/rtl/memv1_crc32b.v'];hashes={}
 for n in names:
  s=ROOT/n;hashes[n]=hashlib.sha256(s.read_bytes()).hexdigest();dest=snap/n.replace('npu_ddr_core_matrix','npu_ddr_core_8oc').replace('npu_ddr_sys_matrix','npu_ddr_sys');dest.parent.mkdir(parents=True,exist_ok=True);text=s.read_text().replace('npu_ddr_core_matrix','npu_ddr_core_8oc').replace('npu_ddr_sys_matrix','npu_ddr_sys');dest.write_text(text,newline='\n')
 core=snap/'npu/rtl/npu_ddr_core_8oc.v';core.write_text(core.read_text()+'\n'+(ROOT/'npu/rtl/npu_ddr_matmul_sequencer.v').read_text())
 original=base.vectors;matrix_shapes=[]
 def vectors(path):
  count=original(path);old=path.read_text().split('\n',1)[1];lines=[];rng=np.random.default_rng(0x4e24)
  def cmd(op,payload=b'',status=0,value=0,reply=b'',writes=0,bad=0):
   nonlocal count
   lines.extend([f'{op} {len(payload)} {status} {value} {len(reply)} {writes} {bad}',' '.join(map(str,payload)),' '.join(map(str,reply))]);count+=1
  def wr(addr,data):
   for off in range(0,len(data),2032):
    block=data[off:off+2032];cmd(0x71,struct.pack('<IH2x',addr+off,len(block))+block,writes=len(block)//16)
  def rd(addr,data):
   for off in range(0,len(data),1024):
    block=data[off:off+1024];cmd(0x70,struct.pack('<IH2x',addr+off,len(block)),value=len(block),reply=block)
  for m,k,n in [(1,17,9),(197,17,9),(257,17,9),(1,17,197)]:
   mp=(m+15)//16*16;kp=(k+15)//16*16;ap=mp+16;bp=kp+16;cp=mp*4+16;ab=0x30000;bb=0x50000;cb=0x80000
   A=rng.integers(-127,128,(k,m),dtype=np.int16).astype(np.int8);B=rng.integers(-127,128,(n,k),dtype=np.int16).astype(np.int8);C=B.astype(np.int64)@A.astype(np.int64)
   av=bytearray([0xa5]*(k*ap));bv=bytearray([0xa5]*(n*bp));cv=bytearray([0xa5]*(n*cp));expected=cv.copy()
   for z in range(k):av[z*ap:z*ap+m]=A[z].tobytes();av[z*ap+m:z*ap+mp]=bytes(mp-m)
   for z in range(n):bv[z*bp:z*bp+k]=B[z].tobytes();expected[z*cp:z*cp+m*4]=C[z].astype('<i4').tobytes();expected[z*cp+m*4:z*cp+mp*4]=bytes((mp-m)*4)
   wr(ab,av);wr(bb,bv);wr(cb,cv);job=struct.pack('<9I',m,k,n,ab,ap,bb,bp,cb,cp);tiles=((m+255)//256)*((n+7)//8)*((k+15)//16)
   cmd(0x78,job,writes=n*(mp//16)*4);cmd(0x79,value=17);cmd(0x7a,value=tiles);cmd(0x7b);cmd(0x7c,value=tiles);cmd(0x7d);rd(cb,expected)
   cmd(0x78,job,status=1,bad=1);cmd(0x7a,value=tiles);rd(cb,expected[:16]);matrix_shapes.append({'m':m,'k':k,'n':n,'tiles':tiles,'outputs':m*n,'padded_zero':True,'gap_bytes_untouched':True})
  path.write_text(str(count)+'\n'+old+'\n'.join(lines)+'\n');return count
 base.vectors=vectors
 base.NATIVE=base.NATIVE.replace('.RECAL_HOLD(8))','.RECAL_HOLD(8),.REQUEST_DATA_PIPELINE(1))').replace('reg[7:0]mem[0:262143]','reg[7:0]mem[0:1048575]').replace("a<32'h30000","a<32'hf0000").replace("mapped=32'h30000+","mapped=32'hf0000+")
 base.MAIN=base.MAIN.replace("16'h4e20","16'h4e24").replace('#1000000000;','#10000000000;')
 base.MAIN=base.MAIN.replace(' integer cached_input_len',' reg[7:0]last_matrix_job[0:35];\n integer cached_input_len').replace("if(opn==8'h68)","if(opn==8'h78)for(i=0;i<36;i=i+1)last_matrix_job[i]=payload[i];\n if(opn==8'h68)")
 extra=r'''

 // Busy/ready level without accepted tiles is not watchdog progress.
 for(i=0;i<36;i=i+1)payload[i]=last_matrix_job[i];force dut.conv_start_ready=0;bw=writes;
 send_request(8'h78,36,0,0);wait(dut.matrix_busy);repeat(220)@(posedge clk);
 if(dut.matrix_accepted!=0||dut.matrix_completed!=0||dut.matrix_progress)$fatal(1,"stalled ready invented progress");
 force dut.link.idle=27000000-1;@(posedge clk);#1;release dut.link.idle;
 repeat(12)@(posedge clk);
 if(!dut.matrix_error||dut.matrix_result_valid||dut.matrix_accepted!=0||writes!=bw||ready)$fatal(1,"stalled matrix did not abort safely");
 release dut.conv_start_ready;arm=0;dir=0;#1000;arm=1;wait_memory();bind_session(32'h8899aabb);
 // In-flight matrix DDR calibration loss must invalidate its lease/result.
 for(i=0;i<36;i=i+1)payload[i]=last_matrix_job[i];native_hold=1;send_request(8'h78,36,0,0);
 wait(dut.conv_busy&&dut.arbiter_active);cal_override=1;read_response(0);
 if(got_status!=8||dut.matrix_result_valid)$fatal(1,"matrix calibration-loss publication");
 cal_override=0;native_hold=0;wait_memory();command(8'h76,0,0,0);if(got_value!=0)$fatal(1,"matrix stale lease survived");bind_session(32'h55667788);
 // Full-width dimensions must be rejected, never truncated into a small job.
 for(i=0;i<36;i=i+1)payload[i]=last_matrix_job[i];payload[0]=0;payload[1]=0;payload[2]=1;payload[3]=0;
 command(8'h78,36,0,5);if(got_value!=1)$fatal(1,"matrix high M truncation");
 command(8'h79,0,0,0);if(got_value!=16'h0104)$fatal(1,"matrix error status");
 command(8'h67,0,0,7);command(8'h78,36,0,4);
 // Only coordinated ARM reset can recover the failed job safely.
 arm=0;dir=0;#1000;arm=1;wait_memory();bind_session(32'h11223344);command(8'h79,0,0,0);if(got_value!=1)$fatal(1,"matrix error survived coordinated reset");
'''
 base.MAIN=base.MAIN.replace(' $display("PASS NPU DDR core',extra+' $display("PASS NPU DDR core')
 base.OLD_TB=base.OLD_TB.replace('waited<26000','waited<2000000').replace('#1000','#200')
 base.ROOT=snap;sys.argv=['run_npu_ddr_core_8oc.py','--iverilog',a.iverilog,'--vvp',a.vvp,'--output',str(out/'proof')];base.main()
 assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==v for n,v in hashes.items())
 (out/'actual-source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n');(out/'matrix-result.json').write_text(json.dumps({'passed':True,'shapes':matrix_shapes,'hardware_access':False,'scope':'actual SYS/core/sequencer/loader/8OC/arbiter/CDC/adapter, mock native DDR; no PHY'},indent=2)+'\n')
if __name__=='__main__':main()
