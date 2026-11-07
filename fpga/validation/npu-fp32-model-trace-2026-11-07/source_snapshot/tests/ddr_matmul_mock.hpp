#pragma once
// Native-only reusable INT32 DDR/1x1Conv test double. Never firmware fallback.
#include "inference/ddr_matmul.hpp"
#include <vector>
#include <cstdio>
#include <cstring>
#include <cassert>
namespace ddr_matmul_test {
namespace dm=inference::ddr_matmul;namespace nd=inference::npu_ddr;
struct Mock {
 std::vector<unsigned char> ram;
 explicit Mock(std::size_t bytes=8*1024*1024):ram(bytes,0xa5){}
 std::vector<std::int32_t> acc;
 unsigned calls=0,tiles=0,aborts=0,fail_at=0,cancel_at=0,change_at=0;
 unsigned fail_tile=0;bool live=true;FILE*trace=nullptr;std::uint64_t scratch=0,scratch_end=0,qo=0;
 static void hex(FILE*f,const void*p,std::size_t n){const auto*b=static_cast<const unsigned char*>(p);for(std::size_t i=0;i<n;i++)std::fprintf(f,"%02x",b[i]);}
 bool gate(){++calls;return !fail_at||calls!=fail_at;}
 static bool read(void*p,std::uint64_t a,void*d,std::size_t n){auto&m=*static_cast<Mock*>(p);if(!m.gate()||a+n>m.ram.size())return false;std::memcpy(d,m.ram.data()+a,n);if(m.trace&&a>=m.qo&&a<m.scratch_end){const std::size_t span=(n+15)&~std::size_t(15);assert(a%16==0);std::fprintf(m.trace,"R %llu %zu ",(unsigned long long)a,span);hex(m.trace,m.ram.data()+a,span);std::fputc('\n',m.trace);}return true;}
 static bool write(void*p,std::uint64_t a,const void*d,std::size_t n){auto&m=*static_cast<Mock*>(p);if(!m.gate()||a+n>m.ram.size())return false;std::memcpy(m.ram.data()+a,d,n);if(m.trace&&a>=m.scratch&&a<m.scratch_end){assert(a%16==0&&n%16==0);std::fprintf(m.trace,"W %llu %zu ",(unsigned long long)a,n);hex(m.trace,d,n);std::fputc('\n',m.trace);}return true;}
 static void put32(unsigned char*p,std::uint32_t x){for(unsigned i=0;i<4;i++)p[i]=x>>(8*i);}
 static bool tile(void*p,const nd::Tile&t){auto&m=*static_cast<Mock*>(p);if(!m.gate())return false;assert(t.kernel==1&&t.stride==1&&t.ic<=16&&t.oc<=8&&t.oh<=16&&t.ow<=16);++m.tiles;if(m.fail_tile&&m.tiles==m.fail_tile)return false;
  if(m.trace){unsigned char d[52]{};d[0]=t.ic;d[1]=t.oc;d[2]=t.oh;d[3]=t.ow;d[4]=d[5]=1;d[6]=(t.first?1:0)|(t.final?2:0)|4;d[8]=t.full_h;d[9]=t.full_h>>8;d[10]=t.full_w;d[11]=t.full_w>>8;put32(d+12,t.origin_y);put32(d+16,t.origin_x);put32(d+20,t.input_base);put32(d+24,t.input_row_pitch);put32(d+28,t.input_channel_pitch);put32(d+32,t.weight_base);put32(d+36,t.weight_oc_stride);put32(d+40,t.output_base);put32(d+44,t.output_row_pitch);put32(d+48,t.output_channel_pitch);std::fputs("T ",m.trace);hex(m.trace,d,52);std::fputc('\n',m.trace);}
  const unsigned plane=t.oh*t.ow;
  if(t.first)m.acc.assign(t.oc*plane,0);assert(m.acc.size()==t.oc*plane);
  for(unsigned o=0;o<t.oc;o++)for(unsigned y=0;y<t.oh;y++)for(unsigned x=0;x<t.ow;x++){
   std::int64_t v=m.acc[o*plane+y*t.ow+x];
   for(unsigned k=0;k<t.ic;k++){const auto a=std::int8_t(m.ram[t.input_base+k*t.input_channel_pitch+(t.origin_y+y)*t.input_row_pitch+t.origin_x+x]);const auto b=std::int8_t(m.ram[t.weight_base+o*t.weight_oc_stride+k]);v+=int(a)*int(b);}
   if(v<INT32_MIN||v>INT32_MAX)return false;m.acc[o*plane+y*t.ow+x]=std::int32_t(v);
  }
  if(t.final)for(unsigned o=0;o<t.oc;o++)for(unsigned y=0;y<t.oh;y++){auto*dst=m.ram.data()+t.output_base+o*t.output_channel_pitch+y*t.output_row_pitch;std::memcpy(dst,m.acc.data()+o*plane+y*t.ow,t.ow*4);std::memset(dst+t.ow*4,0,((t.ow+3)/4*4-t.ow)*4);}return true;
 }
 static bool unchanged(void*p){auto&m=*static_cast<Mock*>(p);return m.live&&(!m.change_at||m.calls<m.change_at);}
 static bool cancelled(void*p){auto&m=*static_cast<Mock*>(p);return m.cancel_at&&m.calls>=m.cancel_at;}
 static void abort(void*p){++static_cast<Mock*>(p)->aborts;}
 dm::Backend backend(){return{this,read,write,tile,unchanged,cancelled,abort};}
 void put(std::uint64_t a,float f){std::memcpy(ram.data()+a,&f,4);}float get(std::uint64_t a){float f;std::memcpy(&f,ram.data()+a,4);return f;}
};
}
