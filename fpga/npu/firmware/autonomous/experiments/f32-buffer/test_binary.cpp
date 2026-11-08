#include "build/generated/rtdetr_graph.cpp"
#include <vector>
#include <cstdio>
#include <cassert>
#include <array>
using namespace inference::rtdetr;
struct Mem{std::vector<unsigned char>b;std::vector<std::array<std::uint64_t,3>>trace;unsigned checks=0,stop=~0u;};
bool rd(void*c,std::uint64_t a,void*p,std::size_t n){auto&m=*static_cast<Mem*>(c);m.trace.push_back({0,a,n});if(a>m.b.size()||n>m.b.size()-a)return false;std::memcpy(p,m.b.data()+a,n);return true;}
bool wr(void*c,std::uint64_t a,const void*p,std::size_t n){auto&m=*static_cast<Mem*>(c);m.trace.push_back({1,a,n});if(a>m.b.size()||n>m.b.size()-a)return false;std::memcpy(m.b.data()+a,p,n);return true;}
const void*mp(void*c,std::uint64_t a,std::size_t n){auto&m=*static_cast<Mem*>(c);return a<=m.b.size()&&n<=m.b.size()-a?m.b.data()+a:nullptr;}
bool cancel(void*c){auto&m=*static_cast<Mem*>(c);return m.checks++==m.stop;}
// Original index32 generic Add/Sub/Mul: same actual A::get, coords,broadcast,put.
bool original(const Model&m,const Node&q,const GraphStorage&s,A&x,A&y,bool&ok){const auto&o=m.t[q.output[0]];double values[128];for(std::uint32_t base=0;base<o.count;base+=128){if(s.cancelled&&s.cancelled(s.context))return false;unsigned count=unsigned(std::min<std::uint32_t>(128,o.count-base));for(unsigned j=0;j<count;++j){std::uint32_t c[8]{};coords(o,base+j,c);const float a=float(x.get(broadcast(x.t,o,c)));const float b=float(y.get(broadcast(y.t,o,c)));double v=0;switch(q.op){case Add:v=a+b;break;case Sub:v=a-b;break;case Mul:v=a*b;break;default:return false;}values[j]=v;}if(!ok||!put(m,unsigned(q.output[0]),s,base,values,count))return false;}return true;}
int main(){unsigned tests=0;const std::uint32_t edges[]={0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc01234,0xffa01234};
for(int op:{Add,Sub,Mul})for(unsigned shape=0;shape<3;++shape)for(unsigned alias=0;alias<3;++alias)for(unsigned mapped=0;mapped<2;++mapped)for(unsigned exceptional=0;exceptional<2;++exceptional)for(unsigned stop:{~0u,0u,1u,2u}){
 Tensor t[3]{};for(auto&z:t){z.rank=2;z.type=1;z.count=514;z.d[0]=2;z.d[1]=257;}if(shape==1){t[1].rank=0;t[1].count=1;}if(shape==2){t[1].rank=1;t[1].count=257;t[1].d[0]=257;}t[0].offset=0;t[1].offset=4096;t[2].offset=8192;if(alias==1)t[2].offset=t[0].offset;if(alias==2&&shape==0)t[2].offset=t[1].offset;
 Mem base;base.b.resize(12288,0xa5);base.stop=stop;for(unsigned id=0;id<2;++id)for(unsigned i=0;i<t[id].count;++i){auto bits=edges[(i*7+id*3)%(exceptional?14:10)];std::memcpy(base.b.data()+t[id].offset+i*4,&bits,4);}Mem candidate=base;Model m;m.t=t;m.nt=3;Node q{};q.op=op;q.ni=2;q.no=1;q.input[0]=0;q.input[1]=1;q.output[0]=2;GraphStorage s;s.context=&base;s.read=rd;s.write=wr;s.cancelled=cancel;s.map=mapped?mp:nullptr;bool oka=true;A ax(m,0,s,oka),ay(m,1,s,oka);bool ra=original(m,q,s,ax,ay,oka);s.context=&candidate;bool okb=true;A bx(m,0,s,okb),by(m,1,s,okb);bool rb=f32_binary(m,q,s,bx,by,okb);assert(ra==rb&&oka==okb&&base.b==candidate.b&&base.trace==candidate.trace&&base.checks==candidate.checks);++tests;
}
std::printf("PASS %u cases Add/Sub/Mul, finite/NaN/Inf,subnormal,signedzero,overflow,inplace,broadcast,map/cache,128chunks,cancel+exactIOtrace\n",tests);}
