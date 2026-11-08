#include "rtdetr_graph.hpp"
#include "index32_contract.hpp"
#include "rtdetr_selection.hpp"
#include <cstring>
#include <limits>
#include <new>
namespace inference { namespace rtdetr {
namespace {
unsigned item(const Tensor&t){return t.type==7?8:4;}
struct A {const Tensor&t;const GraphStorage&s;std::uint32_t address;const unsigned char*p;bool&ok;mutable std::uint32_t cache_base=UINT32_MAX;mutable unsigned char cache[1024];
 A(const Model&m,unsigned id,const GraphStorage&ss,bool&o):t(m.t[id]),s(ss),address(m.address(id)),p(ss.map?static_cast<const unsigned char*>(ss.map(ss.context,address,t.count*item(t))):nullptr),ok(o){}
 double get(std::uint32_t i)const{if(i>=t.count){ok=false;return 0;}const unsigned char*q;if(p)q=p+i*item(t);else{const auto base=i/128*128;if(cache_base!=base){const auto n=std::min<std::uint32_t>(128,t.count-base);if(!s.read(s.context,address+base*item(t),cache,n*item(t))){ok=false;return 0;}cache_base=base;}q=cache+(i-cache_base)*item(t);}if(t.type==1){float v;std::memcpy(&v,q,4);return v;}if(t.type==7){std::int64_t v;std::memcpy(&v,q,8);return double(v);}std::int32_t v;std::memcpy(&v,q,4);return v;}
};
void coords(const Tensor&t,std::uint32_t i,std::uint32_t*c){for(unsigned d=t.rank;d-->0;){c[d]=i%t.d[d];i/=t.d[d];}}
std::uint32_t linear(const Tensor&t,const std::uint32_t*c){std::uint32_t i=0;for(unsigned d=0;d<t.rank;++d)i=i*t.d[d]+c[d];return i;}
std::uint32_t broadcast(const Tensor&t,const Tensor&o,const std::uint32_t*c){std::uint32_t i=0;for(unsigned d=0;d<t.rank;++d)i=i*t.d[d]+(t.d[d]==1?0:c[d+o.rank-t.rank]);return i;}
bool put(const Model&m,unsigned id,const GraphStorage&s,std::uint32_t base,const double*v,unsigned count){const auto&t=m.t[id];unsigned char b[128*8];for(unsigned i=0;i<count;++i){if(t.type==1){const float x=float(v[i]);std::memcpy(b+i*4,&x,4);}else if(t.type==7){const auto x=std::int64_t(v[i]);std::memcpy(b+i*8,&x,8);}else{const auto x=std::int32_t(v[i]);std::memcpy(b+i*4,&x,4);}}return s.write(s.context,m.address(id)+base*item(t),b,count*item(t));}
}
bool Model::load(const void*data,std::size_t bytes,std::uint64_t cb,std::uint64_t ab,std::uint64_t capacity){
 *this={};struct Guard{Model*p;bool done=false;~Guard(){if(!done)*p={};}}guard{this};
 if(!data||bytes<64||reinterpret_cast<std::uintptr_t>(data)%8)return false;
 const auto*h=static_cast<const std::uint32_t*>(data);std::uint32_t crc=~0u;
 for(std::size_t i=0;i<bytes;++i){const auto byte=(i>=36&&i<40)?0:static_cast<const unsigned char*>(data)[i];crc^=byte;for(unsigned b=0;b<8;++b)crc=(crc>>1)^(0xedb88320u&std::uint32_t(-int(crc&1)));}
 if((crc^~0u)!=h[9])return false;
 const bool compact=h[0]==0x32475152&&h[1]==2;const unsigned hb=compact?128:64;
 if((!compact&&(h[0]!=0x31475452||h[1]!=1))||bytes<hb||!h[2]||!h[3]||h[2]>100000||h[3]>100000||h[4]>=h[2]||h[5]>=h[2]||h[6]!=bytes)return false;
 const std::uint64_t table_end=std::uint64_t(hb)+std::uint64_t(h[2])*64+std::uint64_t(h[3])*208;
 if(table_end>bytes)return false;
 if(compact&&(!h[11]||h[13]!=128||h[14]!=1||h[15]!=0||h[11]>h[3]||h[12]!=table_end||table_end+std::uint64_t(h[11])*128>bytes))return false;
 nt=h[2];nn=h[3];input=h[4];output=h[5];version=h[1];header=static_cast<const std::uint8_t*>(data);constant_bytes=h[7];arena_bytes=h[8];
 if(cb>capacity||constant_bytes>capacity-cb||ab>capacity||arena_bytes>capacity-ab)return false;
 if(cb<ab+arena_bytes&&ab<cb+constant_bytes)return false;
 constant_base=cb;arena_base=ab;t=reinterpret_cast<const Tensor*>(header+hb);n=reinterpret_cast<const Node*>(t+nt);
 if(compact){nq=h[11];q=reinterpret_cast<const QuantizedBinding*>(header+h[12]);}
 for(unsigned i=0;i<nt;++i){
  if(t[i].rank>8||(t[i].type!=1&&t[i].type!=6&&t[i].type!=7&&!(compact&&t[i].type==quantized_tensor_type))||t[i].constant>1)return false;
  std::uint64_t count=1;for(unsigned d=0;d<t[i].rank;++d){if(!t[i].d[d]||count>UINT32_MAX/t[i].d[d])return false;count*=t[i].d[d];}
  if(count!=t[i].count)return false;
  if(t[i].type==quantized_tensor_type){if(!t[i].constant||t[i].offset!=UINT64_MAX)return false;continue;}
  const auto limit=t[i].constant?constant_bytes:arena_bytes;if(t[i].offset>limit||count*item(t[i])>limit-t[i].offset)return false;
 }
 for(unsigned i=0;i<nn;++i){const auto&v=n[i];if(v.ni<1||v.ni>8||v.no<1||v.no>4||v.op<Add||v.op>GatherElementsOp)return false;
  for(int j=0;j<v.ni;++j)if(v.input[j]<-1||v.input[j]>=int(nt))return false;
  if(v.input[0]<0)return false;
  if((v.op==Add||v.op==Mul||v.op==Sub||v.op==Div||v.op==Pow||v.op==Conv||v.op==MatMul||v.op==Gemm||v.op==GridSampleOp||v.op==GatherElementsOp)&&(v.ni<2||v.input[1]<0))return false;
  for(int j=0;j<v.no;++j)if(v.output[j]<0||v.output[j]>=int(nt)||t[v.output[j]].constant)return false;
 }
 for(unsigned i=0;i<nq;++i){const auto&b=q[i];
  if(b.node>=nn||b.source_tensor>=nt||b.source_rank>8||b.reserved||!b.k||!b.n||b.pitch<b.k||b.pitch%16||b.data_offset%16||b.scale_offset%16||std::uint64_t(b.n)*b.pitch!=b.data_bytes||b.scale_bytes<std::uint64_t(b.n)*4||b.scale_bytes%16)return false;
  if(b.data_offset>constant_bytes||b.data_bytes>constant_bytes-b.data_offset||b.scale_offset>constant_bytes||b.scale_bytes>constant_bytes-b.scale_offset)return false;
  if(b.data_offset<b.scale_offset+b.scale_bytes&&b.scale_offset<b.data_offset+b.data_bytes)return false;
  const auto&v=n[b.node];const auto&source=t[b.source_tensor];if(source.type!=quantized_tensor_type)return false;if(v.ni<2||v.input[1]!=int(b.source_tensor)||!source.constant||source.rank!=b.source_rank)return false;
  for(unsigned d=0;d<b.source_rank;++d)if(source.d[d]!=b.dims[d])return false;
  const unsigned kind=v.op==Conv?unsigned(QuantizedConv):v.op==MatMul?unsigned(QuantizedMatMul):v.op==Gemm?unsigned(QuantizedGemm):0u;if(b.kind!=kind)return false;
  if(kind==QuantizedConv){if(source.rank!=4||b.n!=source.d[0]||b.k!=std::uint64_t(source.d[1])*source.d[2]*source.d[3])return false;}
  else {if(source.rank!=2)return false;const bool trans=kind==QuantizedGemm&&v.a[1];if(b.k!=source.d[trans?1:0]||b.n!=source.d[trans?0:1])return false;}
  for(unsigned j=0;j<i;++j){const auto&prev=q[j];if(prev.node==b.node)return false;
   auto overlap=[](std::uint64_t a,std::uint64_t an,std::uint64_t bb,std::uint64_t bn){return a<bb+bn&&bb<a+an;};
   const bool any=overlap(b.data_offset,b.data_bytes,prev.data_offset,prev.data_bytes)||overlap(b.data_offset,b.data_bytes,prev.scale_offset,prev.scale_bytes)||overlap(b.scale_offset,b.scale_bytes,prev.data_offset,prev.data_bytes)||overlap(b.scale_offset,b.scale_bytes,prev.scale_offset,prev.scale_bytes);
   if(any&&(b.source_tensor!=prev.source_tensor||b.k!=prev.k||b.n!=prev.n||b.pitch!=prev.pitch||b.data_offset!=prev.data_offset||b.data_bytes!=prev.data_bytes||b.scale_offset!=prev.scale_offset||b.scale_bytes!=prev.scale_bytes||std::memcmp(b.source_sha256,prev.source_sha256,32)))return false;
  }
 }
 if(compact){std::uint64_t quant_start=constant_bytes;for(unsigned i=0;i<nq;++i)quant_start=std::min(quant_start,std::min(q[i].data_offset,q[i].scale_offset));for(unsigned id=0;id<nt;++id)if(t[id].constant&&t[id].type!=quantized_tensor_type&&(t[id].offset>quant_start||t[id].count*item(t[id])>quant_start-t[id].offset))return false;}
 for(unsigned id=0;id<nt;++id)if(t[id].type==quantized_tensor_type){bool bound=false;for(unsigned i=0;i<nn;++i)for(int j=0;j<n[i].ni;++j)if(n[i].input[j]==int(id)){const auto*b=quantized(i);if(j!=1||!b||b->source_tensor!=id)return false;bound=true;}if(!bound)return false;}
 if(t[input].constant||t[output].constant){return false;}
 guard.done=true;return true;
}
bool run_graph(const Model&m,const GraphStorage&s,const GraphHooks&hooks,GraphStats&stats){stats={};if(!index32::validate(m,stats.error))return false;if(!m.t||!s.read||!s.write){stats.error="invalid_model_storage";return false;}if((hooks.require_external_conv&&!hooks.conv&&!hooks.conv_v2)||(hooks.require_external_matmul&&!hooks.matmul&&!hooks.matmul_v2)){stats.error="required_external_backend_missing";return false;}bool ok=true;double values[128];
for(unsigned node=0;node<m.nn;++node){if(s.cancelled&&s.cancelled(s.context)){stats.error="cancelled";return false;}if(hooks.progress)hooks.progress(hooks.context,node,m.nn);const auto&q=m.n[node];const auto&o=m.t[q.output[0]];
if(q.op==Reshape||q.op==Unsqueeze||q.op==Flatten){const auto&in=m.t[q.input[0]];if(q.no!=1||in.type!=o.type||in.count!=o.count||(in.type!=1&&in.type!=6&&in.type!=7)){stats.error="invalid_view_type_or_count";return false;}const auto source=m.address(q.input[0]),destination=m.address(q.output[0]);if(source!=UINT32_MAX&&destination!=UINT32_MAX&&source==destination){stats.completed=node+1;if(hooks.node_done&&!hooks.node_done(hooks.context,node,m,s)){stats.error="node_validation_failed";return false;}continue;}}
alignas(A) unsigned char cache_memory[8*sizeof(A)];A*access[8]{};for(int i=0;i<q.ni;++i)if(q.input[i]>=0&&m.t[q.input[i]].type!=quantized_tensor_type)access[i]=new(cache_memory+i*sizeof(A)) A(m,q.input[i],s,ok);A&x=*access[0];const auto&xt=x.t;stats.error="operator_execution_failed";
if(q.op==Conv){++stats.conv;const auto*binding=m.quantized(node);if(binding&&!hooks.conv_v2){stats.error="quantized_conv_backend_required";return false;}if(hooks.conv_v2){if(!hooks.conv_v2(hooks.context,m,q,s,binding))return false;++stats.external_conv;}else if(hooks.conv){if(!hooks.conv(hooks.context,m,q,s))return false;++stats.external_conv;}else{
 A&w=*access[1];const auto&wt=w.t;const unsigned icg=wt.d[1],ocg=o.d[1]/unsigned(q.a[10]);for(unsigned b=0;b<o.d[0];++b)for(unsigned oc=0;oc<o.d[1];++oc)for(unsigned yy=0;yy<o.d[2];++yy)for(unsigned xb=0;xb<o.d[3];xb+=128){if(s.cancelled&&s.cancelled(s.context))return false;const unsigned nn=std::min<unsigned>(128u,unsigned(o.d[3]-xb));float acc[128];float bias=0;if(q.ni>2&&q.input[2]>=0){A&ba=*access[2];bias=float(ba.get(oc));}std::fill(acc,acc+nn,bias);for(unsigned ic=0;ic<icg;++ic)for(unsigned ky=0;ky<wt.d[2];++ky)for(unsigned kx=0;kx<wt.d[3];++kx){const int iy=int(yy*q.a[2]+ky*q.a[8]-q.a[4]);if(iy<0||iy>=int(xt.d[2]))continue;const float weight=float(w.get(((std::uint32_t(oc)*icg+ic)*wt.d[2]+ky)*wt.d[3]+kx));for(unsigned j=0;j<nn;++j){const int ix=int((xb+j)*q.a[3]+kx*q.a[9]-q.a[5]);if(ix>=0&&ix<int(xt.d[3]))acc[j]+=float(x.get(((std::uint32_t(b)*xt.d[1]+(oc/ocg)*icg+ic)*xt.d[2]+unsigned(iy))*xt.d[3]+unsigned(ix)))*weight;}}for(unsigned j=0;j<nn;++j)values[j]=acc[j];if(!ok||!put(m,q.output[0],s,((std::uint32_t(b)*o.d[1]+oc)*o.d[2]+yy)*o.d[3]+xb,values,nn))return false;}
}}
else if(q.op==MatMul||q.op==Gemm){++stats.matmul;const auto*binding=m.quantized(node);if(binding&&!hooks.matmul_v2){stats.error="quantized_matmul_backend_required";return false;}if(hooks.matmul_v2){if(!hooks.matmul_v2(hooks.context,m,q,s,binding))return false;++stats.external_matmul;}else if(hooks.matmul){if(!hooks.matmul(hooks.context,m,q,s))return false;++stats.external_matmul;}else{A&b=*access[1];const auto&bt=b.t;const unsigned rows=o.d[o.rank-2],cols=o.d[o.rank-1],k=q.op==Gemm&&q.a[0]?xt.d[0]:xt.d[xt.rank-1];const std::uint32_t batches=o.count/rows/cols;
for(std::uint32_t batch=0;batch<batches;++batch){std::uint32_t coord[8]{};coords(o,batch*rows*cols,coord);auto batchbase=[&](const Tensor&t){std::uint32_t v=0;for(unsigned d=0;d+2<t.rank;++d)v=v*t.d[d]+(t.d[d]==1?0:coord[d+o.rank-t.rank]);return v*t.d[t.rank-2]*t.d[t.rank-1];};const auto abase=batchbase(xt),bbase=batchbase(bt);for(unsigned row=0;row<rows;++row)for(unsigned col=0;col<cols;col+=128){if(s.cancelled&&s.cancelled(s.context))return false;unsigned nn=std::min(128u,cols-col);float acc[128]{};for(unsigned kk=0;kk<k;++kk){float av=float(x.get(abase+(q.op==Gemm&&q.a[0]?std::uint32_t(kk)*rows+row:std::uint32_t(row)*k+kk)));for(unsigned j=0;j<nn;++j){const auto bi=q.op==Gemm&&q.a[1]?std::uint32_t(col+j)*k+kk:std::uint32_t(kk)*cols+col+j;acc[j]+=av*float(b.get(bbase+bi));}}
for(unsigned j=0;j<nn;++j){float v=acc[j]*(q.op==Gemm?q.f[0]:1);if(q.op==Gemm&&q.ni>2){A&c=*access[2];std::uint32_t cc[8]{};coords(o,(batch*rows+row)*cols+col+j,cc);v+=q.f[1]*float(c.get(broadcast(c.t,o,cc)));}values[j]=v;}if(!ok||!put(m,q.output[0],s,(batch*rows+row)*cols+col,values,nn))return false;}}}
}
else if(q.op==GridSampleOp){GridSample r;r.input=m.address(q.input[0]);r.grid=m.address(q.input[1]);r.output=m.address(q.output[0]);r.n=xt.d[0];r.c=xt.d[1];r.h=xt.d[2];r.w=xt.d[3];r.oh=o.d[2];r.ow=o.d[3];r.align_corners=q.a[0];GridStats gs;if(!grid_sample(r,s,gs))return false;}
else if(q.op==TopKOp){TopK r;r.input=m.address(q.input[0]);r.values=m.address(q.output[0]);r.indices=m.address(q.output[1]);r.width=xt.d[xt.rank-1];r.rows=unsigned(xt.count/r.width);r.k=unsigned(q.a[0]);if(!topk(r,s))return false;}
else if(q.op==GatherElementsOp){A&indices=*access[1];GatherElements r;r.input=m.address(q.input[0]);r.indices=m.address(q.input[1]);r.output=m.address(q.output[0]);r.rank=xt.rank;r.axis=unsigned(q.a[0]);for(unsigned d=0;d<r.rank&&d<4;++d){r.data_shape[d]=xt.d[d];r.index_shape[d]=indices.t.d[d];}if(!gather_elements(r,s))return false;}
else if(q.op==Softmax){const unsigned axis=unsigned(q.a[0]);std::uint32_t inner=1;for(unsigned d=axis+1;d<xt.rank;++d)inner*=xt.d[d];const auto width=xt.d[axis];const auto outer=xt.count/inner/width;for(std::uint32_t outeri=0;outeri<outer;++outeri)for(std::uint32_t in=0;in<inner;++in){const auto base=outeri*width*inner+in;float mx=-INFINITY;for(unsigned j=0;j<width;++j)mx=std::max(mx,float(x.get(base+j*inner)));float sum=0;for(unsigned j=0;j<width;++j)sum+=std::exp(float(x.get(base+j*inner))-mx);for(unsigned j=0;j<width;++j){double v=std::exp(float(x.get(base+j*inner))-mx)/sum;if(!ok||!put(m,q.output[0],s,base+j*inner,&v,1))return false;}}}
else {for(int oi=0;oi<q.no;++oi){const auto&ot=m.t[q.output[oi]];for(std::uint32_t base=0;base<ot.count;base+=128){if(s.cancelled&&s.cancelled(s.context))return false;unsigned count=unsigned(std::min<std::uint32_t>(128,ot.count-base));for(unsigned j=0;j<count;++j){const auto index=base+j;std::uint32_t c[8]{};coords(ot,index,c);double v=0;
switch(q.op){
case Reshape:case Unsqueeze:case Flatten:case Cast:v=x.get(index);break;
case Transpose:{std::uint32_t cc[8]{};for(unsigned d=0;d<ot.rank;++d)cc[q.a[d]]=c[d];v=x.get(linear(xt,cc));break;}
case Slice:{std::uint32_t cc[8]{};for(unsigned d=0;d<ot.rank;++d)cc[d]=std::uint32_t(q.a[d]+std::int64_t(c[d])*q.a[8+d]);v=x.get(linear(xt,cc));break;}
case Tile:{std::uint32_t cc[8]{};for(unsigned d=0;d<ot.rank;++d)cc[d]=c[d]%xt.d[d];v=x.get(linear(xt,cc));break;}
case Concat:{auto axis=unsigned(q.a[0]);std::uint32_t t=c[axis];for(int in=0;in<q.ni;++in){A&a=*access[in];if(t<a.t.d[axis]){c[axis]=t;v=a.get(linear(a.t,c));break;}t-=a.t.d[axis];}break;}
case Split:{auto axis=unsigned(q.a[0]);for(int z=0;z<oi;++z)c[axis]+=m.t[q.output[z]].d[axis];v=x.get(linear(xt,c));break;}
case Resize:{std::uint32_t cc[8]{};for(unsigned d=0;d<ot.rank;++d)cc[d]=std::min<std::uint32_t>(xt.d[d]-1,c[d]*xt.d[d]/ot.d[d]);v=x.get(linear(xt,cc));break;}
case ReduceMean:case ReduceSum:case ReduceMax:{std::uint32_t cc[8]{},rcount=1;unsigned od=0;for(unsigned d=0;d<xt.rank;++d){if(q.a[0]&(1<<d)){rcount*=xt.d[d];if(q.a[1])++od;}else cc[d]=c[od++];}float acc=q.op==ReduceMax?-INFINITY:0;for(std::uint32_t ri=0;ri<rcount;++ri){auto t=ri;for(unsigned d=xt.rank;d-->0;)if(q.a[0]&(1<<d)){cc[d]=t%xt.d[d];t/=xt.d[d];}float a=float(x.get(linear(xt,cc)));acc=q.op==ReduceMax?std::max(acc,a):acc+a;}v=q.op==ReduceMean?acc/float(rcount):acc;break;}
case MaxPool:case AveragePool:{float acc=q.op==MaxPool?-INFINITY:0;unsigned divisor=0;for(int ky=0;ky<q.a[0];++ky)for(int kx=0;kx<q.a[1];++kx){const int yy=int(c[2]*q.a[2]+ky*q.a[8]-q.a[4]),xx=int(c[3]*q.a[3]+kx*q.a[9]-q.a[5]);if(yy>=0&&xx>=0&&yy<int(xt.d[2])&&xx<int(xt.d[3])){float a=float(x.get(((c[0]*xt.d[1]+c[1])*xt.d[2]+unsigned(yy))*xt.d[3]+unsigned(xx)));acc=q.op==MaxPool?std::max(acc,a):acc+a;++divisor;}else if(q.a[11])++divisor;}v=q.op==AveragePool?acc/divisor:acc;break;}
default:{const float a=float(x.get(broadcast(xt,ot,c)));float b=0;if(q.ni>1&&q.input[1]>=0){A&y=*access[1];b=float(y.get(broadcast(y.t,ot,c)));}switch(q.op){case Add:v=a+b;break;case Mul:v=a*b;break;case Sub:v=a-b;break;case Div:v=a/b;break;case Pow:v=std::pow(a,b);break;case Relu:v=std::max(0.f,a);break;case Sigmoid:v=1.f/(1.f+std::exp(-a));break;case Sqrt:v=std::sqrt(a);break;case Log:v=std::log(a);break;case Erf:v=std::erf(a);break;case Clip:{float high=INFINITY,low=-INFINITY;if(q.ni>1&&q.input[1]>=0)low=b;if(q.ni>2&&q.input[2]>=0){A&y=*access[2];high=float(y.get(0));}v=std::max(low,std::min(high,a));break;}default:stats.error="unsupported_operator";return false;}break;}
}values[j]=v;}if(!ok||!put(m,q.output[oi],s,base,values,count))return false;}}}
if(!ok){return false;}
stats.completed=node+1;if(hooks.node_done&&!hooks.node_done(hooks.context,node,m,s)){stats.error="node_validation_failed";return false;}}
stats.error="none";return true;}
}}
