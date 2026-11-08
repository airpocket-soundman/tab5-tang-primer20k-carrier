#include "crc_table.hpp"
#include <vector>
#include <cstdio>
#include <cassert>
#include <fstream>
#include <iterator>
#include <algorithm>
template<class C> bool bitwise(const void*data,std::size_t n,std::uint32_t&out,C cancel){auto*p=static_cast<const unsigned char*>(data);std::uint32_t c=~0u;for(std::size_t i=0;i<n;++i){if((i&4095u)==0&&cancel())return false;c^=p[i];for(unsigned b=0;b<8;++b)c=(c>>1)^(0xedb88320u&std::uint32_t(-int(c&1)));}out=c^~0u;return !cancel();}
int main(int argc,char**argv){assert(argc==2);std::vector<unsigned char>d(20000);std::uint32_t seed=42;for(auto&x:d){seed=seed*1664525u+1013904223u;x=seed>>24;}
 unsigned comparisons=0;for(std::size_t n: {0u,1u,2u,255u,256u,4095u,4096u,4097u,8192u,8193u,20000u}){
  std::uint32_t a=0,b=0;assert(bitwise(d.data(),n,a,[]{return false;}));assert(crc_table::checked(d.data(),n,b,[]{return false;}));assert(a==b);
  for(std::size_t chunk:{1u,3u,16u,255u,4095u,4096u,4097u}){std::uint32_t c=~0u;for(std::size_t i=0;i<n;i+=chunk)c=crc_table::update(c,d.data()+i,std::min(chunk,n-i));assert((c^~0u)==a);++comparisons;}
  for(unsigned stop=0;stop<9;++stop){unsigned ca=0,cb=0;a=b=0x12345678u;bool ra=bitwise(d.data(),n,a,[&]{return ca++==stop;}),rb=crc_table::checked(d.data(),n,b,[&]{return cb++==stop;});assert(ra==rb&&a==b&&ca==cb);++comparisons;}
 }
 std::uint32_t c=1;assert(crc_table::checked(nullptr,0,c,[]{return false;})&&c==0);assert(crc_table::checked("123456789",9,c,[]{return false;})&&c==0xcbf43926u);
 std::ifstream f(argv[1],std::ios::binary);assert(f);std::vector<unsigned char>p((std::istreambuf_iterator<char>(f)),{});assert(p.size()>65536);const auto*h=reinterpret_cast<const std::uint32_t*>(p.data());std::uint32_t n=h[7],offset=h[6];assert(std::size_t(offset)+n==p.size());std::uint32_t a=0,b=0;assert(bitwise(p.data()+offset,n,a,[]{return false;}));assert(crc_table::checked(p.data()+offset,n,b,[]{return false;}));assert(a==b&&b==h[10]);
 printf("PASS comparisons=%u payload_bytes=%u crc=%08x\n",comparisons,n,b);
}
