#include "transformer_graph.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
namespace inference { namespace transformer {
namespace {
std::uint32_t u32(const std::uint8_t*p){return std::uint32_t(p[0])|(std::uint32_t(p[1])<<8)|(std::uint32_t(p[2])<<16)|(std::uint32_t(p[3])<<24);}
bool overlap(std::uint64_t a,std::uint64_t n,std::uint64_t b,std::uint64_t m){return a<b+m&&b<a+n;}
constexpr std::uint64_t X=0,NORM=151296,QKV=302592,HIDDEN=756480,SCORES=1361664,ATTN=1827376,TEMP=1978672;
struct Context {
 const Model&m;const Storage&s;Scratch&w;const Hooks&h;Stats&stats;unsigned step=0;const char*stage="start";
 bool okay(){if(h.cancelled&&h.cancelled(h.context)){stats.error="cancelled";return false;}return true;}
 bool read(std::uint64_t a,void*p,std::size_t n){if(!okay())return false;if(!s.read(s.context,a,p,n)){stats.error="storage_read";return false;}stats.read_bytes+=n;return true;}
 bool write(std::uint64_t a,const void*p,std::size_t n){if(!okay())return false;if(!s.write(s.context,a,p,n)){stats.error="storage_write";return false;}stats.write_bytes+=n;return true;}
 static bool rd(void*p,std::uint64_t a,void*d,std::size_t n){return static_cast<Context*>(p)->read(a,d,n);}static bool wr(void*p,std::uint64_t a,const void*d,std::size_t n){return static_cast<Context*>(p)->write(a,d,n);}
 std::uint64_t now(){return h.clock_us?h.clock_us(h.context):0;}
 bool finish(const char*name,std::uint64_t begin,bool mat=false){++stats.operations;if(mat)stats.matmul_us+=now()-begin;else stats.other_us+=now()-begin;stage=name;if(h.progress)h.progress(h.context,name,++step,199);return okay();}
 bool mul(MatMul q,const char*name){if(!okay())return false;q.operation=step;const auto begin=now();Storage counted{this,rd,wr};const bool success=h.matmul?h.matmul(h.context,q,counted):cpu_matmul(q,counted,w);if(!success){if(!std::strcmp(stats.error,"none"))stats.error="matmul_failed";return false;}++stats.matmul_operations;stats.matmul_batches+=q.batches;stats.macs+=std::uint64_t(q.m)*q.k*q.n*q.batches;if(h.matmul)++stats.external_matmul_operations;else++stats.cpu_matmul_operations;return finish(name,begin,true);}
 Matrix fm(std::uint64_t offset,unsigned rows){return {m.arena()+offset,4,std::uint32_t(rows*4),0};}
 bool bias(std::uint64_t base,unsigned rows,unsigned cols,unsigned weight,const char*name){const auto begin=now();if(!read(m.weight(weight).address,w.a,cols*4))return false;
  if(rows==1){if(!read(base,w.b,cols*4))return false;for(unsigned j=0;j<cols;j++)w.b[j]+=w.a[j];if(!write(base,w.b,cols*4))return false;}
  else for(unsigned j=0;j<cols;j++){if(!read(base+std::uint64_t(j)*rows*4,w.b,rows*4))return false;for(unsigned i=0;i<rows;i++)w.b[i]+=w.a[j];if(!write(base+std::uint64_t(j)*rows*4,w.b,rows*4))return false;}
  return finish(name,begin);}
 bool linear(std::uint64_t input,std::uint64_t output,unsigned rows,unsigned k,unsigned n,unsigned weight,const char*name,unsigned input_pitch=0){MatMul q;q.a={input,4,std::uint32_t((input_pitch?input_pitch:rows)*4),0};q.b={m.weight(weight).address,4,std::uint32_t(k*4),0};q.output={output,4,std::uint32_t(rows*4),0};q.m=rows;q.k=k;q.n=n;return mul(q,name)&&bias(output,rows,n,weight+1,"bias");}
 bool cache_input(std::uint64_t input,unsigned count){
  if(!w.cache)return true;
  for(unsigned offset=0;offset<count;offset+=1024){const unsigned n=std::min(1024u,count-offset);if(!read(input+std::uint64_t(offset)*4,w.cache+offset,n*4))return false;}
  ++stats.cache_fills;stats.cache_input_bytes+=std::uint64_t(count)*4;return true;
 }
 bool feature(std::uint64_t input,unsigned j,unsigned rows,const float*&values){
  if(w.cache){values=w.cache+std::size_t(j)*rows;return true;}
  if(!read(input+std::uint64_t(j)*rows*4,w.c,rows*4))return false;
  values=w.c;return true;
 }
 bool norm(std::uint64_t input,std::uint64_t output,unsigned weight){const auto begin=now();constexpr unsigned rows=197,cols=192;std::fill_n(w.a,rows,0.0f);std::fill_n(w.b,rows,0.0f);if(!read(m.weight(weight).address,w.a+256,cols*4)||!read(m.weight(weight+1).address,w.a+512,cols*4)||!cache_input(input,rows*cols))return false;
  for(unsigned j=0;j<cols;j++){const float*values;if(!feature(input,j,rows,values))return false;for(unsigned i=0;i<rows;i++)w.a[i]+=values[i];}for(unsigned i=0;i<rows;i++)w.a[i]/=float(cols);
  for(unsigned j=0;j<cols;j++){const float*values;if(!feature(input,j,rows,values))return false;for(unsigned i=0;i<rows;i++){const float d=values[i]-w.a[i];w.b[i]+=d*d;}}for(unsigned i=0;i<rows;i++)w.b[i]=1/std::sqrt(w.b[i]/float(cols)+1e-12f);
  for(unsigned j=0;j<cols;j++){const float*values;if(!feature(input,j,rows,values))return false;for(unsigned i=0;i<rows;i++)w.c[i]=(values[i]-w.a[i])*w.b[i]*w.a[256+j]+w.a[512+j];if(!write(output+std::uint64_t(j)*rows*4,w.c,rows*4))return false;}return finish("layernorm",begin);}
 bool add(std::uint64_t dest,std::uint64_t other,unsigned count,const char*name){const auto begin=now();for(unsigned off=0;off<count;off+=1024){const auto n=std::min(1024u,count-off);if(!read(dest+off*4,w.a,n*4)||!read(other+off*4,w.b,n*4))return false;for(unsigned i=0;i<n;i++)w.c[i]=w.a[i]+w.b[i];if(!write(dest+off*4,w.c,n*4))return false;}return finish(name,begin);}
 bool gelu(std::uint64_t base,unsigned count){const auto begin=now();for(unsigned off=0;off<count;off+=1024){const auto n=std::min(1024u,count-off);if(!read(base+off*4,w.a,n*4))return false;for(unsigned j=0;j<n;j++)w.a[j]=0.5f*w.a[j]*(1+std::erf(w.a[j]/1.4142135623730951f));if(!write(base+off*4,w.a,n*4))return false;}return finish("gelu",begin);}
 bool softmax(std::uint64_t base){const auto begin=now();constexpr unsigned rows=197,cols=197;for(unsigned head=0;head<3;head++){const auto b=base+std::uint64_t(head)*rows*cols*4;if(!cache_input(b,rows*cols))return false;std::fill_n(w.a,rows,-std::numeric_limits<float>::infinity());std::fill_n(w.b,rows,0.0f);
  for(unsigned j=0;j<cols;j++){const float*values;if(!feature(b,j,rows,values))return false;for(unsigned i=0;i<rows;i++)w.a[i]=std::max(w.a[i],values[i]);}
  for(unsigned j=0;j<cols;j++){const float*values;if(!feature(b,j,rows,values))return false;for(unsigned i=0;i<rows;i++)w.b[i]+=std::exp(values[i]-w.a[i]);}
  for(unsigned j=0;j<cols;j++){const float*values;if(!feature(b,j,rows,values))return false;for(unsigned i=0;i<rows;i++){if(!std::isfinite(w.b[i])||w.b[i]<=0){stats.error="softmax_nonfinite";return false;}w.c[i]=std::exp(values[i]-w.a[i])/w.b[i];}if(!write(b+std::uint64_t(j)*rows*4,w.c,rows*4))return false;}}
  return finish("attention_softmax",begin);}
 bool unfold(){const auto begin=now();const auto input=m.input_address(),patches=m.arena()+602112;
  for(unsigned channel=0;channel<3;channel++)for(unsigned dy=0;dy<16;dy++)for(unsigned py=0;py<14;py++){
   if(!read(input+std::uint64_t(channel*224*224+(py*16+dy)*224)*4,w.a,224*4))return false;
   for(unsigned dx=0;dx<16;dx++){for(unsigned px=0;px<14;px++)w.b[px]=w.a[px*16+dx];const auto feature=channel*256+dy*16+dx;if(!write(patches+std::uint64_t(feature*196+py*14)*4,w.b,14*4))return false;}}
  return finish("patch_unfold",begin);}
 bool embedding(){if(!unfold())return false;MatMul q;q.a={m.arena()+602112,4,196*4,0};q.b={m.weight(0).address,4,768*4,0};q.output={m.arena()+X+4,4,197*4,0};q.m=196;q.k=768;q.n=192;if(!mul(q,"patch_projection"))return false;
  const auto begin=now();if(!read(m.weight(1).address,w.a,192*4)||!read(m.weight(2).address,w.b,192*4))return false;
  for(unsigned feature=0;feature<192;feature++){w.c[0]=w.b[feature];if(!read(m.arena()+X+std::uint64_t(feature)*197*4+4,w.c+1,196*4))return false;for(unsigned i=1;i<197;i++)w.c[i]+=w.a[feature];if(!write(m.arena()+X+std::uint64_t(feature)*197*4,w.c,197*4))return false;}
  return finish("class_token_bias",begin)&&add(m.arena()+X,m.weight(3).address,197*192,"position_embedding");}
};
}
std::uint32_t crc32(const void*data,std::size_t bytes){auto*p=static_cast<const std::uint8_t*>(data);std::uint32_t c=UINT32_MAX;while(bytes--){c^=*p++;for(int j=0;j<8;j++)c=(c>>1)^((c&1)?0xedb88320u:0);}return~c;}
Weight Model::weight(unsigned i)const{if(!metadata_||i>=weight_count)return {};const auto*p=metadata_+128+i*16;return{weights_+u32(p),u32(p+4),u32(p+8),u32(p+12)};}
bool Model::load(const void*data,std::size_t bytes,std::size_t package_bytes,std::uint32_t crc,std::uint64_t constants,std::uint64_t arena,std::uint64_t capacity){metadata_=nullptr;if(!data||bytes!=metadata_bytes||crc32(data,bytes)!=crc)return false;const auto*p=static_cast<const std::uint8_t*>(data);if(std::memcmp(p,"DTP1",4)||u32(p+4)!=1||u32(p+8)!=128||u32(p+12)!=152||u32(p+16)!=2560||u32(p+24)!=package_bytes||u32(p+28)!=12||u32(p+32)!=3||u32(p+36)!=192||u32(p+40)!=768||u32(p+44)!=1000)return false;const auto n=u32(p+20);if(std::uint64_t(n)+2560!=package_bytes||constants%16||arena%16||constants>capacity||n>capacity-constants||arena>capacity||arena_bytes>capacity-arena||overlap(constants,n,arena,arena_bytes))return false;
 for(unsigned i=0;i<152;i++){const auto*r=p+128+i*16;const auto off=u32(r),count=u32(r+4),rows=u32(r+8),cols=u32(r+12);unsigned er=0,ec=1;
  if(i==0){er=192;ec=768;}else if(i==1||i==2)er=192;else if(i==3){er=192;ec=197;}else if(i>=148){er=i==150||i==151?1000:192;if(i==150)ec=192;}else{switch((i-4)%12){case 0:case 1:case 5:case 6:case 7:case 11:er=192;break;case 2:er=576;ec=192;break;case 3:er=576;break;case 4:er=192;ec=192;break;case 8:er=768;ec=192;break;case 9:er=768;break;case 10:er=192;ec=768;break;}}
  if(rows!=er||cols!=ec||count!=std::uint64_t(er)*ec||off%16||std::uint64_t(off)+std::uint64_t(count)*4>n)return false;
 }metadata_=p;weights_=constants;arena_=arena;constant_bytes_=n;return true;}
bool cpu_matmul(const MatMul&q,const Storage&s,Scratch&w){if(!q.m||!q.k||!q.n||!q.batches||!s.read||!s.write)return false;for(unsigned batch=0;batch<q.batches;batch++) { for(unsigned i=0;i<q.m;i++) { for(unsigned j=0;j<q.n;j++){float sum=0;for(unsigned off=0;off<q.k;off+=1024){const unsigned count=std::min(1024u,q.k-off);const auto a=q.a.address+std::uint64_t(batch)*q.a.batch_stride+std::uint64_t(i)*q.a.row_stride+std::uint64_t(off)*q.a.column_stride,b=q.b.address+std::uint64_t(batch)*q.b.batch_stride+std::uint64_t(off)*q.b.row_stride+std::uint64_t(j)*q.b.column_stride;
 if(q.a.column_stride==4){if(!s.read(s.context,a,w.a,count*4))return false;}else for(unsigned k=0;k<count;k++)if(!s.read(s.context,a+std::uint64_t(k)*q.a.column_stride,w.a+k,4))return false;
 if(q.b.row_stride==4){if(!s.read(s.context,b,w.b,count*4))return false;}else for(unsigned k=0;k<count;k++)if(!s.read(s.context,b+std::uint64_t(k)*q.b.row_stride,w.b+k,4))return false;
 for(unsigned k=0;k<count;k++)sum+=w.a[k]*w.b[k];}sum*=q.alpha;if(!std::isfinite(sum)||!s.write(s.context,q.output.address+std::uint64_t(batch)*q.output.batch_stride+std::uint64_t(i)*q.output.row_stride+std::uint64_t(j)*q.output.column_stride ,&sum,4))return false;} } }
return true;}
bool run(const Model&m,const Storage&s,Scratch&w,const Hooks&h,Stats&stats){stats={};if(!m.valid()||!s.read||!s.write){stats.error="invalid_model_storage";return false;}if((w.cache&&(w.cache_floats<Scratch::cache_required_floats||reinterpret_cast<std::uintptr_t>(w.cache)%alignof(float)))||(!w.cache&&w.cache_floats)){stats.error="invalid_cache_capacity";return false;}stats.cache_bytes=w.cache?Scratch::cache_required_floats*4:0;Context c{m,s,w,h,stats};const auto begin=c.now();if(!c.embedding())return false;
 for(unsigned layer=0;layer<12;layer++){const unsigned weight=4+layer*12;if(!c.norm(m.arena()+X,m.arena()+NORM,weight)||!c.linear(m.arena()+NORM,m.arena()+QKV,197,192,576,weight+2,"qkv_projection"))return false;
  MatMul q;q.a=c.fm(QKV,197);q.a.batch_stride=64*197*4;q.b={m.arena()+QKV+192*197*4,197*4,4,64*197*4};q.output={m.arena()+SCORES,4,197*4,197*197*4};q.m=197;q.k=64;q.n=197;q.batches=3;q.alpha=.125f;if(!c.mul(q,"attention_qk")||!c.softmax(m.arena()+SCORES))return false;
  q.a={m.arena()+SCORES,4,197*4,197*197*4};q.b={m.arena()+QKV+384*197*4,4,197*4,64*197*4};q.output={m.arena()+ATTN,4,197*4,64*197*4};q.m=197;q.k=197;q.n=64;q.alpha=1;if(!c.mul(q,"attention_av")||!c.linear(m.arena()+ATTN,m.arena()+TEMP,197,192,192,weight+4,"attention_projection")||!c.add(m.arena()+X,m.arena()+TEMP,197*192,"attention_residual")||!c.norm(m.arena()+X,m.arena()+NORM,weight+6)||!c.linear(m.arena()+NORM,m.arena()+HIDDEN,197,192,768,weight+8,"mlp_fc1")||!c.gelu(m.arena()+HIDDEN,197*768)||!c.linear(m.arena()+HIDDEN,m.arena()+TEMP,197,768,192,weight+10,"mlp_fc2")||!c.add(m.arena()+X,m.arena()+TEMP,197*192,"mlp_residual"))return false;++stats.blocks_completed;
 }
 if(!c.norm(m.arena()+X,m.arena()+NORM,148)||!c.linear(m.arena()+NORM,m.output_address(),1,192,1000,150,"classifier",197))return false;
 if(!c.read(m.output_address(),w.a,1000*4))return false;
 for(unsigned i=0;i<1000;i++)if(!std::isfinite(w.a[i])){stats.error="output_nonfinite";return false;}
 stats.total_us=c.now()-begin;return true;}
}}
