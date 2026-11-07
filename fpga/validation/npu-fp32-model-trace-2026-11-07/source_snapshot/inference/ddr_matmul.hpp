#pragma once
// Reusable FPGA DDR MatMul through existing 1x1 INT8 Conv, no CPU fallback.
#include "npu_ddr_transport.hpp"
#include <cstdint>
#include <cstddef>
namespace inference { namespace ddr_matmul {
struct MatrixView { std::uint64_t base=0,row_stride=0,column_stride=4; };
// Immutable caller-owned cache descriptor. Callback authenticates identity/lease.
struct QuantizedB {
 MatrixView source;unsigned k=0,n=0;
 std::uint64_t data_base=0,column_pitch=0,scales_base=0;
 std::uint64_t session_cookie=0,source_identity=0;
};
struct Request {
 MatrixView a,b,output; // A[M,K], B[K,N], output[M,N], FP32 little endian.
 unsigned m=0,k=0,n=0,batches=1;
 std::uint64_t a_batch_stride=0,b_batch_stride=0,output_batch_stride=0;
 std::uint64_t scratch_base=0,scratch_bytes=0;
 bool activation_per_row=false; // opt-in per logical A row/token, over K
 float alpha=1;
 bool cache_row_scales=false; // appended opt-in: retain scales only when M<=256
 const QuantizedB*quantized_b=nullptr; // absent preserves runtime B quantization
};
struct Backend {
 void *context=nullptr;
 bool (*read)(void*,std::uint64_t,void*,std::size_t)=nullptr;
 bool (*write)(void*,std::uint64_t,const void*,std::size_t)=nullptr;
 bool (*tile)(void*,const npu_ddr::Tile&)=nullptr;
 bool (*unchanged)(void*)=nullptr;
 bool (*cancelled)(void*)=nullptr;
 void (*abort)(void*)=nullptr;
 // false authorizes construction; true also requires caller-published ready.
 bool (*validate_b_binding)(void*,const QuantizedB&,bool require_ready)=nullptr;
};
struct Workspace {
 float block[256]{},line[256]{},scales[8]{},a_scales[256]{};
 std::uint8_t bytes[256]{};
 std::int32_t sums[256]{};
};
struct Report {
 bool valid=false,cancelled=false;
 std::uint64_t read_bytes=0,write_bytes=0,tile_jobs=0,macs=0,padded_macs=0,scratch_required=0;
 char error[96]{};
};
struct PrepareReport {
 bool valid=false,cancelled=false;
 std::uint64_t source_read_bytes=0,write_bytes=0,verify_read_bytes=0;
 std::uint32_t expected_quantized_crc32=0,actual_quantized_crc32=0,expected_scales_crc32=0,actual_scales_crc32=0;
 char error[96]{};
};
// Builds full N*column_pitch bytes plus align16(N*4) scales; zero padding,
// exact existing quantization and full readback CRC. Does not publish readiness.
// Caller owns immutable source + writable destination and invalidates on abort.
bool prepare_b(const QuantizedB&,const Backend&,Workspace&,PrepareReport&);
// Scratch belongs exclusively to this call; source/output must not overlap it.
// Session is checked at entry/final publication; every I/O must reject an
// unbound/reset device. Caller exclusively owns the DDR session during run.
// No output publication until true + Report.valid. Failure can leave a DDR prefix
// modified: caller discards the entire output and performs no downstream work.
std::uint64_t scratch_required(unsigned m,unsigned k,bool activation_per_row=false,bool cache_row_scales=false);
bool run(const Request&,const Backend&,Workspace&,Report&);
}}
