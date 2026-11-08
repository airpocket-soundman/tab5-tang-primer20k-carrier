#include "rtdetr_fpga_backend.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
namespace inference { namespace rtdetr_fpga {
namespace nd=npu_ddr;namespace rt=rtdetr;
namespace {std::uint64_t a16(std::uint64_t x){return(x+15)&~UINT64_C(15);}bool overlap(std::uint64_t a,std::uint64_t n,std::uint64_t b,std::uint64_t m){return a<b+m&&b<a+n;}std::int8_t quant(float v,float s){return std::int8_t(std::max(-127.f,std::min(127.f,std::round(v/s))));}
std::uint64_t batchbase(const rt::Tensor&t,const rt::Tensor&o,std::uint64_t batch){std::uint64_t c[8]{},index=batch*o.d[o.rank-2]*o.d[o.rank-1];for(unsigned d=o.rank;d-->0;){c[d]=index%o.d[d];index/=o.d[d];}std::uint64_t v=0;for(unsigned d=0;d+2<t.rank;d++)v=v*t.d[d]+(t.d[d]==1?0:c[d+o.rank-t.rank]);return v*t.d[t.rank-2]*t.d[t.rank-1];}
std::uint64_t biasindex(const rt::Tensor&t,const rt::Tensor&o,std::uint64_t index){std::uint64_t c[8]{};for(unsigned d=o.rank;d-->0;){c[d]=index%o.d[d];index/=o.d[d];}std::uint64_t v=0;for(unsigned d=0;d<t.rank;d++)v=v*t.d[d]+(t.d[d]==1?0:c[d+o.rank-t.rank]);return v;}}
bool Backend::fail(const char*why){if(!error_[0])std::snprintf(error_,sizeof error_,"%s",why);valid_=false;return false;}
bool Backend::check(){if(!valid_)return false;if(options_.cancelled&&options_.cancelled(options_.context))return fail("cancelled");if(lease_!=nd::session_serial())return fail("transport_lease_changed");if(options_.cooperate)options_.cooperate(options_.context);if(options_.cancelled&&options_.cancelled(options_.context))return fail("cancelled");if(lease_!=nd::session_serial())return fail("transport_lease_changed");return true;}
bool Backend::read(const rt::GraphStorage&s,std::uint64_t a,void*p,std::size_t n){if(!check())return false;if(a>options_.capacity||n>options_.capacity-a||!s.read||!(a>=options_.scratch_base?nd::read(a,p,n):s.read(s.context,a,p,n)))return fail("storage_read");stats_.read_bytes+=n;return check();}
bool Backend::write(const rt::GraphStorage&s,std::uint64_t a,const void*p,std::size_t n){if(!check())return false;if(a>options_.capacity||n>options_.capacity-a||!s.write||!(a>=options_.scratch_base?nd::write(a,p,n):s.write(s.context,a,p,n)))return fail("storage_write");stats_.write_bytes+=n;return check();}
bool Backend::number(const rt::GraphStorage&s,std::uint64_t a,float&v){if(!read(s,a,&v,4))return false;return std::isfinite(v)||fail("nonfinite_source");}
bool Backend::configure(const Options&o){options_=o;stats_={};error_[0]=0;valid_=false;lease_=nd::session_serial();if(!lease_||o.scratch_base%16||!o.scratch_bytes||o.capacity>UINT64_C(128)*1024*1024||o.scratch_base>o.capacity||o.scratch_bytes>o.capacity-o.scratch_base||nd::execution()!=nd::Execution::Matrix4E24||nd::counter_sampling()!=nd::CounterSampling::Disabled)return fail("invalid_owner_or_scratch");valid_=true;return check()&&(nd::unchanged()||fail(nd::error()));}
bool Backend::safe(const rt::Model&m){if(!check()||overlap(options_.scratch_base,options_.scratch_bytes,m.constant_base,m.constant_bytes)||overlap(options_.scratch_base,options_.scratch_bytes,m.arena_base,m.arena_bytes))return fail("scratch_model_overlap");return nd::unchanged()||fail(nd::error());}
rt::GraphHooks Backend::hooks(){rt::GraphHooks h;h.context=this;h.require_external_conv=h.require_external_matmul=true;h.conv_v2=[](void*p,const rt::Model&m,const rt::Node&n,const rt::GraphStorage&s,const rt::QuantizedBinding*q){return static_cast<Backend*>(p)->convolution(m,n,s,q);};h.matmul_v2=[](void*p,const rt::Model&m,const rt::Node&n,const rt::GraphStorage&s,const rt::QuantizedBinding*q){return static_cast<Backend*>(p)->multiplication(m,n,s,q);};return h;}
bool Backend::convolution(const rt::Model&m,const rt::Node&n,const rt::GraphStorage&s,const rt::QuantizedBinding*q){
 if(!safe(m)||!q||q->node>=m.nn||m.n+q->node!=&n||q->source_tensor!=unsigned(n.input[1])||q->kind!=rt::QuantizedConv||m.quantized_data(*q)==UINT64_MAX||m.quantized_scales(*q)==UINT64_MAX){return fail("conv_requires_typed_weight");}const auto&x=m.t[n.input[0]];const auto&o=m.t[n.output[0]];const unsigned ic=x.d[1],oc=o.d[1],ih=x.d[2],iw=x.d[3],oh=o.d[2],ow=o.d[3],k=unsigned(n.a[0]),stride=unsigned(n.a[2]);
 if(x.type!=1||o.type!=1||x.rank!=4||o.rank!=4||x.d[0]!=1||o.d[0]!=1||n.a[10]!=1||(k!=1&&k!=3)||n.a[1]!=k||(stride!=1&&stride!=2)||n.a[3]!=stride||n.a[8]!=1||n.a[9]!=1||q->k!=ic*k*k||q->n!=oc||q->pitch<a16(q->k))return fail("conv_descriptor");
 const auto row=a16(iw),channel=row*ih,qbytes=channel*ic,qi=options_.scratch_base,qo=qi+a16(qbytes);if(qbytes>options_.scratch_bytes||8192>options_.scratch_bytes-qbytes)return fail("conv_scratch");stats_.scratch_peak_bytes=std::max(stats_.scratch_peak_bytes,qbytes+8192);
 float maximum=0;for(std::uint64_t base=0;base<x.count;base+=256){const unsigned size=unsigned(std::min< std::uint64_t>(256,x.count-base));if(!read(s,m.address(n.input[0])+base*4,block_,size*4))return false;for(unsigned i=0;i<size;i++){if(!std::isfinite(block_[i]))return fail("conv_nonfinite_input");maximum=std::max(maximum,std::fabs(block_[i]));}}
 const float sx=maximum?maximum/127.f:1.f;if(!std::isfinite(sx)||sx<=0)return fail("conv_scale");
 // Quantized NCHW rows remain byte-identical, including row padding. Reuse
 // the existing transpose workspace only while Conv owns this backend.
 auto*staging=reinterpret_cast<std::uint8_t*>(transpose_);std::size_t staged=0;std::uint64_t uploaded=0;
 auto flush_qA=[&](){if(!staged)return true;if(staged>2032||staged%16||uploaded>qbytes||staged>qbytes-uploaded)return fail("conv_qA_staging_range");if(!write(s,qi+uploaded,staging,staged))return false;++stats_.activation_quant_write_calls;stats_.activation_quant_write_bytes+=staged;++stats_.conv_activation_quant_write_calls;stats_.conv_activation_quant_write_bytes+=staged;uploaded+=staged;staged=0;return true;};
 for(unsigned c=0;c<ic;c++)for(unsigned y=0;y<ih;y++)for(unsigned xb=0;xb<row;xb+=256){const unsigned total=unsigned(std::min<std::uint64_t>(256,row-xb)),size=xb<iw?std::min(total,iw-xb):0;std::memset(bytes_,0,total);if(size){if(!read(s,m.address(n.input[0])+((std::uint64_t(c)*ih+y)*iw+xb)*4,block_,size*4))return false;for(unsigned j=0;j<size;j++)bytes_[j]=std::uint8_t(quant(block_[j],sx));}for(unsigned consumed=0;consumed<total;){const auto take=std::min<std::size_t>(total-consumed,2032-staged);std::memcpy(staging+staged,bytes_+consumed,take);staged+=take;consumed+=unsigned(take);if(staged==2032&&!flush_qA())return false;}}
 if(!flush_qA()){return false;}
 if(uploaded!=qbytes)return fail("conv_qA_bytecount");
 for(unsigned ob=0;ob<oc;ob+=8){const unsigned on=std::min(8u,oc-ob);if(!read(s,m.quantized_scales(*q)+ob*4,bscale_,on*4))return false;float bias[8]{};if(n.ni>2&&n.input[2]>=0&&!read(s,m.address(n.input[2])+ob*4,bias,on*4))return false;for(unsigned z=0;z<on;z++)if(!std::isfinite(bscale_[z])||bscale_[z]<=0||!std::isfinite(bias[z]))return fail("conv_weight_scale_bias");
  for(unsigned y=0;y<oh;y+=16)for(unsigned xb=0;xb<ow;xb+=16){const unsigned hh=std::min(16u,oh-y),ww=std::min(16u,ow-xb);for(unsigned ib=0;ib<ic;ib+=16){nd::Tile t;t.ic=std::min(16u,ic-ib);t.oc=on;t.oh=hh;t.ow=ww;t.kernel=k;t.stride=stride;t.first=ib==0;t.final=ib+t.ic==ic;t.full_h=ih;t.full_w=iw;t.origin_y=std::int32_t(y*stride)-std::int32_t(n.a[4]);t.origin_x=std::int32_t(xb*stride)-std::int32_t(n.a[5]);t.input_base=std::uint32_t(qi+ib*channel);t.input_row_pitch=std::uint32_t(row);t.input_channel_pitch=std::uint32_t(channel);t.weight_base=std::uint32_t(m.quantized_data(*q)+ob*q->pitch+ib*k*k);t.weight_oc_stride=q->pitch;t.output_base=std::uint32_t(qo);t.output_row_pitch=64;t.output_channel_pitch=hh*64;if(!check()||!nd::tile(t))return fail(nd::error());++stats_.tile_jobs;}
   for(unsigned z=0;z<on;z++){const bool plane=ww==16;if(plane){const auto size=std::size_t(hh)*64;if(!read(s,qo+z*hh*64,sums_,size))return false;++stats_.conv_dequant_read_calls;stats_.conv_dequant_read_bytes+=size;}for(unsigned yy=0;yy<hh;yy++){if(!plane){if(!read(s,qo+z*hh*64+yy*64,sums_,ww*4))return false;++stats_.conv_dequant_read_calls;stats_.conv_dequant_read_bytes+=ww*4;}const auto*row_sums=plane?sums_+yy*16:sums_;for(unsigned xx=0;xx<ww;xx++){out_[xx]=float(row_sums[xx])*(sx*bscale_[z])+bias[z];if(!std::isfinite(out_[xx]))return fail("conv_nonfinite_output");}if(!write(s,m.address(n.output[0])+((std::uint64_t(ob+z)*oh+y+yy)*ow+xb)*4,out_,ww*4))return false;}}
  }
 }++stats_.conv_calls;return safe(m);
}
bool Backend::multiplication(const rt::Model&m,const rt::Node&n,const rt::GraphStorage&s,const rt::QuantizedBinding*q){
 if(!safe(m)){return false;}if(q&&(q->node>=m.nn||m.n+q->node!=&n||q->source_tensor!=unsigned(n.input[1])||q->kind!=(n.op==rt::Gemm?rt::QuantizedGemm:rt::QuantizedMatMul)||m.quantized_data(*q)==UINT64_MAX||m.quantized_scales(*q)==UINT64_MAX))return fail("matmul_typed_binding");const auto&a=m.t[n.input[0]],&b=m.t[n.input[1]],&o=m.t[n.output[0]];if(a.type!=1||o.type!=1||a.rank<2||b.rank<2||o.rank<2||a.rank>o.rank||b.rank>o.rank)return fail("matmul_rank_type");const bool gemm=n.op==rt::Gemm,ta=gemm&&n.a[0],tb=gemm&&n.a[1];unsigned rows=o.d[o.rank-2];const unsigned cols=o.d[o.rank-1],k=ta?a.d[0]:a.d[a.rank-1];auto batches=o.count/rows/cols;if(q&&!gemm&&b.rank==2){rows=unsigned(o.count/cols);batches=1;}if(!rows||!cols||!k||k>65535||(!q&&b.type!=1)||(q&&(q->k!=k||q->n!=cols||q->pitch<a16(k))))return fail("matmul_shape_binding");
 const auto ap=a16(rows),bp=a16(k),qa=options_.scratch_base,qb=qa+ap*k+ap,qo=qb+(q?0:bp*8),qs=qo+8192,need=qs-options_.scratch_base+a16(std::uint64_t(rows)*4);if(need>options_.scratch_bytes)return fail("matmul_scratch");stats_.scratch_peak_bytes=std::max(stats_.scratch_peak_bytes,need);
 for(std::uint64_t batch=0;batch<batches;batch++){
  const auto abase=batchbase(a,o,batch),bbase=batchbase(b,o,batch);auto bv=[&](unsigned kk,unsigned col,float&v){stats_.dynamic_weight_fp32_read_bytes+=4;return number(s,m.address(n.input[1])+(bbase+(tb?std::uint64_t(col)*k+kk:std::uint64_t(kk)*cols+col))*4,v);};
  // Keep one256-row activation window resident in the graph cache. The
  // fixed256x16 float block transposes row-major input to full qA columns.
  for(unsigned rb=0;rb<rows;rb+=256){const unsigned rn=std::min(256u,rows-rb);
   std::fill(scales_,scales_+rn,0.f);
   if(ta){for(unsigned kk=0;kk<k;kk++){if(!read(s,m.address(n.input[0])+(abase+std::uint64_t(kk)*rows+rb)*4,block_,rn*4))return false;for(unsigned r=0;r<rn;r++){if(!std::isfinite(block_[r]))return fail("matmul_nonfinite_a");scales_[r]=std::max(scales_[r],std::fabs(block_[r]));}}}
   else for(unsigned r=0;r<rn;r++)for(unsigned kb=0;kb<k;kb+=256){const unsigned kn=std::min(256u,k-kb);if(!read(s,m.address(n.input[0])+(abase+std::uint64_t(rb+r)*k+kb)*4,block_,kn*4))return false;for(unsigned kk=0;kk<kn;kk++){if(!std::isfinite(block_[kk]))return fail("matmul_nonfinite_a");scales_[r]=std::max(scales_[r],std::fabs(block_[kk]));}}
   for(unsigned r=0;r<rn;r++){scales_[r]=scales_[r]?scales_[r]/127.f:1.f;if(!std::isfinite(scales_[r])||scales_[r]<=0)return fail("matmul_a_scale");}
   if(!write(s,qs+rb*4,scales_,rn*4))return false;
   for(unsigned kb=0;kb<k;kb+=16){const unsigned kn=std::min(16u,k-kb);
    if(ta){for(unsigned kk=0;kk<kn;kk++)if(!read(s,m.address(n.input[0])+(abase+std::uint64_t(kb+kk)*rows+rb)*4,transpose_+kk*256,rn*4))return false;}
    else for(unsigned r=0;r<rn;r++)if(!read(s,m.address(n.input[0])+(abase+std::uint64_t(rb+r)*k+kb)*4,transpose_+r*16,kn*4))return false;
    for(unsigned kk=0;kk<kn;kk++){std::memset(bytes_,0,sizeof bytes_);for(unsigned r=0;r<rn;r++)bytes_[r]=std::uint8_t(quant(ta?transpose_[kk*256+r]:transpose_[r*16+kk],scales_[r]));const auto count=std::size_t(a16(rn));if(!write(s,qa+std::uint64_t(kb+kk)*ap+rb,bytes_,count))return false;++stats_.activation_quant_write_calls;stats_.activation_quant_write_bytes+=count;}
   }
  }
  // Static B stays resident, so finish one256-row output window across all
  // columns before moving on. Dynamic B retains its eight-column slab order.
  for(unsigned rowpanel=0;rowpanel<(q?(rows+255)/256:1u);rowpanel++){
  for(unsigned cb=0;cb<cols;cb+=8){const unsigned cn=std::min(8u,cols-cb);if(q){if(!read(s,m.quantized_scales(*q)+cb*4,bscale_,cn*4))return false;}else{
    std::fill(bscale_,bscale_+8,0.f);for(unsigned kk=0;kk<k;kk++){if(!tb){if(!read(s,m.address(n.input[1])+(bbase+std::uint64_t(kk)*cols+cb)*4,block_,cn*4))return false;stats_.dynamic_weight_fp32_read_bytes+=cn*4;}else for(unsigned c=0;c<cn;c++)if(!bv(kk,cb+c,block_[c]))return false;for(unsigned c=0;c<cn;c++){if(!std::isfinite(block_[c]))return fail("dynamic_b_nonfinite");bscale_[c]=std::max(bscale_[c],std::fabs(block_[c]));}}
    for(unsigned c=0;c<cn;c++){bscale_[c]=bscale_[c]?bscale_[c]/127.f:1.f;if(!std::isfinite(bscale_[c])||bscale_[c]<=0)return fail("dynamic_b_scale");}
    for(unsigned kb=0;kb<bp;kb+=16){const unsigned kn=kb<k?std::min(16u,k-kb):0;for(unsigned kk=0;kk<kn;kk++){if(!tb){if(!read(s,m.address(n.input[1])+(bbase+std::uint64_t(kb+kk)*cols+cb)*4,block_+kk*8,cn*4))return false;stats_.dynamic_weight_fp32_read_bytes+=cn*4;}else for(unsigned c=0;c<cn;c++)if(!bv(kb+kk,cb+c,block_[kk*8+c]))return false;}for(unsigned c=0;c<cn;c++){std::memset(bytes_,0,16);for(unsigned kk=0;kk<kn;kk++)bytes_[kk]=std::uint8_t(quant(block_[kk*8+c],bscale_[c]));if(!write(s,qb+c*bp+kb,bytes_,16))return false;}}
   }
   for(unsigned c=0;c<cn;c++)if(!std::isfinite(bscale_[c])||bscale_[c]<=0)return fail("matmul_b_scale");
   for(unsigned rb=q?rowpanel*256:0;rb<(q?std::min(rows,(rowpanel+1)*256):rows);rb+=256){const unsigned rn=std::min(256u,rows-rb);nd::MatrixJob j;j.m=rn;j.k=k;j.n=cn;j.a_base=std::uint32_t(qa+rb);j.a_pitch=std::uint32_t(ap);j.b_base=std::uint32_t(q?m.quantized_data(*q)+cb*q->pitch:qb);j.b_pitch=q?q->pitch:std::uint32_t(bp);j.c_base=std::uint32_t(qo);j.c_pitch=std::uint32_t(a16(rn)*4);if(!check()||!nd::matrix(j))return fail(nd::error());++stats_.matrix_jobs;if(!read(s,qs+rb*4,scales_,rn*4))return false;
    for(unsigned c=0;c<cn;c++){if(!read(s,qo+c*j.c_pitch,sums_,rn*4))return false;for(unsigned r=0;r<rn;r++){float v=float(sums_[r])*(scales_[r]*bscale_[c])*(gemm?n.f[0]:1.f);if(gemm&&n.ni>2&&n.input[2]>=0){float bias;if(!number(s,m.address(n.input[2])+biasindex(m.t[n.input[2]],o,(batch*rows+rb+r)*cols+cb+c)*4,bias))return false;v+=n.f[1]*bias;}if(!std::isfinite(v))return fail("matmul_output_nonfinite");panel_[r*8+c]=v;}
    }
    for(unsigned r=0;r<rn;r++)if(!write(s,m.address(n.output[0])+((batch*rows+rb+r)*cols+cb)*4,panel_+r*8,cn*4))return false;
   }
  }
  }
 }++stats_.matmul_calls;return safe(m);
}
}}
