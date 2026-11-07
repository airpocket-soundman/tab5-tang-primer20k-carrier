#pragma once
#include <cstdint>
#include <cstddef>
namespace inference { namespace transformer {
struct Storage {void*context=nullptr;bool(*read)(void*,std::uint64_t,void*,std::size_t)=nullptr;bool(*write)(void*,std::uint64_t,const void*,std::size_t)=nullptr;};
struct Matrix {std::uint64_t address=0;std::uint32_t row_stride=0,column_stride=4,batch_stride=0;};
struct MatMul {Matrix a,b,output;unsigned m=0,k=0,n=0,batches=1;float alpha=1;unsigned operation=0;}; // conventional A[M,K] B[K,N]
struct Hooks {void*context=nullptr;bool(*matmul)(void*,const MatMul&,const Storage&)=nullptr;bool(*cancelled)(void*)=nullptr;void(*progress)(void*,const char*,unsigned,unsigned)=nullptr;std::uint64_t(*clock_us)(void*)=nullptr;};
struct Scratch {
 float a[1024],b[1024],c[1024];
 // Optional external PSRAM working buffer, never placed on the caller stack.
 // Absent means baseline IO; present requires at least cache_required_floats.
 static constexpr std::size_t cache_required_floats=197*197;
 float*cache=nullptr;std::size_t cache_floats=0;
};
struct Stats {unsigned blocks_completed=0,operations=0,matmul_operations=0,matmul_batches=0,cpu_matmul_operations=0,external_matmul_operations=0;std::uint64_t macs=0,read_bytes=0,write_bytes=0,total_us=0,matmul_us=0,other_us=0,cache_bytes=0,cache_fills=0,cache_input_bytes=0;const char*error="none";};
struct Weight {std::uint64_t address=0;unsigned count=0,rows=0,cols=0;};
class Model {
 const std::uint8_t*metadata_=nullptr;std::uint64_t weights_=0,arena_=0;std::size_t constant_bytes_=0;
public:
 static constexpr unsigned image=224,patch=16,dim=192,mlp=768,tokens=197,heads=3,blocks=12,classes=1000,weight_count=152,metadata_bytes=2560;
 static constexpr std::size_t arena_bytes=2359296; // fixed bounded liveness layout, metadata separate
 bool load(const void*metadata,std::size_t bytes,std::size_t package_bytes,std::uint32_t metadata_crc,std::uint64_t constants_base,std::uint64_t arena_base,std::uint64_t capacity);
 bool valid()const{return metadata_!=nullptr;}Weight weight(unsigned)const;std::uint64_t arena()const{return arena_;}std::size_t constant_bytes()const{return constant_bytes_;}
 std::uint64_t input_address()const{return arena_;}std::uint64_t output_address()const{return arena_+2300000;} // input normalized RGB NCHW224; output1000 FP32logits
};
// A callback owns EVERY matrix multiplication. False aborts, no CPU fallback.
// Without callback cpu_matmul is a portable native/reference backend only.
bool run(const Model&,const Storage&,Scratch&,const Hooks&,Stats&);
bool cpu_matmul(const MatMul&,const Storage&,Scratch&);
std::uint32_t crc32(const void*,std::size_t);
}}
