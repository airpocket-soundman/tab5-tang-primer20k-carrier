#include "platform.hpp"
#include "npu_ddr_transport.hpp"
#include <cstring>
#include <algorithm>
#ifndef AUTONOMOUS_SOFTWARE_MATRIX
#define AUTONOMOUS_SOFTWARE_MATRIX 1
#endif
namespace inference {namespace npu_ddr {
namespace {
const char*reason="none";Counters count{};std::uint32_t epoch=0;bool bound=false;
void put16(unsigned char*p,unsigned v){p[0]=std::uint8_t(v);p[1]=std::uint8_t(v>>8);}
void put32(unsigned char*p,std::uint32_t v){for(unsigned i=0;i<4;++i)p[i]=std::uint8_t(v>>(8*i));}
bool job(unsigned command,const unsigned char*descriptor,unsigned bytes,bool require_result){using namespace autonomous;if(!unchanged())return false;auto s=mmio(AUTONOMOUS_MMIO_STATUS);if(!(s&AUTONOMOUS_READY)||(s&(AUTONOMOUS_BUSY|AUTONOMOUS_DONE))){reason="job_not_ready";return false;}for(unsigned i=0;i<52;i+=4){std::uint32_t v=0;if(i<bytes)std::memcpy(&v,descriptor+i,4);mmio(AUTONOMOUS_MMIO_DESCRIPTOR+i,v);}mmio(AUTONOMOUS_MMIO_COMMAND,command);for(unsigned polls=0;polls<0x7fffffffu;++polls){s=mmio(AUTONOMOUS_MMIO_STATUS);if(autonomous::cancelled()){mmio(AUTONOMOUS_MMIO_ABORT,1);reason="job_cancelled_or_epoch";return false;}if(s&AUTONOMOUS_DONE){if((s&(AUTONOMOUS_ERROR|AUTONOMOUS_QUARANTINED))||(require_result&&!(s&AUTONOMOUS_RESULT_VALID))){reason="job_result_invalid";return false;}mmio(AUTONOMOUS_MMIO_ACK,1);return unchanged();}}mmio(AUTONOMOUS_MMIO_ABORT,1);reason="job_timeout_no_retry";return false;}
}
Execution execution(){return Execution::Matrix4E24;}CounterSampling counter_sampling(){return CounterSampling::Disabled;}
std::uint64_t session_serial(){if(!bound){epoch=autonomous::mmio(AUTONOMOUS_MMIO_EPOCH);bound=true;}return std::uint64_t(epoch)+1;}
bool unchanged(){using namespace autonomous;const auto s=mmio(AUTONOMOUS_MMIO_STATUS);if(!bound)session_serial();if(!(s&AUTONOMOUS_MEMORY_READY)||(s&(AUTONOMOUS_ERROR|AUTONOMOUS_QUARANTINED))||mmio(AUTONOMOUS_MMIO_EPOCH)!=epoch){reason="memory_or_epoch_changed";return false;}return true;}
bool read(std::uint64_t a,void*out,std::size_t n){if(!autonomous::read(nullptr,a,out,n)){reason="direct_ddr_read";return false;}count.read_bytes+=n;return true;}
bool write(std::uint64_t a,const void*in,std::size_t n){if(!autonomous::write(nullptr,a,in,n)){reason="direct_ddr_write";return false;}count.write_bytes+=n;return true;}
bool tile(const Tile&t){unsigned char d[52]{};if(t.ic<1||t.ic>16||t.oc<1||t.oc>8||t.oh<1||t.oh>16||t.ow<1||t.ow>16||(t.kernel!=1&&t.kernel!=3)||(t.stride!=1&&t.stride!=2)||!t.full_h||t.full_h>65535||!t.full_w||t.full_w>65535||std::uint64_t(t.input_base)+std::uint64_t(t.ic)*t.input_channel_pitch>0x05000000u||std::uint64_t(t.weight_base)+std::uint64_t(t.oc)*t.weight_oc_stride>0x05000000u||std::uint64_t(t.output_base)+std::uint64_t(t.oc)*t.output_channel_pitch>0x05000000u){reason="tile_shape";return false;}d[0]=std::uint8_t(t.ic);d[1]=std::uint8_t(t.oc);d[2]=std::uint8_t(t.oh);d[3]=std::uint8_t(t.ow);d[4]=std::uint8_t(t.kernel);d[5]=std::uint8_t(t.stride);d[6]=(t.first?1:0)|(t.final?2:0)|4;put16(d+8,t.full_h);put16(d+10,t.full_w);put32(d+12,std::uint32_t(t.origin_y));put32(d+16,std::uint32_t(t.origin_x));const std::uint32_t f[]={t.input_base,t.input_row_pitch,t.input_channel_pitch,t.weight_base,t.weight_oc_stride,t.output_base,t.output_row_pitch,t.output_channel_pitch};for(unsigned i=0;i<8;++i)put32(d+20+i*4,f[i]);if(!job(1,d,52,t.final))return false;++count.tile_jobs;return true;}
bool matrix(const MatrixJob&t){const auto ap=(std::uint64_t(t.m)+15)&~UINT64_C(15),bp=(std::uint64_t(t.k)+15)&~UINT64_C(15);const auto ae=std::uint64_t(t.a_base)+std::uint64_t(t.k)*t.a_pitch,be=std::uint64_t(t.b_base)+std::uint64_t(t.n)*t.b_pitch,ce=std::uint64_t(t.c_base)+std::uint64_t(t.n)*t.c_pitch;auto overlap=[](std::uint64_t a,std::uint64_t e,std::uint64_t b,std::uint64_t f){return a<f&&b<e;};if(!t.m||!t.k||!t.n||t.m>65535||t.k>65535||t.n>65535||t.a_base%16||t.b_base%16||t.c_base%16||t.a_pitch%16||t.b_pitch%16||t.c_pitch%16||t.a_pitch<ap||t.b_pitch<bp||t.c_pitch<ap*4||ae>0x05000000u||be>0x05000000u||ce>0x05000000u||overlap(t.a_base,ae,t.b_base,be)||overlap(t.a_base,ae,t.c_base,ce)||overlap(t.b_base,be,t.c_base,ce)){reason="matrix_range_or_alias";return false;}
#if AUTONOMOUS_SOFTWARE_MATRIX
 // Same N8/M256/K16 traversal and descriptors as the isolated RTL sequencer.
 // Scheduling runs on FPGA-local RV32; every integer MAC remains hardware.
 for(unsigned nb=0;nb<t.n;nb+=8)for(unsigned mb=0;mb<t.m;mb+=256)for(unsigned kb=0;kb<t.k;kb+=16){Tile d;d.ic=std::min<std::uint32_t>(16,t.k-kb);d.oc=std::min<std::uint32_t>(8,t.n-nb);d.oh=(std::min<std::uint32_t>(256,t.m-mb)+15)/16;d.ow=16;d.kernel=d.stride=1;d.first=kb==0;d.final=kb+d.ic==t.k;d.full_h=(t.m+15)/16;d.full_w=16;d.origin_y=std::int32_t(mb/16);d.origin_x=0;d.input_base=t.a_base+kb*t.a_pitch;d.input_row_pitch=16;d.input_channel_pitch=t.a_pitch;d.weight_base=t.b_base+nb*t.b_pitch+kb;d.weight_oc_stride=t.b_pitch;d.output_base=t.c_base+nb*t.c_pitch+mb*4;d.output_row_pitch=64;d.output_channel_pitch=t.c_pitch;if(!tile(d))return false;}
#else
 unsigned char d[36];const std::uint32_t f[]={t.m,t.k,t.n,t.a_base,t.a_pitch,t.b_base,t.b_pitch,t.c_base,t.c_pitch};for(unsigned i=0;i<9;++i)put32(d+i*4,f[i]);if(!job(2,d,36,true))return false;
#endif
 ++count.matrix_jobs;return true;}
const char*error(){return reason;}Counters counters(){return count;}
}}
