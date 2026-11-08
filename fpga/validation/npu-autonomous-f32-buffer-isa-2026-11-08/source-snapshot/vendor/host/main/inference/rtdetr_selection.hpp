#pragma once
#include "rtdetr_grid_sample.hpp"
#include <cstring>
namespace inference { namespace rtdetr {
struct TopK {std::uint64_t input=0,values=0,indices=0;unsigned rows=0,width=0,k=0;};
// Actual RT-DETR: last axis, largest=1, sorted=1 FLOAT -> FLOAT/INT64.
// Bounded O(k) workspace; stable equal values choose lower source index.
inline bool topk(const TopK&r,const Storage&s){
 if(!s.read||!s.write||!r.rows||!r.width||!r.k||r.k>r.width||r.k>1250)return false;
 const std::uint64_t ins=std::uint64_t(r.rows)*r.width,outs=std::uint64_t(r.rows)*r.k;if(ins>UINT32_MAX||outs>UINT32_MAX||r.input>UINT64_MAX-ins*4||r.values>UINT64_MAX-outs*4||r.indices>UINT64_MAX-outs*8)return false;
 struct Entry {float v;std::int64_t i;};Entry heap[1250];float block[128];
 auto better=[](const Entry&a,const Entry&b){return a.v>b.v||(a.v==b.v&&a.i<b.i);};
 for(unsigned row=0;row<r.rows;++row){unsigned used=0;
  for(unsigned base=0;base<r.width;base+=128){unsigned count=std::min(128u,r.width-base);if(s.cancelled&&s.cancelled(s.context))return false;if(!s.read(s.context,r.input+(std::uint64_t(row)*r.width+base)*4,block,count*4))return false;
   for(unsigned j=0;j<count;++j){if(!std::isfinite(block[j]))return false;Entry e{block[j],std::int64_t(base+j)};
    if(used<r.k){heap[used++]=e;std::push_heap(heap,heap+used,better);}else if(better(e,heap[0])){std::pop_heap(heap,heap+used,better);heap[used-1]=e;std::push_heap(heap,heap+used,better);}
   }
  }
  std::sort(heap,heap+used,better);for(unsigned j=0;j<used;++j){if(!s.write(s.context,r.values+(std::uint64_t(row)*r.k+j)*4,&heap[j].v,4)||!s.write(s.context,r.indices+(std::uint64_t(row)*r.k+j)*8,&heap[j].i,8))return false;}
 }
 return true;
}
struct GatherElements {std::uint64_t input=0,indices=0,output=0;unsigned rank=0,axis=0;unsigned data_shape[4]{},index_shape[4]{};};
inline bool gather_elements(const GatherElements&r,const Storage&s){
 if(!s.read||!s.write||r.rank<1||r.rank>4||r.axis>=r.rank)return false;
 std::uint64_t count=1,strides[4]{},data_count=1;for(unsigned i=r.rank;i-->0;){if(!r.data_shape[i]||!r.index_shape[i]||(i!=r.axis&&r.index_shape[i]>r.data_shape[i]))return false;strides[i]=data_count;data_count*=r.data_shape[i];count*=r.index_shape[i];if(data_count>UINT32_MAX||count>UINT32_MAX)return false;}
 if(r.input>UINT64_MAX-data_count*4||r.indices>UINT64_MAX-count*8||r.output>UINT64_MAX-count*4)return false;
 float out[128];std::int64_t indices[128];
 for(std::uint64_t base=0;base<count;base+=128){unsigned n=unsigned(std::min<std::uint64_t>(128,count-base));if(s.cancelled&&s.cancelled(s.context))return false;if(!s.read(s.context,r.indices+base*8,indices,n*8))return false;
  for(unsigned j=0;j<n;++j){std::uint64_t t=base+j,address=0;for(unsigned d=r.rank;d-->0;){const unsigned coordinate=unsigned(t%r.index_shape[d]);t/=r.index_shape[d];std::int64_t index=d==r.axis?indices[j]:coordinate;if(d==r.axis&&index<0)index+=r.data_shape[d];if(index<0||std::uint64_t(index)>=r.data_shape[d])return false;address+=std::uint64_t(index)*strides[d];}if(!s.read(s.context,r.input+address*4,&out[j],4))return false;}
  if(!s.write(s.context,r.output+base*4,out,n*4))return false;
 }
 return true;
}
}}
