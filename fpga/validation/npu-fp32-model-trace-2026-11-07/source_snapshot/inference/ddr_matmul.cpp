extern "C" void epilogue_trace(int,float,float,float,unsigned,unsigned,unsigned,float);
#include "ddr_matmul.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
namespace inference { namespace ddr_matmul { namespace {
constexpr std::uint64_t capacity=UINT64_C(128)*1024*1024;
std::uint64_t align16(std::uint64_t x){return(x+15)&~UINT64_C(15);}
bool add(std::uint64_t a,std::uint64_t b,std::uint64_t&v){if(a>UINT64_MAX-b)return false;v=a+b;return true;}
bool mul(std::uint64_t a,std::uint64_t b,std::uint64_t&v){if(b&&a>UINT64_MAX/b)return false;v=a*b;return true;}
bool overlap(std::uint64_t a,std::uint64_t ae,std::uint64_t b,std::uint64_t be){return a<be&&b<ae;}
bool extent(const MatrixView&v,unsigned rows,unsigned cols,unsigned batches,std::uint64_t stride,std::uint64_t&end){
 std::uint64_t x,y,z;if(!rows||!cols||!batches||v.base%4||v.row_stride%4||v.column_stride%4||stride%4||!v.row_stride||!v.column_stride)return false;
 if(!mul(rows-1,v.row_stride,x)||!mul(cols-1,v.column_stride,y)||!add(x,y,x)||!mul(batches-1,stride,z)||!add(x,z,x)||!add(x,4,x)||!add(v.base,x,end))return false;
 return end<=capacity;
}
bool same_view(const MatrixView&a,const MatrixView&b){return a.base==b.base&&a.row_stride==b.row_stride&&a.column_stride==b.column_stride;}
bool binding_layout(const QuantizedB&q,std::uint64_t&source_end,std::uint64_t&q_end,std::uint64_t&s_end){
 std::uint64_t bytes;if(!q.k||q.k>133144||!q.n||!q.session_cookie||!q.source_identity||q.data_base%16||q.scales_base%16||q.column_pitch%16||q.column_pitch<align16(q.k)||q.column_pitch>UINT32_MAX)return false;
 if(!extent(q.source,q.k,q.n,1,0,source_end)||!mul(q.n,q.column_pitch,bytes)||!add(q.data_base,bytes,q_end)||!add(q.scales_base,align16(std::uint64_t(q.n)*4),s_end)||q_end>capacity||s_end>capacity)return false;
 return !overlap(q.data_base,q_end,q.scales_base,s_end)&&!overlap(q.data_base,q_end,q.source.base,source_end)&&!overlap(q.scales_base,s_end,q.source.base,source_end);
}
std::uint32_t crc_update(std::uint32_t crc,const void*data,std::size_t bytes){const auto*p=static_cast<const std::uint8_t*>(data);for(std::size_t i=0;i<bytes;i++){crc^=p[i];for(unsigned j=0;j<8;j++)crc=(crc>>1)^(UINT32_C(0xedb88320)&(0u-(crc&1)));}return crc;}
struct Preparer {
 const QuantizedB&q;const Backend&b;Workspace&w;PrepareReport&p;
 bool fail(const char*s){if(!p.error[0])std::snprintf(p.error,sizeof p.error,"%s",s);return false;}
 bool check(){if(b.cancelled&&b.cancelled(b.context)){p.cancelled=true;return fail("cancelled");}return true;}
 bool session(){if(!check())return false;if(!b.unchanged(b.context))return fail("ddr_session_changed");if(!b.validate_b_binding(b.context,q,false))return fail("quantized_b_prepare_binding");return true;}
 bool read(std::uint64_t a,void*d,std::size_t n,bool verify=false){if(!check())return false;if(!b.read(b.context,a,d,n))return fail(verify?"cache_verify_read_failed":"source_read_failed");if(verify)p.verify_read_bytes+=n;else p.source_read_bytes+=n;return check();}
 bool write(std::uint64_t a,const void*d,std::size_t n){if(!check())return false;if(!b.write(b.context,a,d,n))return fail("cache_write_failed");p.write_bytes+=n;return check();}
 bool line(unsigned k,unsigned col,unsigned count){const auto address=q.source.base+std::uint64_t(k)*q.source.row_stride+std::uint64_t(col)*q.source.column_stride;
  if(q.source.row_stride==4){if(!read(address,w.line,count*4))return false;}else for(unsigned i=0;i<count;i++)if(!read(address+i*q.source.row_stride,w.line+i,4))return false;
  for(unsigned i=0;i<count;i++)if(!std::isfinite(w.line[i]))return fail("nonfinite_b_source");
  return true;
 }
 bool execute(){
  if(!b.read||!b.write||!b.unchanged||!b.abort||!b.validate_b_binding)return fail("missing_prepare_backend");
  std::uint64_t source_end,q_end,s_end;if(!binding_layout(q,source_end,q_end,s_end))return fail("invalid_quantized_b_layout");
  if(!session())return false;
  std::uint32_t qc=UINT32_MAX,sc=UINT32_MAX;
  for(unsigned nb=0;nb<q.n;nb+=8){const unsigned nn=std::min(8u,q.n-nb);std::fill(w.scales,w.scales+8,0.f);
   for(unsigned col=0;col<nn;col++){
    float mx=0;for(unsigned k=0;k<q.k;k+=256){const unsigned count=std::min(256u,q.k-k);if(!line(k,nb+col,count))return false;for(unsigned i=0;i<count;i++)mx=std::max(mx,std::fabs(w.line[i]));}
    const float scale=mx?mx/127.f:1.f;if(!std::isfinite(scale)||scale==0)return fail("invalid_b_scale");w.scales[col]=scale;
    std::uint64_t written=0;
    for(unsigned k=0;k<q.k;k+=256){const unsigned count=std::min(256u,q.k-k);if(!line(k,nb+col,count))return false;std::memset(w.bytes,0,sizeof w.bytes);for(unsigned i=0;i<count;i++){const float v=std::round(w.line[i]/scale);w.bytes[i]=std::uint8_t(std::int8_t(std::max(-127.f,std::min(127.f,v))));}const auto n=std::size_t(align16(count));if(!write(q.data_base+(nb+col)*q.column_pitch+k,w.bytes,n))return false;qc=crc_update(qc,w.bytes,n);written=k+n;}
    std::memset(w.bytes,0,sizeof w.bytes);while(written<q.column_pitch){const auto n=std::size_t(std::min<std::uint64_t>(256,q.column_pitch-written));if(!write(q.data_base+(nb+col)*q.column_pitch+written,w.bytes,n))return false;qc=crc_update(qc,w.bytes,n);written+=n;}
   }
   const auto n=std::size_t(align16(nn*4));if(!write(q.scales_base+nb*4,w.scales,n))return false;sc=crc_update(sc,w.scales,n);
  }
  p.expected_quantized_crc32=qc^UINT32_MAX;p.expected_scales_crc32=sc^UINT32_MAX;
  qc=sc=UINT32_MAX;
  for(std::uint64_t address=q.data_base;address<q_end;){const auto n=std::size_t(std::min<std::uint64_t>(1024,q_end-address));if(!read(address,w.block,n,true))return false;qc=crc_update(qc,w.block,n);address+=n;}
  for(std::uint64_t address=q.scales_base;address<s_end;){const auto n=std::size_t(std::min<std::uint64_t>(1024,s_end-address));if(!read(address,w.block,n,true))return false;sc=crc_update(sc,w.block,n);address+=n;}
  p.actual_quantized_crc32=qc^UINT32_MAX;p.actual_scales_crc32=sc^UINT32_MAX;
  if(p.actual_quantized_crc32!=p.expected_quantized_crc32||p.actual_scales_crc32!=p.expected_scales_crc32)return fail("quantized_b_readback_crc");
  return session();
 }
};
struct Runner {
 const Request&r;const Backend&b;Workspace&w;Report&p;
 bool fail(const char*s){if(!p.error[0])std::snprintf(p.error,sizeof p.error,"%s",s);return false;}
 bool check(){if(b.cancelled&&b.cancelled(b.context)){p.cancelled=true;return fail("cancelled");}return true;}
 bool session(){if(!check())return false;if(!b.unchanged(b.context))return fail("ddr_session_changed");return true;}
 bool read(std::uint64_t a,void*d,std::size_t n){if(!check())return false;if(!b.read(b.context,a,d,n))return fail("ddr_read_failed");p.read_bytes+=n;return check();}
 bool write(std::uint64_t a,const void*d,std::size_t n){if(!check())return false;if(!b.write(b.context,a,d,n))return fail("ddr_write_failed");p.write_bytes+=n;return check();}
 bool line(const MatrixView&v,unsigned row,unsigned col,bool along_rows,unsigned count,float*out){
  const auto a=v.base+std::uint64_t(row)*v.row_stride+std::uint64_t(col)*v.column_stride;const auto stride=along_rows?v.row_stride:v.column_stride;
  if(stride==4){if(!read(a,out,count*4))return false;}else for(unsigned j=0;j<count;j++)if(!read(a+j*stride,out+j,4))return false;
  for(unsigned j=0;j<count;j++)if(!std::isfinite(out[j]))return fail("nonfinite_input");
  return true;
 }
 static std::int8_t quant(float x,float scale){const float q=std::round(x/scale);return std::int8_t(std::max(-127.f,std::min(127.f,q)));}
 bool execute(){
  if(!b.read||!b.write||!b.tile||!b.unchanged||!b.abort)return fail("missing_backend");
  const auto need=scratch_required(r.m,r.k,r.activation_per_row,r.cache_row_scales);p.scratch_required=need;
  std::uint64_t ae,be,oe,se;
  if(!need||!r.n||!r.batches||r.m>65535||r.k>133144||!std::isfinite(r.alpha)||r.scratch_base%16||r.scratch_bytes<need||!add(r.scratch_base,r.scratch_bytes,se)||se>capacity||
    !extent(r.a,r.m,r.k,r.batches,r.a_batch_stride,ae)||!extent(r.b,r.k,r.n,r.batches,r.b_batch_stride,be)||!extent(r.output,r.m,r.n,r.batches,r.output_batch_stride,oe))return fail("invalid_descriptor");
  const bool output_columns=r.output.row_stride==4 && r.output.column_stride>=std::uint64_t(r.m)*4;
  if(!output_columns && (r.output.column_stride!=4||r.output.row_stride<std::uint64_t(r.n)*4))return fail("output_layout");
  const auto output_major=output_columns?r.output.column_stride:r.output.row_stride;
  const auto output_minor_bytes=std::uint64_t(output_columns?r.m:r.n)*4;
  const auto output_major_count=output_columns?r.n:r.m;
  const std::uint64_t one_output=(output_major_count-1)*output_major+output_minor_bytes;
  if(r.batches>1 && r.output_batch_stride<one_output){
   std::uint64_t last;if(r.output_batch_stride<output_minor_bytes||!mul(r.batches-1,r.output_batch_stride,last)||last>output_major-output_minor_bytes)return fail("output_batch_overlap");
  }
  if(overlap(r.scratch_base,se,r.a.base,ae)||overlap(r.scratch_base,se,r.b.base,be)||overlap(r.scratch_base,se,r.output.base,oe)||overlap(r.output.base,oe,r.a.base,ae)||overlap(r.output.base,oe,r.b.base,be))return fail("memory_overlap");
  if(r.quantized_b){
   const auto&q=*r.quantized_b;std::uint64_t source_end,q_end,s_end;
   if(!b.validate_b_binding||q.k!=r.k||q.n!=r.n||!same_view(q.source,r.b)||(r.batches>1&&r.b_batch_stride)||!binding_layout(q,source_end,q_end,s_end))return fail("invalid_quantized_b_binding");
   if(overlap(q.data_base,q_end,r.a.base,ae)||overlap(q.data_base,q_end,r.output.base,oe)||overlap(q.data_base,q_end,r.scratch_base,se)||overlap(q.scales_base,s_end,r.a.base,ae)||overlap(q.scales_base,s_end,r.output.base,oe)||overlap(q.scales_base,s_end,r.scratch_base,se))return fail("quantized_b_memory_overlap");
  }
  if(!session())return false;
  if(r.quantized_b&&!b.validate_b_binding(b.context,*r.quantized_b,true))return fail("quantized_b_binding_not_ready");
  const bool cached_scales=r.activation_per_row&&r.cache_row_scales&&r.m<=256;
  const auto ap=align16(r.m),bp=align16(r.k),qa=r.scratch_base,qb=qa+ap*r.k,qo=qb+bp*8,qs=qo+8192;
  for(unsigned batch=0;batch<r.batches;batch++){
   auto av=r.a,bv=r.b,ov=r.output;av.base+=batch*r.a_batch_stride;bv.base+=batch*r.b_batch_stride;ov.base+=batch*r.output_batch_stride;
   float as=1;
   if(!r.activation_per_row){
   float maximum=0;
   if(av.row_stride==4){for(unsigned col=0;col<r.k;col++)for(unsigned row=0;row<r.m;row+=256){const unsigned n=std::min(256u,r.m-row);if(!line(av,row,col,true,n,w.line))return false;for(unsigned j=0;j<n;j++)maximum=std::max(maximum,std::fabs(w.line[j]));}}
   else for(unsigned y=0;y<r.m;y++)for(unsigned z=0;z<r.k;z+=256){const unsigned n=std::min(256u,r.k-z);if(!line(av,y,z,false,n,w.line))return false;for(unsigned j=0;j<n;j++)maximum=std::max(maximum,std::fabs(w.line[j]));}
   as=maximum?maximum/127.f:1.f;if(!std::isfinite(as)||as==0)return fail("invalid_a_scale");
   if(av.row_stride==4){
    for(unsigned col=0;col<r.k;col++)for(unsigned row=0;row<r.m;row+=256){const unsigned nm=std::min(256u,r.m-row);if(!line(av,row,col,true,nm,w.line))return false;std::memset(w.bytes,0,sizeof w.bytes);for(unsigned j=0;j<nm;j++)w.bytes[j]=std::uint8_t(quant(w.line[j],as));if(!write(qa+col*ap+row,w.bytes,std::size_t(align16(nm))))return false;}
   }else{
   // 16x16 transpose only: no full activation allocation in host memory.
   for(unsigned z=0;z<r.k;z+=16)for(unsigned y=0;y<r.m;y+=16){
    const unsigned nk=std::min(16u,r.k-z),nm=std::min(16u,r.m-y);
    for(unsigned row=0;row<nm;row++)if(!line(av,y+row,z,false,nk,w.block+row*16))return false;
    for(unsigned col=0;col<nk;col++){std::memset(w.bytes,0,16);for(unsigned row=0;row<nm;row++)w.bytes[row]=std::uint8_t(quant(w.block[row*16+col],as));if(!write(qa+(z+col)*ap+y,w.bytes,16))return false;}
   }
   }
   }else{
    for(unsigned panel=0;panel<r.m;panel+=256){
     const unsigned nm=std::min(256u,r.m-panel);
     std::fill(w.a_scales,w.a_scales+256,0.f);
     if(av.row_stride==4){
      for(unsigned col=0;col<r.k;col++){if(!line(av,panel,col,true,nm,w.line))return false;for(unsigned row=0;row<nm;row++)w.a_scales[row]=std::max(w.a_scales[row],std::fabs(w.line[row]));}
     }else{
      for(unsigned row=0;row<nm;row++)for(unsigned col=0;col<r.k;col+=256){const unsigned nk=std::min(256u,r.k-col);if(!line(av,panel+row,col,false,nk,w.line))return false;for(unsigned j=0;j<nk;j++)w.a_scales[row]=std::max(w.a_scales[row],std::fabs(w.line[j]));}
     }
     for(unsigned row=0;row<nm;row++){w.a_scales[row]=w.a_scales[row]?w.a_scales[row]/127.f:1.f;if(!std::isfinite(w.a_scales[row])||w.a_scales[row]==0)return fail("invalid_a_row_scale");}
     if(!cached_scales && !write(qs+panel*4,w.a_scales,std::size_t(align16(nm)*4)))return false;
     if(av.row_stride==4){
      for(unsigned col=0;col<r.k;col++){if(!line(av,panel,col,true,nm,w.line))return false;std::memset(w.bytes,0,sizeof w.bytes);for(unsigned row=0;row<nm;row++)w.bytes[row]=std::uint8_t(quant(w.line[row],w.a_scales[row]));if(!write(qa+col*ap+panel,w.bytes,std::size_t(align16(nm))))return false;}
     }else{
      for(unsigned z=0;z<r.k;z+=16)for(unsigned y=0;y<nm;y+=16){const unsigned nk=std::min(16u,r.k-z),rows=std::min(16u,nm-y);for(unsigned row=0;row<rows;row++)if(!line(av,panel+y+row,z,false,nk,w.block+row*16))return false;for(unsigned col=0;col<nk;col++){std::memset(w.bytes,0,16);for(unsigned row=0;row<rows;row++)w.bytes[row]=std::uint8_t(quant(w.block[row*16+col],w.a_scales[y+row]));if(!write(qa+(z+col)*ap+panel+y,w.bytes,16))return false;}}
     }
    }
   }
   for(unsigned nb=0;nb<r.n;nb+=8){
    const unsigned nn=std::min(8u,r.n-nb);
    if(r.quantized_b){
     if(!read(r.quantized_b->scales_base+nb*4,w.scales,nn*4))return false;
     for(unsigned col=0;col<nn;col++)if(!std::isfinite(w.scales[col])||w.scales[col]<=0)return fail("invalid_cached_b_scale");
    }else     if(bv.row_stride==4){
    for(unsigned col=0;col<nn;col++){
     float mx=0;for(unsigned z=0;z<r.k;z+=256){const unsigned nk=std::min(256u,r.k-z);if(!line(bv,z,nb+col,true,nk,w.line))return false;for(unsigned j=0;j<nk;j++)mx=std::max(mx,std::fabs(w.line[j]));}
     const float bs=mx?mx/127.f:1.f;if(!std::isfinite(bs)||bs==0)return fail("invalid_b_scale");w.scales[col]=bs;
     for(unsigned z=0;z<r.k;z+=256){const unsigned nk=std::min(256u,r.k-z);if(!line(bv,z,nb+col,true,nk,w.line))return false;std::memset(w.bytes,0,sizeof w.bytes);for(unsigned j=0;j<nk;j++)w.bytes[j]=std::uint8_t(quant(w.line[j],bs));if(!write(qb+col*bp+z,w.bytes,std::size_t(align16(nk))))return false;}
    }
    }else{
     // Dynamic QK: contiguous token panel per feature, no scalar DDR gather.
     for(unsigned col=0;col<nn;col++)w.scales[col]=0;
     for(unsigned z=0;z<r.k;z+=16){const unsigned nk=std::min(16u,r.k-z);for(unsigned row=0;row<nk;row++){if(!line(bv,z+row,nb,false,nn,w.block+row*8))return false;for(unsigned col=0;col<nn;col++)w.scales[col]=std::max(w.scales[col],std::fabs(w.block[row*8+col]));}}
     for(unsigned col=0;col<nn;col++){w.scales[col]=w.scales[col]?w.scales[col]/127.f:1.f;if(!std::isfinite(w.scales[col])||w.scales[col]==0)return fail("invalid_b_scale");}
     for(unsigned z=0;z<r.k;z+=16){const unsigned nk=std::min(16u,r.k-z);for(unsigned row=0;row<nk;row++)if(!line(bv,z+row,nb,false,nn,w.block+row*8))return false;for(unsigned col=0;col<nn;col++){std::memset(w.bytes,0,16);for(unsigned row=0;row<nk;row++)w.bytes[row]=std::uint8_t(quant(w.block[row*8+col],w.scales[col]));if(!write(qb+col*bp+z,w.bytes,16))return false;}}
    }
    for(unsigned mb=0;mb<r.m;mb+=256){
     const unsigned mm=std::min(256u,r.m-mb),width=std::min(16u,r.m),height=(mm+width-1)/width;
     for(unsigned kb=0;kb<r.k;kb+=16){
      npu_ddr::Tile t;t.ic=std::min(16u,r.k-kb);t.oc=nn;t.oh=height;t.ow=width;t.kernel=1;t.stride=1;t.first=kb==0;t.final=kb+t.ic==r.k;
      t.full_h=(r.m+width-1)/width;t.full_w=width;t.origin_y=mb/width;t.input_base=qa+kb*ap;t.input_row_pitch=16;t.input_channel_pitch=ap;
      t.weight_base=r.quantized_b?r.quantized_b->data_base+nb*r.quantized_b->column_pitch+kb:qb+kb;t.weight_oc_stride=r.quantized_b?r.quantized_b->column_pitch:bp;t.output_base=qo;t.output_row_pitch=64;t.output_channel_pitch=height*64;
      if(!check())return false;
      if(!b.tile(b.context,t))return fail("fpga_matmul_tile_failed");
      p.tile_jobs++;p.macs+=std::uint64_t(mm)*nn*t.ic;p.padded_macs+=std::uint64_t(width)*height*nn*t.ic;
      if(!check())return false;
     }
     if(r.activation_per_row && !cached_scales){
      if(!read(qs+mb*4,w.a_scales,mm*4))return false;
      for(unsigned row=0;row<mm;row++)if(!std::isfinite(w.a_scales[row])||w.a_scales[row]<=0)return fail("invalid_staged_a_scale");
     }
     const unsigned channel_bytes=height*64;
     if(output_columns){
      for(unsigned col=0;col<nn;col++){
       if(!read(qo+col*channel_bytes,w.sums,mm*4))return false;
       for(unsigned row=0;row<mm;row++){w.line[row]=float(w.sums[row])*((r.activation_per_row?w.a_scales[row]:as)*w.scales[col])*r.alpha;epilogue_trace(w.sums[row],r.activation_per_row?w.a_scales[row]:as,w.scales[col],r.alpha,mb+row,nb+col,batch,w.line[row]);if(!std::isfinite(w.line[row]))return fail("nonfinite_output");}
       if(!write(ov.base+mb*ov.row_stride+(nb+col)*ov.column_stride,w.line,mm*4))return false;
      }
     }else{
      // Compatibility layout: bounded16x8 output panel, no scalar writes.
      for(unsigned pixel=0;pixel<mm;pixel+=16){const unsigned count=std::min(16u,mm-pixel);
       for(unsigned col=0;col<nn;col++){
        if(!read(qo+col*channel_bytes+pixel*4,w.sums,count*4))return false;
        for(unsigned row=0;row<count;row++){w.block[col*16+row]=float(w.sums[row])*((r.activation_per_row?w.a_scales[pixel+row]:as)*w.scales[col])*r.alpha;epilogue_trace(w.sums[row],r.activation_per_row?w.a_scales[pixel+row]:as,w.scales[col],r.alpha,mb+pixel+row,nb+col,batch,w.block[col*16+row]);if(!std::isfinite(w.block[col*16+row]))return fail("nonfinite_output");}
       }
       for(unsigned row=0;row<count;row++){for(unsigned col=0;col<nn;col++)w.line[col]=w.block[col*16+row];if(!write(ov.base+(mb+pixel+row)*ov.row_stride+nb*4,w.line,nn*4))return false;}
      }
     }

    }
   }
  }
  if(r.quantized_b&&!b.validate_b_binding(b.context,*r.quantized_b,true))return fail("quantized_b_binding_changed");
  return session();
 }
};
}
bool prepare_b(const QuantizedB&q,const Backend&b,Workspace&w,PrepareReport&p){p=PrepareReport{};Preparer c{q,b,w,p};if(!c.execute()){if(b.abort)b.abort(b.context);return false;}p.valid=true;return true;}
std::uint64_t scratch_required(unsigned m,unsigned k,bool activation_per_row,bool cache_row_scales){if(!m||!k)return 0;std::uint64_t x,y;if(!mul(align16(m),k,x)||!mul(align16(k),8,y)||!add(x,y,x)||!add(x,8192,x))return 0;
 if(activation_per_row&&(!cache_row_scales||m>256)){if(!mul(align16(m),4,y)||!add(x,y,x))return 0;}
 return x;}
bool run(const Request&r,const Backend&b,Workspace&w,Report&p){p=Report{};Runner c{r,b,w,p};if(!c.execute()){if(b.abort)b.abort(b.context);return false;}p.valid=true;return true;}
}}
