"""Shape/policy arithmetic only: no model execution, RTL, or hardware access."""
from pathlib import Path
import argparse,struct,json,hashlib,math
HERE=Path(__file__).resolve().parent
HOST=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106')
def ceildiv(n,d):return(n+d-1)//d
def product(xs):return math.prod(xs)
def main():
 p=argparse.ArgumentParser();p.add_argument('--host',type=Path,default=HOST);p.add_argument('--output',type=Path,default=HERE/'budget.json');a=p.parse_args();host=a.host;meta=host/'build/rtdetr-graph-300-quant/metadata.bin';manifest=host/'build/rtdetr-graph-300-quant/manifest.json';raw=meta.read_bytes();h=struct.unpack_from('<32I',raw);assert h[0]==0x32475152 and h[1]==2;nt,nn=h[2:4];t=[]
 for i in range(nt):
  q=struct.unpack_from('<8IQQ4I',raw,128+i*64);t.append({'shape':q[:q[10]],'count':q[8]})
 binding_nodes={struct.unpack_from('<I',raw,h[12]+i*128)[0] for i in range(h[11])};names=json.loads(manifest.read_text())['node_names'];layers=[]
 for j in range(nn):
  off=128+nt*64+j*208;q=struct.unpack_from('<15i',raw,off);attrs=struct.unpack_from('<16q',raw,off+64)
  if q[0] not in [26,27,28]:continue
  X,W,Y=t[q[3]],t[q[4]],t[q[11]];x,w,y=X['shape'],W['shape'],Y['shape'];r={'node':j,'name':names[j],'op':{26:'Conv',27:'MatMul',28:'Gemm'}[q[0]],'A':x,'B':w,'output':y,'static_B':j in binding_nodes}
  if q[0]==26:
   batch,ic,ih,iw=x;_,oc,oh,ow=y;kh,kw=attrs[:2];assert batch==1 and attrs[10]==attrs[8]==attrs[9]==1
   iblocks=ceildiv(ic,16);oblocks=ceildiv(oc,8);spatial=ceildiv(oh,16)*ceildiv(ow,16)
   r.update(conv_tile_commands=iblocks*oblocks*spatial,matrix_panel_commands=0,internal_tiles=iblocks*oblocks*spatial,logical_MAC=product(y)*ic*kh*kw,
    engine_cycles=oblocks*oh*ow*(2*ic*kh*kw+3*iblocks),qA_write_bytes=ic*ih*ceildiv(iw,16)*16,qA_write_calls=ic*ih*ceildiv(ceildiv(iw,16)*16,256),qB_dynamic_write_bytes=0,
    A_scale_write_bytes=0,A_scale_read_bytes=0,B_scale_read_bytes=oc*4, bias_logical_read_bytes=oc*4 if q[1]>2 and q[5]>=0 else 0,
    A_FP32_logical_read_bytes=2*X['count']*4,B_dynamic_FP32_logical_read_bytes=0,INT32_C_logical_read_bytes=Y['count']*4,
    INT32_C_aligned_reply_bytes=oc*oh*ceildiv(ow,4)*16,output_FP32_logical_write_bytes=Y['count']*4)
  else:
   gemm=q[0]==28;rows=y[-2];cols=y[-1];k=x[0] if gemm and attrs[0] else x[-1];batches=Y['count']//rows//cols;collapse=not gemm and j in binding_nodes and len(w)==2
   if collapse:rows=Y['count']//cols;batches=1
   ap=ceildiv(rows,16)*16;kp=ceildiv(k,16)*16;np=ceildiv(cols,8);mp=ceildiv(rows,256);jobs=batches*np*mp;tiles=jobs*ceildiv(k,16)
   r.update(effective_rows=rows,effective_cols=cols,effective_K=k,effective_batches=batches,static_B_collapse=collapse,conv_tile_commands=0,matrix_panel_commands=jobs,internal_tiles=tiles,logical_MAC=batches*rows*k*cols,
    engine_cycles=batches*np*ap*(2*k+3*ceildiv(k,16)),qA_write_bytes=batches*ap*k,qA_write_calls=batches*ap*k//16,
    qB_dynamic_write_bytes=0 if j in binding_nodes else batches*cols*kp,A_scale_write_bytes=batches*rows*4,A_scale_read_bytes=batches*rows*4*np,
    B_scale_read_bytes=batches*cols*4 if j in binding_nodes else 0,bias_logical_read_bytes=Y['count']*4 if gemm and q[1]>2 and q[5]>=0 else 0,
    A_FP32_logical_read_bytes=batches*rows*k*8,B_dynamic_FP32_logical_read_bytes=0 if j in binding_nodes else batches*k*cols*8,
    INT32_C_logical_read_bytes=Y['count']*4,INT32_C_aligned_reply_bytes=batches*cols*ceildiv(rows,4)*16,output_FP32_logical_write_bytes=Y['count']*4)
  r['engine_seconds_27MHz']=r['engine_cycles']/27000000;r['MAC_command_request_response_bytes']=r['conv_tile_commands']*70+r['matrix_panel_commands']*54;layers.append(r)
 sums=['conv_tile_commands','matrix_panel_commands','internal_tiles','logical_MAC','engine_cycles','qA_write_bytes','qA_write_calls','qB_dynamic_write_bytes','A_scale_write_bytes','A_scale_read_bytes','B_scale_read_bytes','bias_logical_read_bytes','A_FP32_logical_read_bytes','B_dynamic_FP32_logical_read_bytes','INT32_C_logical_read_bytes','INT32_C_aligned_reply_bytes','output_FP32_logical_write_bytes','MAC_command_request_response_bytes']
 def total(ls):
  z={k:sum(q[k]for q in ls)for k in sums};z['engine_seconds_27MHz']=z['engine_cycles']/27000000;return z
 totals={'Conv':total([q for q in layers if q['op']=='Conv']),'MatMul_Gemm':total([q for q in layers if q['op']!='Conv']),'All_MAC':total(layers)}
 assert totals['Conv']['conv_tile_commands']==217280 and totals['MatMul_Gemm']['matrix_panel_commands']==13067
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();d={'scope':'Deterministic actualRQG2 shapes +current bounded backend policy arithmetic; NOT measured hardware time/throughput/FPS','hardware_access':False,'source_sha256':{str(p.relative_to(host)).replace('\\','/'):sha(p)for p in [meta,manifest,host/'main/inference/rtdetr_fpga_backend.cpp',host/'main/inference/rtdetr_fpga_backend.hpp']},'clock_Hz':27000000,'policy':'Conv OC8/OH16/OW16/IC16; staticrank2B MatMul collapses leadingA intoM; M256/N8 Matrix panels, IC16 internal; perlogicalrowAquant','units':'bytes=decimal bytes; seconds engine cycles/27MHz only','totals':totals,'layers':layers,'top_engine_layers':[q['node']for q in sorted(layers,key=lambda q:q['engine_cycles'],reverse=True)[:12]],'top_command_layers':[q['node']for q in sorted(layers,key=lambda q:q['conv_tile_commands']+q['matrix_panel_commands'],reverse=True)[:12]],'exclusions':['DDR loader/bridge/adapter/staging/PHY cycles','hostFP32quant/dequant/nonMACoperators','graphpagecache fill/writeback extra pages and evictions','MEM CRC framing/guard/RMW beyond explicit aligned INT32 replies','session/generation/counter-query commands','filesystem/input/display/cold model upload']}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(totals,indent=2))
if __name__=='__main__':main()
