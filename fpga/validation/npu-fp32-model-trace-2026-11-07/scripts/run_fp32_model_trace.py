"""Instrument copies only: full DeiT native replay -> stratified FP32 RTL proof."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,struct,os,importlib.util,gzip
ROOT=Path(__file__).resolve().parents[3]
def main():
 p=argparse.ArgumentParser();p.add_argument('--host',type=Path,default=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106'));p.add_argument('--image',choices=['CREW','ASTRONAUT','CROP'],default='CREW');p.add_argument('--compiler',default='D:/GitHub/airpocket-soundman/tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe');p.add_argument('--output',type=Path,default=ROOT/'fpga/build/epilogue-model-trace');a=p.parse_args();host=a.host.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);snap=out/'source_snapshot';hashes={}
 names=['main/inference/ddr_matmul.cpp','main/inference/ddr_matmul.hpp','main/inference/npu_ddr_transport.hpp','main/inference/transformer_graph.cpp','main/inference/transformer_graph.hpp','tests/ddr_matmul_mock.hpp','tools/ddr_matmul_scale_cache_replay.cpp']
 for n in names:
  dest=snap/n.removeprefix('main/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(host/n,dest);hashes[n]=hashlib.sha256(dest.read_bytes()).hexdigest()
 cpp=snap/'inference/ddr_matmul.cpp';s=cpp.read_text();decl='extern "C" void epilogue_trace(int,float,float,float,unsigned,unsigned,unsigned,float);\n';s=decl+s
 needle='w.line[row]=float(w.sums[row])*((r.activation_per_row?w.a_scales[row]:as)*w.scales[col])*r.alpha;'
 assert s.count(needle)==1;s=s.replace(needle,needle+'epilogue_trace(w.sums[row],r.activation_per_row?w.a_scales[row]:as,w.scales[col],r.alpha,mb+row,nb+col,batch,w.line[row]);')
 needle='w.block[col*16+row]=float(w.sums[row])*((r.activation_per_row?w.a_scales[pixel+row]:as)*w.scales[col])*r.alpha;'
 assert s.count(needle)==1;s=s.replace(needle,needle+'epilogue_trace(w.sums[row],r.activation_per_row?w.a_scales[pixel+row]:as,w.scales[col],r.alpha,mb+pixel+row,nb+col,batch,w.block[col*16+row]);');cpp.write_text(s)
 base=(snap/'tools/ddr_matmul_scale_cache_replay.cpp').read_text();prefix=base[:base.index('struct Replay {')]
 harness=prefix+r'''
static const tr::MatMul*active=nullptr;static const tr::Model*model_ptr=nullptr;
static ddr_matmul_test::Mock*mem_ptr=nullptr;static FILE*trace_file=nullptr;
static unsigned traces=0,biased=0;
static std::uint32_t fb(float x){std::uint32_t v;std::memcpy(&v,&x,4);return v;}
extern "C" void epilogue_trace(int sum,float as,float bs,float alpha,unsigned row,unsigned col,unsigned batch,float value){
 assert(active&&trace_file);const auto&op=*active;
 if(row!=0&&row!=op.m/2&&row!=op.m-1)return;
 float bias=0;bool en=false;
 for(unsigned id=0;id<tr::Model::weight_count;id++)if(model_ptr->weight(id).address==op.b.address){
  auto w=model_ptr->weight(id+1);assert(w.count==op.n);std::memcpy(&bias,mem_ptr->ram.data()+w.address+col*4,4);en=true;break;}
 const float expected=en?value+bias:value;
 const std::uint32_t rec[]={op.operation,batch,row,col,std::uint32_t(sum),fb(as),fb(bs),fb(alpha),fb(bias),unsigned(en),fb(expected)};
 assert(std::fwrite(rec,sizeof(rec),1,trace_file)==1);++traces;if(en)++biased;
}
'''
 replay=base[base.index('struct Replay {'):base.index('static std::vector<unsigned char> bytes')]
 replay=replay.replace('mm::Report report;return mm::run(r,b,c.work,report)&&report.valid;','active=&op;std::printf("OP %u %u %u %u\\n",op.operation,op.m,op.n,op.batches);mm::Report report;const bool ok=mm::run(r,b,c.work,report)&&report.valid;active=nullptr;return ok;')
 harness+=replay+base[base.index('static std::vector<unsigned char> bytes'):base.index('int main(')]
 harness+=r'''
int main(int argc,char**argv){assert(argc==6);auto package=bytes(argv[1]),input=bytes(argv[2]),golden=bytes(argv[3]);assert(input.size()==602112&&golden.size()==4000);trace_file=std::fopen(argv[5],"wb");assert(trace_file);
 Replay c;const auto constants=u32(package.data()+20);const std::uint64_t cb=65536,arena=(cb+constants+15)&~UINT64_C(15);c.temp=(arena+tr::Model::arena_bytes+15)&~UINT64_C(15);std::memcpy(c.memory.ram.data()+cb,package.data()+2560,constants);std::memcpy(c.memory.ram.data()+arena,input.data(),input.size());tr::Model model;assert(model.load(package.data(),2560,package.size(),tr::crc32(package.data(),2560),cb,arena,c.memory.ram.size()));model_ptr=&model;mem_ptr=&c.memory;
 tr::Scratch scratch{};tr::Stats stats;tr::Storage storage{&c,Replay::read,Replay::write};tr::Hooks hooks;hooks.context=&c;hooks.matmul=Replay::matmul;hooks.progress=[](void*,const char*,unsigned,unsigned){};
 assert(tr::run(model,storage,scratch,hooks,stats));assert(stats.blocks_completed==12&&stats.operations==199&&stats.matmul_operations==74&&stats.matmul_batches==122&&c.tiles==51468);
 std::vector<unsigned char>actual(c.memory.ram.begin()+model.output_address(),c.memory.ram.begin()+model.output_address()+4000);assert(actual==golden);std::ofstream f(argv[4],std::ios::binary);f.write(reinterpret_cast<const char*>(actual.data()),4000);std::fclose(trace_file);
 std::printf("PASS fullgraph golden1000bits exact samples=%u biased=%u blocks12 ops199 MatMul74 batches122 tiles51468 nohardware\n",traces,biased);
}
'''
 (snap/'trace.cpp').write_text(harness)
 commands=[]
 def run(cmd,timeout=600):
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout);commands.append({'command':list(map(str,cmd)),'returncode':r.returncode,'output':r.stdout+r.stderr});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stdout+r.stderr;return r.stdout
 exe=out/'trace.exe';run([a.compiler,'c++','-std=c++17','-O2','-march=native','-ffp-contract=fast','-UNDEBUG','-Wall','-Wextra','-Werror','-I'+str(snap),'-I'+str(snap/'tests'),str(snap/'trace.cpp'),str(cpp),str(snap/'inference/transformer_graph.cpp'),'-o',str(exe)],180)
 model=host/'build/transformer-deit-tiny-fm/model.dtp';image=host/f'build/transformer-sd-fm-v1/images/{a.image}.F32';golden=host/f'build/transformer-rowwise-final/{a.image}-rowwise-fast.f32';actual=out/'actual.f32';trace=out/'samples.bin';log=run([str(exe),str(model),str(image),str(golden),str(actual),str(trace)]);print(log[-250:])
 spec=importlib.util.spec_from_file_location('epilogue_oracle',ROOT/'fpga/npu/tests/run_fp32_epilogue.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
 data=trace.read_bytes();assert len(data)%44==0;lines=[];coverage={};bias_count=0
 for n,rec in enumerate(struct.iter_unpack('<11I',data)):
  op,batch,row,col,i,x,y,z,b,en,expected=rec;i=i if i<2**31 else i-2**32
  value,err=ref.oracle(i,x,y,z,b,en);assert err==0 and value==expected,(n,rec,value,err)
  lines.append(f'{n} {i&0xffffffff:08x} {x:08x} {y:08x} {z:08x} {b:08x} {en} {expected:08x} 0');coverage.setdefault(op,set()).add((batch,row,col));bias_count+=en
 ops=[]
 for line in log.splitlines():
  if line.startswith('OP '):
   _,op,m,nn,batches=map(str,line.split());op,m,nn,batches=map(int,[op,m,nn,batches]);want={(ba,row,col) for ba in range(batches) for row in {0,m//2,m-1} for col in range(nn)};assert coverage[op]==want;ops.append({'operation':op,'m':m,'n':nn,'batches':batches,'samples':len(want)})
 assert len(ops)==74 and sum(o['batches'] for o in ops)==122
 vectors=out/'vectors.txt';vectors.write_text('\n'.join(lines)+'\n');(out/'tb.v').write_text(ref.TB.replace('VECTORS',vectors.as_posix()).replace('#100000000;','#200000000;'))
 tool=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin');os.environ['PATH']=str(tool)+os.pathsep+os.environ['PATH'];rtl=ROOT/'fpga/npu/rtl/npu_fp32_epilogue.v';run([str(tool/'iverilog.exe'),'-g2012','-s','tb','-o',str(out/'test.vvp'),str(rtl),str(out/'tb.v')]);print(run([str(tool/'vvp.exe'),str(out/'test.vvp')]))
 with gzip.GzipFile(filename=str(out/'samples.bin.gz'),mode='wb',mtime=0) as f:f.write(data)
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 result={'passed':True,'image':a.image,'hardware_access':False,'sampling':'Rows0,floor(M/2),M-1; every output column and batch of all74MatMul, NOT all outputs','samples':len(lines),'biased_samples':bias_count,'dynamic_no_bias_samples':len(lines)-bias_count,'operations':ops,'graph_output_bit_exact':actual.read_bytes()==golden.read_bytes(),'input_sha256':sha(image),'package_sha256':sha(model),'golden_sha256':sha(golden),'actual_sha256':sha(actual),'rtl_sha256':sha(rtl),'host_original_sha256':hashes,'instrumented_cpp_sha256':sha(cpp),'trace_sha256':sha(trace),'trace_format':'11uint32LE:operation,batch,row,col,signed_sum_bits,as,bs,alpha,bias,bias_enable,expectedFP32bits'}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS samples',len(lines),'bias',bias_count)
 assert all(hashlib.sha256((host/n).read_bytes()).hexdigest()==v for n,v in hashes.items()),'Production host source changed during proof'
if __name__=='__main__':main()
