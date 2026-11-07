"""Read typed RQG2 metadata independently for carrier bounds/shape compatibility."""
from pathlib import Path
import argparse,struct,json,hashlib,collections,math
ROOT=Path(__file__).resolve().parents[3]
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',type=Path,default=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106/build/rtdetr-graph-300-quant/metadata.bin'));p.add_argument('--manifest',type=Path,default=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106/build/rtdetr-graph-300-quant/manifest.json'));p.add_argument('--output',type=Path,default=ROOT/'fpga/build/npu-rtdetr-shape-audit');a=p.parse_args();raw=a.metadata.read_bytes();h=struct.unpack_from('<32I',raw);assert h[0]==0x32475152 and h[1]==2;nt,nn=h[2:4];assert len(raw)==h[6];t=[]
 for i in range(nt):
  v=struct.unpack_from('<8IQQ4I',raw,128+i*64);t.append({'dims':v[:v[10]],'count':v[8],'offset':v[9],'type':v[11],'constant':v[12]})
 bindings={}
 for i in range(h[11]):
  v=struct.unpack_from('<8I2Q9I32s3I',raw,h[12]+i*128);assert v[0] not in bindings
  assert v[5]%16==0 and v[5]>=v[3] and v[5]*v[4]==v[6] and v[8]%16==v[9]%16==0
  assert v[8]+v[6]<=h[7] and v[9]+v[7]<=h[7]
  bindings[v[0]]={'kind':v[2],'k':v[3],'n':v[4],'pitch':v[5],'data_bytes':v[6],'scale_bytes':v[7],'data_offset':v[8],'scale_offset':v[9]}
 conv=[];mm=[]
 for j in range(nn):
  off=128+nt*64+j*208;v=struct.unpack_from('<15i',raw,off);attr=struct.unpack_from('<16q',raw,off+64);f=struct.unpack_from('<4f',raw,off+192)
  if v[0]==26:
   x,w,y=t[v[3]],t[v[4]],t[v[11]];assert j in bindings and bindings[j]['kind']==1
   assert attr[0]==attr[1] and attr[0] in [1,3] and attr[2]==attr[3] and attr[2] in [1,2] and attr[8]==attr[9]==attr[10]==1
   assert attr[4]==attr[6] and attr[5]==attr[7] and attr[4] in [0,1] and attr[5] in [0,1]
   assert bindings[j]['k']==w['dims'][1]*w['dims'][2]*w['dims'][3] and bindings[j]['n']==w['dims'][0]
   conv.append({'node':j,'input':x['dims'],'weight':w['dims'],'output':y['dims'],'attributes':attr[:11],'binding':bindings[j]})
  if v[0] in [27,28]:
   x,w,y=t[v[3]],t[v[4]],t[v[11]];assert max(x['dims'])<=65535 and max(y['dims'])<=65535
   if v[0]==28:assert attr[0]==0 and attr[1]==1 and f[0]==f[1]==1
   mm.append({'node':j,'op':'Gemm' if v[0]==28 else 'MatMul','a':x['dims'],'b':w['dims'],'output':y['dims'],'flags':attr[:2],'alpha_beta':f[:2],'static':j in bindings,'binding':bindings.get(j)})
 assert len(conv)==57 and len(mm)==65 and len(bindings)==114 and sum(not q['static']for q in mm)==8
 conv_tiles=sum(math.ceil(c['weight'][0]/8)*math.ceil(c['output'][2]/16)*math.ceil(c['output'][3]/16)*math.ceil(c['weight'][1]/16)for c in conv)
 conv_mac=sum(math.prod(c['output'])*math.prod(c['weight'][1:])for c in conv)
 cycles=sum(math.ceil(c['weight'][0]/8)*c['output'][0]*c['output'][2]*c['output'][3]*(2*math.prod(c['weight'][1:])+3*math.ceil(c['weight'][1]/16))for c in conv)
 m=json.loads(a.manifest.read_text());assert h[7]==m['payload_bytes'] and h[8]==m['arena_bytes'];assert m['scratch_base']+m['scratch_available_bytes']==134217728
 result={'passed':True,'hardware_access':False,'scope':'Metadata shapes/address-contract audit only; not runtime/model inference proof','metadata_sha256':hashlib.sha256(raw).hexdigest(),'manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),'RQG2_package_sha256':m['package_sha256'],'source_sha256':m['source_sha256'],'memory':{k:m[k]for k in ['payload_bytes','arena_bytes','constant_plus_arena_bytes','control_base_bytes','scratch_base','scratch_available_bytes']},'conv_attributes':{str(k):v for k,v in collections.Counter((q['attributes'][0],q['attributes'][2])for q in conv).items()},'conv':conv,'matmul':mm,'estimates':{'conv_tile_jobs':conv_tiles,'conv_MAC':conv_mac,'conv_engine_cycles':cycles,'conv_compute_only_seconds_27MHz':cycles/27e6,'conv_qinput_bytes_total':sum(q['input'][0]*q['input'][1]*q['input'][2]*((q['input'][3]+15)//16*16)for q in conv),'max_conv_qinput_bytes':max(q['input'][1]*q['input'][2]*((q['input'][3]+15)//16*16)for q in conv),'conv_FP32_outputs_bytes':sum(math.prod(q['output'])*4 for q in conv)}}
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS 57Conv/65MatMul RQG2 shapes,pitches,bounds;',m['scratch_available_bytes'],'scratch bytes')
if __name__=='__main__':main()
