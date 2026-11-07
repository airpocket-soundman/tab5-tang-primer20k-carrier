// Offline full Deit replay: same graph + independent INT64 tile oracle,
// comparing legacy row-scale spill vs opt-in cache. No transport/device code.
#include "inference/ddr_matmul.hpp"
#include "inference/transformer_graph.hpp"
#include "ddr_matmul_mock.hpp"
#include <fstream>
#include <vector>
#include <cstring>
#include <cassert>
#include <cstdio>
namespace tr=inference::transformer;namespace mm=inference::ddr_matmul;

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
struct Replay {
 ddr_matmul_test::Mock memory{32*1024*1024};mm::Workspace work;bool cache=false;
 std::uint64_t temp=0,read_bytes=0,write_bytes=0,read_calls=0,write_calls=0,tiles=0;
 static bool read(void*p,std::uint64_t a,void*d,std::size_t n){auto&c=*static_cast<Replay*>(p);c.read_bytes+=n;++c.read_calls;return ddr_matmul_test::Mock::read(&c.memory,a,d,n);}
 static bool write(void*p,std::uint64_t a,const void*d,std::size_t n){auto&c=*static_cast<Replay*>(p);c.write_bytes+=n;++c.write_calls;return ddr_matmul_test::Mock::write(&c.memory,a,d,n);}
 static bool tile(void*p,const inference::npu_ddr::Tile&t){auto&c=*static_cast<Replay*>(p);++c.tiles;return ddr_matmul_test::Mock::tile(&c.memory,t);}
 static bool unchanged(void*){return true;}static void abort(void*){assert(false&&"unexpected full replay abort");}
 static bool matmul(void*p,const tr::MatMul&op,const tr::Storage&){auto&c=*static_cast<Replay*>(p);mm::Request r;r.a={op.a.address,op.a.row_stride,op.a.column_stride};r.b={op.b.address,op.b.row_stride,op.b.column_stride};r.output={op.output.address,op.output.row_stride,op.output.column_stride};r.m=op.m;r.k=op.k;r.n=op.n;r.batches=op.batches;r.a_batch_stride=op.a.batch_stride;r.b_batch_stride=op.b.batch_stride;r.output_batch_stride=op.output.batch_stride;r.alpha=op.alpha;r.activation_per_row=true;r.cache_row_scales=c.cache;r.scratch_base=c.temp;r.scratch_bytes=mm::scratch_required(op.m,op.k,true,c.cache);mm::Backend b{&c,read,write,tile,unchanged,nullptr,abort};active=&op;std::printf("OP %u %u %u %u\n",op.operation,op.m,op.n,op.batches);mm::Report report;const bool ok=mm::run(r,b,c.work,report)&&report.valid;active=nullptr;return ok;}
};
static std::vector<unsigned char> bytes(const char*name){std::ifstream f(name,std::ios::binary);assert(f);return{std::istreambuf_iterator<char>(f),{}};}
static std::uint32_t u32(const unsigned char*p){return std::uint32_t(p[0])|(std::uint32_t(p[1])<<8)|(std::uint32_t(p[2])<<16)|(std::uint32_t(p[3])<<24);}

int main(int argc,char**argv){assert(argc==6);auto package=bytes(argv[1]),input=bytes(argv[2]),golden=bytes(argv[3]);assert(input.size()==602112&&golden.size()==4000);trace_file=std::fopen(argv[5],"wb");assert(trace_file);
 Replay c;const auto constants=u32(package.data()+20);const std::uint64_t cb=65536,arena=(cb+constants+15)&~UINT64_C(15);c.temp=(arena+tr::Model::arena_bytes+15)&~UINT64_C(15);std::memcpy(c.memory.ram.data()+cb,package.data()+2560,constants);std::memcpy(c.memory.ram.data()+arena,input.data(),input.size());tr::Model model;assert(model.load(package.data(),2560,package.size(),tr::crc32(package.data(),2560),cb,arena,c.memory.ram.size()));model_ptr=&model;mem_ptr=&c.memory;
 tr::Scratch scratch{};tr::Stats stats;tr::Storage storage{&c,Replay::read,Replay::write};tr::Hooks hooks;hooks.context=&c;hooks.matmul=Replay::matmul;hooks.progress=[](void*,const char*,unsigned,unsigned){};
 assert(tr::run(model,storage,scratch,hooks,stats));assert(stats.blocks_completed==12&&stats.operations==199&&stats.matmul_operations==74&&stats.matmul_batches==122&&c.tiles==51468);
 std::vector<unsigned char>actual(c.memory.ram.begin()+model.output_address(),c.memory.ram.begin()+model.output_address()+4000);assert(actual==golden);std::ofstream f(argv[4],std::ios::binary);f.write(reinterpret_cast<const char*>(actual.data()),4000);std::fclose(trace_file);
 std::printf("PASS fullgraph golden1000bits exact samples=%u biased=%u blocks12 ops199 MatMul74 batches122 tiles51468 nohardware\n",traces,biased);
}
