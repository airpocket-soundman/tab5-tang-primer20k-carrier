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
struct Replay {
 ddr_matmul_test::Mock memory{32*1024*1024};mm::Workspace work;bool cache=false;
 std::uint64_t temp=0,read_bytes=0,write_bytes=0,read_calls=0,write_calls=0,tiles=0;
 static bool read(void*p,std::uint64_t a,void*d,std::size_t n){auto&c=*static_cast<Replay*>(p);c.read_bytes+=n;++c.read_calls;return ddr_matmul_test::Mock::read(&c.memory,a,d,n);}
 static bool write(void*p,std::uint64_t a,const void*d,std::size_t n){auto&c=*static_cast<Replay*>(p);c.write_bytes+=n;++c.write_calls;return ddr_matmul_test::Mock::write(&c.memory,a,d,n);}
 static bool tile(void*p,const inference::npu_ddr::Tile&t){auto&c=*static_cast<Replay*>(p);++c.tiles;return ddr_matmul_test::Mock::tile(&c.memory,t);}
 static bool unchanged(void*){return true;}static void abort(void*){assert(false&&"unexpected full replay abort");}
 static bool matmul(void*p,const tr::MatMul&op,const tr::Storage&){auto&c=*static_cast<Replay*>(p);mm::Request r;r.a={op.a.address,op.a.row_stride,op.a.column_stride};r.b={op.b.address,op.b.row_stride,op.b.column_stride};r.output={op.output.address,op.output.row_stride,op.output.column_stride};r.m=op.m;r.k=op.k;r.n=op.n;r.batches=op.batches;r.a_batch_stride=op.a.batch_stride;r.b_batch_stride=op.b.batch_stride;r.output_batch_stride=op.output.batch_stride;r.alpha=op.alpha;r.activation_per_row=true;r.cache_row_scales=c.cache;r.scratch_base=c.temp;r.scratch_bytes=mm::scratch_required(op.m,op.k,true,c.cache);mm::Backend b{&c,read,write,tile,unchanged,nullptr,abort};mm::Report report;return mm::run(r,b,c.work,report)&&report.valid;}
};
static std::vector<unsigned char> bytes(const char*name){std::ifstream f(name,std::ios::binary);assert(f);return{std::istreambuf_iterator<char>(f),{}};}
static std::uint32_t u32(const unsigned char*p){return std::uint32_t(p[0])|(std::uint32_t(p[1])<<8)|(std::uint32_t(p[2])<<16)|(std::uint32_t(p[3])<<24);}
int main(int argc,char**argv){assert(argc==5);const auto package=bytes(argv[1]),input=bytes(argv[2]),golden=bytes(argv[3]);assert(input.size()==3*224*224*4&&golden.size()==4000);std::vector<unsigned char> baseline;
 std::uint64_t before_read=0,before_write=0,before_rc=0,before_wc=0;
 for(bool cache:{false,true}){Replay c;c.cache=cache;const auto constants=u32(package.data()+20);const std::uint64_t cb=65536,arena=(cb+constants+15)&~UINT64_C(15);c.temp=(arena+tr::Model::arena_bytes+15)&~UINT64_C(15);std::memcpy(c.memory.ram.data()+cb,package.data()+2560,constants);std::memcpy(c.memory.ram.data()+arena,input.data(),input.size());tr::Model model;assert(model.load(package.data(),2560,package.size(),tr::crc32(package.data(),2560),cb,arena,c.memory.ram.size()));tr::Scratch scratch{};tr::Stats stats;tr::Storage storage{&c,Replay::read,Replay::write};tr::Hooks hooks;hooks.context=&c;hooks.matmul=Replay::matmul;assert(tr::run(model,storage,scratch,hooks,stats));assert(stats.blocks_completed==12&&stats.operations==199&&stats.matmul_operations==74&&stats.matmul_batches==122&&stats.cpu_matmul_operations==0&&c.tiles==51468);
  std::vector<unsigned char> actual(c.memory.ram.begin()+model.output_address(),c.memory.ram.begin()+model.output_address()+4000);assert(actual==golden);
  if(!cache){baseline=actual;before_read=c.read_bytes;before_write=c.write_bytes;before_rc=c.read_calls;before_wc=c.write_calls;assert(c.read_bytes==180940452&&c.write_bytes==73564960);}else{assert(actual==baseline);assert(before_read-c.read_bytes==2997956&&before_write-c.write_bytes==100736);assert(before_rc-c.read_calls==3929&&before_wc-c.write_calls==122);std::ofstream f(argv[4],std::ios::binary);f.write(reinterpret_cast<const char*>(actual.data()),actual.size());assert(f);}
  std::printf("PROFILE cache=%u blocks=%u operations=%u matmul=%u batches=%u tiles=%llu read=%llu write=%llu read_calls=%llu write_calls=%llu golden_bits=exact\n",unsigned(cache),stats.blocks_completed,stats.operations,stats.matmul_operations,stats.matmul_batches,(unsigned long long)c.tiles,(unsigned long long)c.read_bytes,(unsigned long long)c.write_bytes,(unsigned long long)c.read_calls,(unsigned long long)c.write_calls);
 }
 std::puts("PASS scale-cache full12block74MatMul all1000bits exact vs independent nativeINT8 golden; no hardware");
}
