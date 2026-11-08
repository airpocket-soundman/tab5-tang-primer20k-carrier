#pragma once
#include "rtdetr_graph.hpp"
#include "npu_ddr_transport.hpp"
namespace inference { namespace rtdetr_fpga {
struct Options {std::uint64_t scratch_base=0,scratch_bytes=0,capacity=128u*1024u*1024u;void*context=nullptr;bool(*cancelled)(void*)=nullptr;void(*cooperate)(void*)=nullptr;};
struct Stats {std::uint64_t conv_calls=0,matmul_calls=0,tile_jobs=0,matrix_jobs=0,read_bytes=0,write_bytes=0,static_weight_fp32_reads=0,dynamic_weight_fp32_read_bytes=0,scratch_peak_bytes=0,activation_quant_write_calls=0,activation_quant_write_bytes=0,conv_activation_quant_write_calls=0,conv_activation_quant_write_bytes=0,conv_dequant_read_calls=0,conv_dequant_read_bytes=0;};
// Caller owns the already-bound Matrix4E24/Disabled transport and verified RTG2
// constants. No begin/end/retry/fallback. A failed hook invalidates this owner.
class Backend {
 Options options_{};std::uint64_t lease_=0;bool valid_=false;char error_[128]{};Stats stats_{};
 float transpose_[4096]{};float panel_[2048]{};float block_[256]{},scales_[256]{},out_[256]{},bscale_[8]{};std::int32_t sums_[256]{};std::uint8_t bytes_[256]{};
 bool fail(const char*);bool check();bool read(const rtdetr::GraphStorage&,std::uint64_t,void*,std::size_t);bool write(const rtdetr::GraphStorage&,std::uint64_t,const void*,std::size_t);bool number(const rtdetr::GraphStorage&,std::uint64_t,float&);bool safe(const rtdetr::Model&);bool convolution(const rtdetr::Model&,const rtdetr::Node&,const rtdetr::GraphStorage&,const rtdetr::QuantizedBinding*);bool multiplication(const rtdetr::Model&,const rtdetr::Node&,const rtdetr::GraphStorage&,const rtdetr::QuantizedBinding*);
public:
 bool configure(const Options&);rtdetr::GraphHooks hooks();const char*error()const{return error_;}const Stats&stats()const{return stats_;}
};
}}
