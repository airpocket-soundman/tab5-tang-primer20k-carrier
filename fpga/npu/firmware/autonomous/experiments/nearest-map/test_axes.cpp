#include "build/generated/rtdetr_graph.cpp"
#include <vector>
#include <cstdio>
#include <cassert>
#include <limits>
using namespace inference::rtdetr;
struct Mem{std::vector<unsigned char>b;unsigned writes=0,calls=0,cancel_at=~0u;};
bool read(void*c,std::uint64_t a,void*p,std::size_t n){auto&m=*static_cast<Mem*>(c);if(a>m.b.size()||n>m.b.size()-a)return false;std::memcpy(p,m.b.data()+a,n);return true;}
bool write(void*c,std::uint64_t a,const void*p,std::size_t n){auto&m=*static_cast<Mem*>(c);if(a>m.b.size()||n>m.b.size()-a)return false;std::memcpy(m.b.data()+a,p,n);++m.writes;return true;}
const void*map(void*c,std::uint64_t a,std::size_t n){auto&m=*static_cast<Mem*>(c);return a<=m.b.size()&&n<=m.b.size()-a?m.b.data()+a:nullptr;}
bool cancel(void*c){auto&m=*static_cast<Mem*>(c);return m.calls++==m.cancel_at;}
void test(std::initializer_list<unsigned>is,std::initializer_list<unsigned>os){Tensor t[2]{};unsigned j=0;for(auto dims:{is,os}){auto&x=t[j++];x.rank=dims.size();x.type=1;x.count=1;unsigned i=0;for(auto d:dims){x.d[i++]=d;x.count*=d;}}assert(resize_mapped_eligible(t[0],t[1]));t[1].offset=t[0].count*4;Model model;model.t=t;model.nt=2;Mem mem;mem.b.resize((t[0].count+t[1].count)*4+16,0xa5);for(unsigned i=0;i<t[0].count;++i){std::uint32_t bits=(i%17==0)?0x7fc01234u:(i%19==0)?0x80000000u:0x3f000000u+i;std::memcpy(mem.b.data()+i*4,&bits,4);}GraphStorage s;s.context=&mem;s.read=read;s.write=write;s.map=map;s.cancelled=cancel;bool ok=true;A x(model,0,s,ok);assert(resize_mapped(model,1,s,x,ok)&&ok);assert(mem.calls==(t[1].count+127)/128);
for(unsigned i=0;i<t[1].count;++i){std::uint64_t tail=t[1].count,source=0;for(unsigned d=0;d<t[1].rank;++d){tail/=t[1].d[d];const auto c=(i/tail)%t[1].d[d];source=source*t[0].d[d]+std::min<std::uint64_t>(t[0].d[d]-1,std::uint64_t(c)*t[0].d[d]/t[1].d[d]);}float v;std::memcpy(&v,mem.b.data()+source*4,4);double wide=v;float expected=float(wide);assert(!std::memcmp(mem.b.data()+t[1].offset+i*4,&expected,4));}for(unsigned i=0;i<16;++i)assert(mem.b[(t[0].count+t[1].count)*4+i]==0xa5);
mem.calls=mem.writes=0;mem.cancel_at=0;assert(!resize_mapped(model,1,s,x,ok));assert(mem.calls==1&&mem.writes==0);
}
int main(){test({1,3,5,7},{1,3,5,7});test({2,3,3,5},{2,3,7,11});test({2,3,7,11},{2,3,3,5});test({13},{29});test({4096},{4096});test({1,2,1,2,1,2,1,2},{2,1,2,1,2,1,2,1});Tensor a{},b{};a.rank=b.rank=1;a.d[0]=1;b.d[0]=4097;assert(!resize_mapped_eligible(a,b));b.d[0]=0;assert(!resize_mapped_eligible(a,b));b.rank=2;assert(!resize_mapped_eligible(a,b));a.rank=b.rank=0;assert(!resize_mapped_eligible(a,b));std::puts("PASS six actual-helper shapes,4096bound,NaN/signedzero,128chunks,cancel,nooverflowguard;fourfallbacks");}
