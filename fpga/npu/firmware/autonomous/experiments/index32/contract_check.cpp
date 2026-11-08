#include "index32_contract.hpp"
#include <vector>
#include <fstream>
#include <cstdio>
#include <cstring>
#include <cassert>
using namespace inference::rtdetr;
int main(int argc,char**argv){assert(argc==2);std::ifstream f(argv[1],std::ios::binary);std::vector<unsigned char>b((std::istreambuf_iterator<char>(f)),{});auto*h=reinterpret_cast<const unsigned*>(b.data());Model m;assert(m.load(b.data(),h[6],65536,(65536ull+h[7]+15)&~15ull,128u*1024u*1024u));const char*why="none";assert(index32::validate(m,why));unsigned cases=0;
 auto reject=[&](Model&v){why="none";assert(!index32::validate(v,why));++cases;std::printf("reject %s\n",why);};
 auto v=m;v.nt=951;reject(v);v=m;v.arena_base=index32::limit;reject(v);
 std::vector<Tensor>t(m.t,m.t+m.nt);v=m;v.t=t.data();t[m.input].count=UINT64_C(1)<<25;reject(v);t.assign(m.t,m.t+m.nt);t[m.input].offset=index32::limit+1;reject(v);
 std::vector<QuantizedBinding>q(m.q,m.q+m.nq);v=m;v.q=q.data();q[0].data_offset=index32::limit;reject(v);
 std::vector<unsigned char>header(m.header,m.header+128);v=m;v.header=header.data();header[36]^=1;reject(v);
 // A post-load table fixture makes Resize the only coordinate transform. Every
 // tensor extent still fits80MiB, but65536x65536 cross multiplication overflowsU32.
 t.assign(m.t,m.t+m.nt);for(unsigned id=0;id<2;++id){t[id]={};t[id].rank=1;t[id].d[0]=65536;t[id].count=65536;t[id].type=1;t[id].offset=0;}
 std::vector<Node>n(m.nn);for(auto&node:n){node.op=Tile;node.ni=node.no=1;node.input[0]=0;node.output[0]=1;}
 v=m;v.t=t.data();v.n=n.data();assert(index32::validate(v,why));n[0].op=Resize;reject(v);
 n[0].op=Slice;n[0].a[0]=65535;n[0].a[8]=2;reject(v);
 assert(cases==8);std::printf("PASS8 index32 contract guards; canonical modelaccepted; Model.load unchanged\n");}
