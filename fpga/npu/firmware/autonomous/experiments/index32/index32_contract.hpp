#pragma once
#include "rtdetr_graph.hpp"
#include <cstring>
#include <climits>
// Model-specific experimental index contract. Floating math and file ABI unchanged.
namespace inference { namespace rtdetr { namespace index32 {
constexpr std::uint64_t limit=UINT64_C(0x05000000);
inline bool range(std::uint64_t address,std::uint64_t bytes){return address<=limit&&bytes<=limit-address;}
inline bool validate(const Model&m,const char*&why){
 auto fail=[&](const char*s){why=s;return false;};
 static const unsigned char source[32]={0xa4,0xe1,0xd5,0xc1,0x12,0xb1,0x87,0x3d,0x70,0x1b,0x69,0x0d,0xdf,0x92,0xd2,0xe6,0xaa,0x82,0x2a,0x2e,0x75,0x94,0x43,0xee,0x7f,0x7f,0x27,0x91,0x6b,0x21,0xb5,0x55};
 std::uint32_t metadata_crc=0;if(m.header)std::memcpy(&metadata_crc,m.header+36,4);
 if(!m.header||!m.t||!m.n||!m.q||m.version!=2||m.nt!=952||m.nn!=649||metadata_crc!=763848396u||!m.source_sha256()||std::memcmp(m.source_sha256(),source,32))return fail("index32_pinned_metadata_contract");
 if(!range(m.constant_base,m.constant_bytes)||!range(m.arena_base,m.arena_bytes))return fail("index32_model_range");
 for(unsigned i=0;i<m.nt;++i){const auto&t=m.t[i];
  if(t.rank>8||!t.count||t.count>=(UINT64_C(1)<<25)||(t.type!=quantized_tensor_type&&t.offset>limit)||(t.type==quantized_tensor_type&&t.offset!=UINT64_MAX))return fail("index32_count_rank_offset");
  std::uint64_t product=1;for(unsigned d=0;d<t.rank;++d){if(!t.d[d]||t.d[d]>=(1u<<25)||product>UINT32_MAX/t.d[d])return fail("index32_dimension_product");product*=t.d[d];}
  if(product!=t.count)return fail("index32_shape_product");
  if(t.type!=quantized_tensor_type){const auto bytes=t.count*(t.type==7?8u:4u);if(!range(m.address(i),bytes))return fail("index32_tensor_range");}
 }
 for(unsigned i=0;i<m.nq;++i){const auto&q=m.q[i];if(!range(m.quantized_data(q),q.data_bytes)||!range(m.quantized_scales(q),q.scale_bytes))return fail("index32_quantized_range");}
 for(unsigned i=0;i<m.nn;++i){const auto&n=m.n[i];if(n.ni<1||n.ni>8||n.no<1||n.no>4||n.input[0]<0||unsigned(n.input[0])>=m.nt||n.output[0]<0||unsigned(n.output[0])>=m.nt)return fail("index32_node_reference");
  for(int j=0;j<n.ni;++j)if(n.input[j]<-1||(n.input[j]>=0&&unsigned(n.input[j])>=m.nt))return fail("index32_node_reference");
  for(int j=0;j<n.no;++j)if(n.output[j]<0||unsigned(n.output[j])>=m.nt)return fail("index32_node_reference");
  const auto&in=m.t[n.input[0]];const auto&out=m.t[n.output[0]];
  if(n.op==Reshape||n.op==Flatten||n.op==Unsqueeze||n.op==Cast){if(in.count!=out.count)return fail("index32_view_count");}
  if(n.op>=Add&&n.op<=Clip){for(int j=0;j<n.ni;++j)if(n.input[j]>=0){const auto&v=m.t[n.input[j]];if(v.rank>out.rank)return fail("index32_broadcast_rank");for(unsigned d=0;d<v.rank;++d)if(v.d[d]!=1&&v.d[d]!=out.d[d+out.rank-v.rank])return fail("index32_broadcast_shape");}}
  if(n.op==Tile&&in.rank!=out.rank)return fail("index32_tile_rank");
  if(n.op==Concat){if(n.a[0]<0||n.a[0]>=out.rank||in.rank!=out.rank)return fail("index32_concat_axis");std::uint64_t sum=0;for(int j=0;j<n.ni;++j){if(n.input[j]<0)return fail("index32_concat_input");const auto&v=m.t[n.input[j]];if(v.rank!=out.rank)return fail("index32_concat_rank");for(unsigned d=0;d<out.rank;++d)if(d!=unsigned(n.a[0])&&v.d[d]!=out.d[d])return fail("index32_concat_shape");sum+=v.d[unsigned(n.a[0])];}if(sum!=out.d[unsigned(n.a[0])])return fail("index32_concat_sum");}
  if(n.op==Split){if(n.a[0]<0||n.a[0]>=in.rank)return fail("index32_split_axis");std::uint64_t sum=0;for(int j=0;j<n.no;++j){const auto&v=m.t[n.output[j]];if(v.rank!=in.rank)return fail("index32_split_rank");for(unsigned d=0;d<in.rank;++d)if(d!=unsigned(n.a[0])&&v.d[d]!=in.d[d])return fail("index32_split_shape");sum+=v.d[unsigned(n.a[0])];}if(sum!=in.d[unsigned(n.a[0])])return fail("index32_split_sum");}
  if(n.op==Softmax){if(in.rank!=out.rank||in.count!=out.count)return fail("index32_softmax_shape");for(unsigned d=0;d<in.rank;++d)if(in.d[d]!=out.d[d])return fail("index32_softmax_shape");}
  if(n.op==ReduceMean||n.op==ReduceMax||n.op==ReduceSum){if(n.a[0]<0||std::uint64_t(n.a[0])>=(UINT64_C(1)<<in.rank)||(n.a[1]!=0&&n.a[1]!=1))return fail("index32_reduce_axes");unsigned od=0;for(unsigned d=0;d<in.rank;++d){if(n.a[0]&(1<<d)){if(n.a[1]){if(od>=out.rank||out.d[od++]!=1)return fail("index32_reduce_shape");}}else if(od>=out.rank||out.d[od++]!=in.d[d])return fail("index32_reduce_shape");}if(od!=out.rank)return fail("index32_reduce_rank");}
  if(n.op==MaxPool||n.op==AveragePool){if(in.rank!=4||out.rank!=4||in.d[0]!=out.d[0]||in.d[1]!=out.d[1])return fail("index32_pool_shape");for(unsigned d=0;d<2;++d){const auto k=n.a[d],stride=n.a[2+d],dilation=n.a[8+d],pad=n.a[4+d];if(k<1||k>65535||stride<1||stride>65535||dilation<1||dilation>65535||pad<0||pad>INT32_MAX)return fail("index32_pool_attribute");const auto last=std::int64_t(out.d[2+d]-1)*stride+(k-1)*dilation-pad;if(last>INT32_MAX||last<INT32_MIN)return fail("index32_pool_coordinate");}}
  // All hot coordinate products are bounded by tensor count except Resize's cross-product.
  if(n.op==Resize){if(in.rank!=out.rank)return fail("index32_resize_rank");for(unsigned d=0;d<in.rank;++d)if(std::uint64_t(in.d[d])*out.d[d]>UINT32_MAX)return fail("index32_resize_product");}
  if(n.op==Slice){if(in.rank!=out.rank)return fail("index32_slice_rank");for(unsigned d=0;d<in.rank;++d){const auto start=n.a[d],step=n.a[8+d];if(start<0||start>=in.d[d]||step<INT32_MIN||step>INT32_MAX)return fail("index32_slice_attribute");const std::int64_t last=start+std::int64_t(out.d[d]-1)*step;if(last<0||last>=in.d[d])return fail("index32_slice_endpoint");}}
  // The CRC pins operator attributes. These explicit bounds reject arithmetic-invalid variants
  // even when a caller mutates the in-memory Model tables after successful load.
  if(n.op==Softmax){if(n.a[0]<0||n.a[0]>=in.rank)return fail("index32_softmax_axis");}
  if(n.op==Concat||n.op==Split){if(n.a[0]<0||n.a[0]>=in.rank)return fail("index32_concat_split_axis");}
  if(n.op==Transpose){unsigned mask=0;if(in.rank!=out.rank)return fail("index32_transpose_rank");for(unsigned d=0;d<in.rank;++d){if(n.a[d]<0||n.a[d]>=in.rank||(mask&(1u<<n.a[d])))return fail("index32_transpose_permutation");if(out.d[d]!=in.d[unsigned(n.a[d])])return fail("index32_transpose_shape");mask|=1u<<n.a[d];}}
 }
 return true;
}
}}}
