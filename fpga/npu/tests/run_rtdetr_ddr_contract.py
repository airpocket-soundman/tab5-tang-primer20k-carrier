"""RT-DETR backend assumptions against unmodified4E24, real kernel+DDR adapter."""
from pathlib import Path
import sys,json,struct,hashlib
import numpy as np
import run_ddr_matrix_core as matrix
ROOT=Path(__file__).resolve().parents[2]
def main():
 original_main=matrix.base.main;records=[]
 def execute():
  prior=matrix.base.vectors
  def vectors(path):
   count=prior(path);old=path.read_text().split('\n',1)[1];lines=[];rng=np.random.default_rng(0x52444732)
   def cmd(op,payload=b'',status=0,value=0,reply=b'',writes=0,bad=0):
    nonlocal count
    lines.extend([f'{op} {len(payload)} {status} {value} {len(reply)} {writes} {bad}',' '.join(map(str,payload)),' '.join(map(str,reply))]);count+=1
   def wr(addr,data):
    for off in range(0,len(data),2032):
     chunk=data[off:off+2032];cmd(0x71,struct.pack('<IH2x',addr+off,len(chunk))+chunk,writes=len(chunk)//16)
   def rd(addr,data):
    for off in range(0,len(data),1024):
     chunk=data[off:off+1024];cmd(0x70,struct.pack('<IH2x',addr+off,len(chunk)),value=len(chunk),reply=chunk)
   for ic,k,s,pad,h,w in [(32,3,2,1,19,23),(33,3,2,1,19,23),(256,1,1,0,3,5)]:
    oc=9;oh=(h+2*pad-k)//s+1;ow=(w+2*pad-k)//s+1;ip=(w+15)//16*16;cp=ip*h;wp=(ic*k*k+15)//16*16
    ab=0x05000000;bb=0x02002000;cb=0x05020000;op=64;ocp=oh*op
    A=rng.integers(-127,128,(ic,h,w),dtype=np.int16).astype(np.int8);B=rng.integers(-127,128,(oc,ic,k,k),dtype=np.int16).astype(np.int8)
    av=bytearray([0xa5]*(ic*cp));bv=bytearray([0xa5]*(oc*wp))
    for c in range(ic):
     for y in range(h):av[c*cp+y*ip:c*cp+y*ip+w]=A[c,y].tobytes()
    for c in range(oc):bv[c*wp:c*wp+ic*k*k]=B[c].tobytes()
    wr(ab,av);wr(bb,bv);C=np.zeros((oc,oh,ow),dtype=np.int64)
    for yy in range(oh):
     for xx in range(ow):
      for ky in range(k):
       for kx in range(k):
        iy=yy*s-pad+ky;ix=xx*s-pad+kx
        if 0<=iy<h and 0<=ix<w:C[:,yy,xx]+=B[:,:,ky,kx].astype(np.int64)@A[:,iy,ix].astype(np.int64)
    tiles=0
    for ob in range(0,oc,8):
     no=min(8,oc-ob);sentinel=bytes([0xa5]*(no*ocp));wr(cb,sentinel)
     for ib in range(0,ic,16):
      ni=min(16,ic-ib);final=ib+ni==ic;flags=int(ib==0)|(int(final)<<1)|4
      desc=bytes([ni,no,oh,ow,k,s,flags,0])+struct.pack('<HHiiIIIIIIII',h,w,-pad,-pad,ab+ib*cp,ip,cp,bb+ob*wp+ib*k*k,wp,cb,op,ocp)
      cmd(0x68,desc,writes=no*oh*((ow+3)//4) if final else 0);tiles+=1
      if not final:rd(cb,sentinel[:16])
     expected=bytearray(sentinel)
     for c in range(no):
      for y in range(oh):
       at=c*ocp+y*op;expected[at:at+ow*4]=C[ob+c,y].astype('<i4').tobytes();expected[at+ow*4:at+((ow+3)//4)*16]=bytes(((ow+3)//4)*16-ow*4)
     rd(cb,expected)
    records.append({'kind':'Conv','ic':ic,'oc':oc,'kernel':k,'stride':s,'pad':pad,'input_hw':[h,w],'output_hw':[oh,ow],'weight_OC_pitch':wp,'tiles':tiles,'outputs':oc*oh*ow,'padding_gaps':True})
   # Full static NxK (transB=1 Gemm convention) and M257 panel-offset guard.
   for m,k,n in [(3,65,9),(257,65,9)]:
    ap=(m+15)//16*16;bp=(k+15)//16*16;ab=0x05030000;bb=0x02020000;cb=0x05050000
    A=rng.integers(-127,128,(k,m),dtype=np.int16).astype(np.int8);B=rng.integers(-127,128,(n,k),dtype=np.int16).astype(np.int8);av=bytearray(k*ap+ap);bv=bytearray(n*bp)
    for ci in range(k):av[ci*ap:ci*ap+m]=A[ci].tobytes()
    for co in range(n):bv[co*bp:co*bp+k]=B[co].tobytes()
    wr(ab,av);wr(bb,bv);C=B.astype(np.int64)@A.astype(np.int64);jobs=0;tiles=0
    for nb in range(0,n,8):
     no=min(8,n-nb)
     for mb in range(0,m,256):
      mm=min(256,m-mb);mp=(mm+15)//16*16;cp=mp*4;sentinel=bytes([0xa5]*(no*cp+32));wr(cb-16,sentinel)
      payload=struct.pack('<9I',mm,k,no,ab+mb,ap,bb+nb*bp,bp,cb,cp)
      cmd(0x78,payload,writes=no*(mp//16)*4);expected=bytearray(sentinel)
      for co in range(no):at=16+co*cp;expected[at:at+mm*4]=C[nb+co,mb:mb+mm].astype('<i4').tobytes();expected[at+mm*4:at+cp]=bytes(cp-mm*4)
      rd(cb-16,expected);tile_count=(k+15)//16;cmd(0x7a,value=tile_count);cmd(0x7c,value=tile_count);jobs+=1;tiles+=tile_count
    records.append({'kind':'Gemm/MatMul','m':m,'k':k,'n':n,'weight_OC_pitch':bp,'jobs':jobs,'tiles':tiles,'outputs':m*n,'guard_and_padding':True})
   path.write_text(str(count)+'\n'+old+'\n'.join(lines)+'\n');return count
  matrix.base.vectors=vectors
  matrix.base.NATIVE=matrix.base.NATIVE.replace('mem[0:1048575]','mem[0:2097151]').replace("else if(a>=32'h07ff0000", "else if(a>=32'h02000000&&a<32'h02040000)mapped=32'h100000+(a-32'h02000000);else if(a>=32'h05000000&&a<32'h05080000)mapped=32'h140000+(a-32'h05000000);else if(a>=32'h07ff0000")
  # Keep the inherited legacy recovery fixture bound to its original low-address
  # Conv; new high-address static-weight cases must not replace that descriptor.
  matrix.base.MAIN=matrix.base.MAIN.replace("if(opn==8'h68)for", "if(opn==8'h68 && {payload[23],payload[22],payload[21],payload[20]}<32'h30000)for")
  original_main()
 matrix.base.main=execute
 if '--output' not in sys.argv:sys.argv+=['--output',str(ROOT/'build/npu-rtdetr-contract')]
 requested_out=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
 matrix.main()
 out=requested_out;(out/'rtdetr-result.json').write_text(json.dumps({'passed':True,'hardware_access':False,'source':'Unmodified4E24 real core/8OC/adapter; sparse native DDR model maps32MiB/80MiB windows','seed':0x52444732,'cases':records,'numeric_conv_outputs':sum(x['outputs']for x in records if x['kind']=='Conv'),'numeric_matrix_outputs':sum(x['outputs']for x in records if x['kind']!='Conv')},indent=2)+'\n')
if __name__=='__main__':main()
