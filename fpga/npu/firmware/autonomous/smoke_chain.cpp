#include "platform.hpp"
#include "npu_ddr_transport.hpp"
#include <cstring>
namespace autonomous {
static std::uint32_t smoke_epoch=0;
bool valid(std::uint64_t a,std::size_t n){return a<=0x05000000u&&n<=0x05000000u-a;}
bool cancelled(){auto s=mmio(AUTONOMOUS_MMIO_STATUS);return !(s&AUTONOMOUS_MEMORY_READY)||(s&(AUTONOMOUS_ERROR|AUTONOMOUS_QUARANTINED))||mmio(AUTONOMOUS_MMIO_EPOCH)!=smoke_epoch;}
bool read(void*,std::uint64_t a,void*out,std::size_t n){if(!valid(a,n)||!out)return false;std::memcpy(out,reinterpret_cast<const void*>(std::uintptr_t(a)),n);return true;}
bool write(void*,std::uint64_t a,const void*in,std::size_t n){if(!valid(a,n)||!in)return false;std::memcpy(reinterpret_cast<void*>(std::uintptr_t(a)),in,n);return true;}
void fail(unsigned code,const char*){mailbox().error=code;mailbox().state=AP_FAILED;mmio(AUTONOMOUS_MMIO_APP_ERROR,code);mmio(AUTONOMOUS_MMIO_FINISH,2);}
}
extern "C" void firmware_main(){using namespace autonomous;namespace nd=inference::npu_ddr;auto&mb=mailbox();smoke_epoch=mmio(AUTONOMOUS_MMIO_EPOCH);mb.state=AP_RUNNING;mb.error=0;mb.output_count=0;mb.nodes=0;
 auto*a=reinterpret_cast<signed char*>(0x1000u);auto*b=reinterpret_cast<signed char*>(0x2000u);auto*c=reinterpret_cast<int*>(0x3000u);for(unsigned i=0;i<96;++i)a[i]=0;for(unsigned i=0;i<32;++i)b[i]=0;for(unsigned z=0;z<3;++z)for(unsigned y=0;y<2;++y)for(unsigned x=0;x<2;++x)a[z*32+y*16+x]=signed(z*3+y*2+x)-5;for(unsigned z=0;z<2;++z)for(unsigned i=0;i<3;++i)b[z*16+i]=signed(z+i)-2;
 nd::Tile t;t.ic=3;t.oc=2;t.oh=t.ow=2;t.kernel=t.stride=1;t.first=t.final=true;t.full_h=t.full_w=2;t.input_base=0x1000;t.input_row_pitch=16;t.input_channel_pitch=32;t.weight_base=0x2000;t.weight_oc_stride=16;t.output_base=0x3000;t.output_row_pitch=64;t.output_channel_pitch=128;
 if(!nd::tile(t)){fail(1,nd::error());return;}for(unsigned z=0;z<2;++z)for(unsigned y=0;y<2;++y)for(unsigned x=0;x<2;++x){int sum=0;for(unsigned i=0;i<3;++i)sum+=int(a[i*32+y*16+x])*int(b[z*16+i]);if(c[z*32+y*16+x]!=sum){fail(2,"tile_mismatch");return;}}mb.nodes=8;
 a=reinterpret_cast<signed char*>(0x4000u);b=reinterpret_cast<signed char*>(0x5000u);c=reinterpret_cast<int*>(0x6000u);for(unsigned i=0;i<80;++i)a[i]=0;for(unsigned i=0;i<32;++i)b[i]=0;for(unsigned k=0;k<5;++k)for(unsigned m=0;m<3;++m)a[k*16+m]=signed(k*3+m)-7;for(unsigned n=0;n<2;++n)for(unsigned k=0;k<5;++k)b[n*16+k]=signed(n+k)-3;
 nd::MatrixJob j;j.m=3;j.k=5;j.n=2;j.a_base=0x4000;j.a_pitch=16;j.b_base=0x5000;j.b_pitch=16;j.c_base=0x6000;j.c_pitch=64;if(!nd::matrix(j)){fail(3,nd::error());return;}
 for(unsigned n=0;n<2;++n)for(unsigned m=0;m<3;++m){int sum=0;for(unsigned k=0;k<5;++k)sum+=int(a[k*16+m])*int(b[n*16+k]);if(c[n*16+m]!=sum){fail(4,"matrix_mismatch");return;}}
 // Exercise partial accumulator ownership across MMIO ACK: IC16 thenIC1.
 a=reinterpret_cast<signed char*>(0x8000u);b=reinterpret_cast<signed char*>(0x9000u);c=reinterpret_cast<int*>(0xa000u);auto*guard=reinterpret_cast<unsigned char*>(0x9ff0u);for(unsigned i=0;i<544;++i)a[i]=0;for(unsigned i=0;i<32;++i)b[i]=0;for(unsigned i=0;i<160;++i)guard[i]=0x55;
 for(unsigned z=0;z<17;++z){b[z]=signed(z%7)-3;for(unsigned y=0;y<2;++y)for(unsigned x=0;x<3;++x)a[z*32+y*16+x]=signed((z*5+y*3+x)%19)-9;}
 nd::Tile u;u.ic=16;u.oc=1;u.oh=2;u.ow=3;u.kernel=u.stride=1;u.first=true;u.final=false;u.full_h=2;u.full_w=3;u.input_base=0x8000;u.input_row_pitch=16;u.input_channel_pitch=32;u.weight_base=0x9000;u.weight_oc_stride=32;u.output_base=0xa000;u.output_row_pitch=64;u.output_channel_pitch=128;
 if(!nd::tile(u)){fail(5,nd::error());return;}for(unsigned i=0;i<160;++i)if(guard[i]!=0x55){fail(6,"nonfinal_wrote_DDR");return;}
 u.ic=1;u.first=false;u.final=true;u.input_base+=16*32;u.weight_base+=16;if(!nd::tile(u)){fail(7,nd::error());return;}
 for(unsigned y=0;y<2;++y)for(unsigned x=0;x<3;++x){int sum=0;for(unsigned z=0;z<17;++z)sum+=int(a[z*32+y*16+x])*int(b[z]);if(c[y*16+x]!=sum){fail(8,"partial_chain_mismatch");return;}}
 for(unsigned i=0;i<160;++i){bool owned=(i>=16&&i<32)||(i>=80&&i<96);if(!owned&&guard[i]!=0x55){fail(9,"partial_chain_guard");return;}}
 mb.nodes=20;mb.output_base=0xa000;mb.output_count=6;mb.state=AP_COMPLETE;mmio(AUTONOMOUS_MMIO_NODE,20);mmio(AUTONOMOUS_MMIO_STAGE,AP_COMPLETE);mmio(AUTONOMOUS_MMIO_FINISH,1);
}
