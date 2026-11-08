#pragma once
#include "rtdetr_grid_sample.hpp"
#include <cstdint>
#include <cstddef>
namespace inference { namespace rtdetr {
enum Op {Add=1,Mul,Sub,Div,Pow,Relu,Sigmoid,Sqrt,Erf,Log,Clip,Cast,Reshape,Unsqueeze,Flatten,Transpose,Slice,Concat,Split,Tile,Resize,ReduceMean,ReduceMax,ReduceSum,Softmax,Conv,MatMul,Gemm,MaxPool,AveragePool,GridSampleOp,TopKOp,GatherElementsOp};
struct Tensor {std::uint32_t d[8];std::uint64_t count,offset;std::uint32_t rank,type,constant,reserved;};
struct Node {std::int32_t op,ni,no,input[8],output[4];std::int64_t a[16];float f[4];};
static_assert(sizeof(Tensor)==64,"RTG tensor layout");static_assert(sizeof(Node)==208,"RTG node layout");
enum QuantizedKind:std::uint32_t {QuantizedConv=1,QuantizedMatMul=2,QuantizedGemm=3};
constexpr std::uint32_t quantized_tensor_type=100;
struct QuantizedBinding {std::uint32_t node,source_tensor,kind,k,n,pitch,data_bytes,scale_bytes;std::uint64_t data_offset,scale_offset;std::uint32_t source_rank,dims[8];std::uint8_t source_sha256[32];std::uint32_t data_crc32,scale_crc32,reserved;};
static_assert(sizeof(QuantizedBinding)==128,"RQG2 binding layout");
namespace rqg2 {constexpr unsigned header_bytes=128,metadata_bytes_offset=24,payload_bytes_offset=28,arena_bytes_offset=32,metadata_crc_offset=36,payload_crc_offset=40,binding_count_offset=44,binding_offset_offset=48,source_sha_offset=64,rqw_sha_offset=96;}
struct Model {const Tensor*t=nullptr;const Node*n=nullptr;const QuantizedBinding*q=nullptr;const std::uint8_t*header=nullptr;unsigned nt=0,nn=0,input=0,output=0,version=0,nq=0;std::uint64_t constant_base=0,arena_base=0,constant_bytes=0,arena_bytes=0;
 // Caller verifies complete package/constant CRC and source SHA before binding.
 bool load(const void*,std::size_t,std::uint64_t,std::uint64_t,std::uint64_t);
 std::uint64_t address(unsigned id)const{return id>=nt||t[id].type==quantized_tensor_type?UINT64_MAX:(t[id].constant?constant_base:arena_base)+t[id].offset;}
 const std::uint8_t*source_sha256()const{return version==2?header+64:nullptr;}
 const QuantizedBinding*quantized(unsigned node)const{for(unsigned i=0;i<nq;++i)if(q[i].node==node)return q+i;return nullptr;}
 std::uint64_t quantized_data(const QuantizedBinding&b)const{return quantized(b.node)==&b?constant_base+b.data_offset:UINT64_MAX;}
 std::uint64_t quantized_scales(const QuantizedBinding&b)const{return quantized(b.node)==&b?constant_base+b.scale_offset:UINT64_MAX;}
};
struct GraphStorage:Storage {// optional native CPU oracle fast view; no allocation.
 const void*(*map)(void*,std::uint64_t,std::size_t)=nullptr;
};
struct GraphStats {unsigned completed=0,conv=0,matmul=0,external_conv=0,external_matmul=0;const char*error="none";};
struct GraphHooks {void*context=nullptr;bool require_external_conv=false,require_external_matmul=false;bool(*conv)(void*,const Model&,const Node&,const GraphStorage&)=nullptr;bool(*matmul)(void*,const Model&,const Node&,const GraphStorage&)=nullptr;bool(*conv_v2)(void*,const Model&,const Node&,const GraphStorage&,const QuantizedBinding*)=nullptr;bool(*matmul_v2)(void*,const Model&,const Node&,const GraphStorage&,const QuantizedBinding*)=nullptr;void(*progress)(void*,unsigned,unsigned)=nullptr;bool(*node_done)(void*,unsigned,const Model&,const GraphStorage&)=nullptr;};
bool run_graph(const Model&,const GraphStorage&,const GraphHooks&,GraphStats&);
}}
