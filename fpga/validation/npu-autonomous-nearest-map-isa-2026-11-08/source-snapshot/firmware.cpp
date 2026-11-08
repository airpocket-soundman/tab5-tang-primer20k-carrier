#include "platform.hpp"
#include "rtdetr_graph.hpp"
#include "rtdetr_fpga_backend.hpp"
#include <cstring>
#include <cstdio>
namespace autonomous {
constexpr std::uint32_t graph_limit=0x05000000u;
std::uint32_t boot_epoch=0,token=0;
void fail(unsigned code,const char*text){auto&m=mailbox();m.error=code;m.output_count=0;m.completed_token=0;unsigned i=0;for(;text&&text[i]&&i+1<sizeof m.error_text;++i)m.error_text[i]=text[i];m.error_text[i]=0;asm volatile("":::"memory");m.state=code==2?AP_CANCELLED:AP_FAILED;mmio(AUTONOMOUS_MMIO_APP_ERROR,code);mmio(AUTONOMOUS_MMIO_STAGE,m.state);mmio(AUTONOMOUS_MMIO_FINISH,2);}
bool cancelled(){const auto s=mmio(AUTONOMOUS_MMIO_STATUS);return mailbox().cancel||!(s&AUTONOMOUS_MEMORY_READY)||(s&(AUTONOMOUS_ERROR|AUTONOMOUS_QUARANTINED))||mmio(AUTONOMOUS_MMIO_EPOCH)!=boot_epoch;}
bool crc32(const void*data,std::size_t n,std::uint32_t&out){const auto*p=static_cast<const unsigned char*>(data);std::uint32_t crc=~0u;for(std::size_t i=0;i<n;++i){if((i&4095u)==0&&cancelled())return false;crc^=p[i];for(unsigned b=0;b<8;++b)crc=(crc>>1)^(0xedb88320u&std::uint32_t(-int(crc&1)));}out=crc^~0u;return !cancelled();}
bool valid(std::uint64_t a,std::size_t n){return a<=graph_limit&&n<=graph_limit-a;}
bool read(void*,std::uint64_t a,void*out,std::size_t n){if(cancelled()||!valid(a,n)||(n&&!out))return false;std::memcpy(out,reinterpret_cast<const void*>(std::uintptr_t(a)),n);return true;}
bool write(void*,std::uint64_t a,const void*in,std::size_t n){if(cancelled()||!valid(a,n)||(n&&!in))return false;std::memcpy(reinterpret_cast<void*>(std::uintptr_t(a)),in,n);return true;}
const void*map(void*,std::uint64_t a,std::size_t n){return valid(a,n)?reinterpret_cast<const void*>(std::uintptr_t(a)):nullptr;}
void progress(void*,unsigned current,unsigned total){mailbox().progress=current;mailbox().total=total;mmio(AUTONOMOUS_MMIO_NODE,current);}
}
extern "C" void firmware_main(){
 namespace rt=inference::rtdetr;namespace rf=inference::rtdetr_fpga;namespace nd=inference::npu_ddr;using namespace autonomous;auto&mb=mailbox();
 mb.state=AP_BOOT;mmio(AUTONOMOUS_MMIO_STAGE,AP_BOOT);mb.error=0;mb.output_count=0;mb.completed_token=0;mb.firmware_abi=AUTONOMOUS_ABI;mb.progress=0;mb.nodes=mb.conv=mb.matmul=0;mb.softcore_nonmac=mb.hard_mac=0;
 if(mb.magic!=AUTONOMOUS_MAGIC||mb.abi!=AUTONOMOUS_ABI||mb.command!=1||!mb.token){fail(1,"boot_parameters");return;}token=mb.token;boot_epoch=mmio(AUTONOMOUS_MMIO_EPOCH);mb.epoch=boot_epoch;mb.state=AP_CHECKING;mmio(AUTONOMOUS_MMIO_STAGE,AP_CHECKING);
 if(mb.metadata_base!=0x05800000u||mb.metadata_bytes<128||mb.metadata_bytes>0x100000u||mb.constant_base!=65536||!valid(mb.arena_base,0)||!valid(mb.scratch_base,mb.scratch_bytes)||mb.scratch_base%16){fail(3,"metadata_or_layout");return;}
 const auto*metadata=reinterpret_cast<const void*>(mb.metadata_base);const auto*h=static_cast<const std::uint32_t*>(metadata);static const unsigned char expected_source[32]={0xa4,0xe1,0xd5,0xc1,0x12,0xb1,0x87,0x3d,0x70,0x1b,0x69,0x0d,0xdf,0x92,0xd2,0xe6,0xaa,0x82,0x2a,0x2e,0x75,0x94,0x43,0xee,0x7f,0x7f,0x27,0x91,0x6b,0x21,0xb5,0x55};
 rt::Model model;if(!model.load(metadata,mb.metadata_bytes,mb.constant_base,mb.arena_base,graph_limit)||model.version!=2||model.nn!=649||std::memcmp(model.source_sha256(),expected_source,32)){fail(4,"typed_metadata_or_source");return;}
 std::uint32_t payload_crc=0;if(!valid(mb.constant_base,model.constant_bytes)){fail(5,"payload_range");return;}if(!crc32(reinterpret_cast<const void*>(mb.constant_base),std::size_t(model.constant_bytes),payload_crc)){fail(2,"cancelled_during_crc");return;}if(payload_crc!=h[10]){fail(5,"payload_crc");return;}
 const auto&shape=model.t[model.input];if(shape.type!=1||shape.rank!=4||shape.d[0]!=1||shape.d[1]!=3||shape.d[2]!=640||shape.d[3]!=640){fail(6,"rgb_input_shape");return;}
 // Raw camera/sample RGB is input only; conversion is performed by FPGA CPU.
 const auto*rgb=reinterpret_cast<const unsigned char*>(0x05900000u);auto*input=reinterpret_cast<float*>(std::uintptr_t(model.address(model.input)));
 for(unsigned c=0;c<3;++c)for(unsigned i=0;i<640u*640u;++i){if((i&1023u)==0&&cancelled()){fail(2,"cancelled");return;}input[c*640u*640u+i]=float(rgb[i*3+(2-c)]);}
 rt::GraphStorage storage;storage.read=read;storage.write=write;storage.map=map;storage.cancelled=[](void*){return cancelled();};static rf::Backend backend;rf::Options options;options.capacity=graph_limit;options.scratch_base=mb.scratch_base;options.scratch_bytes=mb.scratch_bytes;options.cancelled=[](void*){return cancelled();};
 if(!backend.configure(options)){fail(7,backend.error());return;}auto hooks=backend.hooks();hooks.progress=progress;rt::GraphStats stats;mb.state=AP_RUNNING;mmio(AUTONOMOUS_MMIO_STAGE,AP_RUNNING);
 const bool ran=rt::run_graph(model,storage,hooks,stats);mb.nodes=stats.completed;mb.conv=stats.external_conv;mb.matmul=stats.external_matmul;
 if(!ran){fail(cancelled()?2:8,stats.error);return;}
 if(cancelled()||!nd::unchanged()||stats.completed!=649||stats.external_conv!=57||stats.external_matmul!=65){fail(9,"completion_counts_or_epoch");return;}
 const auto&out=model.t[model.output];if(out.type!=1||out.count!=1800){fail(10,"output_shape");return;}const auto*values=reinterpret_cast<const float*>(std::uintptr_t(model.address(model.output)));for(unsigned i=0;i<1800;++i)if(!std::isfinite(values[i])){fail(11,"nonfinite_output");return;}for(unsigned i=0;i<300;++i){const auto*v=values+i*6;if(v[0]<0||v[0]>24||std::floor(v[0])!=v[0]||v[5]<0||v[5]>1){fail(12,"output_class_or_score");return;}}
 mb.output_base=std::uint32_t(model.address(model.output));mb.tile_jobs=std::uint32_t(backend.stats().tile_jobs);mb.matrix_jobs=std::uint32_t(backend.stats().matrix_jobs);mb.softcore_nonmac=stats.completed-stats.external_conv-stats.external_matmul;mb.hard_mac=stats.external_conv+stats.external_matmul;mb.output_count=1800;mb.completed_token=token;asm volatile("":::"memory");mb.state=AP_COMPLETE;mmio(AUTONOMOUS_MMIO_NODE,649);mmio(AUTONOMOUS_MMIO_STAGE,AP_COMPLETE);mmio(AUTONOMOUS_MMIO_FINISH,1);
}
