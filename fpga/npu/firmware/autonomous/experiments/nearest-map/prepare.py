from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
FW=HERE.parents[1]
INDEX=HERE.parent/'index32'
HELPER=r"""
bool resize_mapped_eligible(const Tensor&x,const Tensor&o){if(!o.rank||o.rank!=x.rank||o.rank>8)return false;unsigned sum=0;for(unsigned d=0;d<o.rank;++d){if(!o.d[d]||!x.d[d]||o.d[d]>4096-sum)return false;sum+=o.d[d];}return true;}
bool resize_mapped(const Model&m,unsigned output,const GraphStorage&s,A&x,bool&ok){
 const auto&o=m.t[output];const auto&xt=x.t;std::uint32_t map[4096],offset[8]{},stride[8]{},coord[8]{};unsigned end=0;std::uint32_t step=1;
 for(unsigned d=xt.rank;d-->0;){stride[d]=step;step*=xt.d[d];}
 for(unsigned d=0;d<o.rank;++d){offset[d]=end;for(std::uint32_t c=0;c<o.d[d];++c)map[end++]=std::min<std::uint32_t>(xt.d[d]-1,c*xt.d[d]/o.d[d])*stride[d];}
 double values[128];for(std::uint32_t base=0;base<o.count;base+=128){if(s.cancelled&&s.cancelled(s.context))return false;const unsigned count=unsigned(std::min<std::uint32_t>(128,o.count-base));for(unsigned j=0;j<count;++j){std::uint32_t source=0;for(unsigned d=0;d<o.rank;++d)source+=map[offset[d]+coord[d]];values[j]=x.get(source);for(unsigned d=o.rank;d-->0;){if(++coord[d]<o.d[d])break;coord[d]=0;}}if(!ok||!put(m,output,s,base,values,count))return false;}return true;
}
"""
def prepare():
 src=INDEX/'generated/rtdetr_graph.cpp';s=src.read_text(encoding='utf-8');assert hashlib.sha256(src.read_bytes()).hexdigest()=='4c27743df01793df97c0d9d14026600ebc3bf869c142651b0f02e9edadde55c6'
 marker='\n}\nbool Model::load';assert s.count(marker)==1;s=s.replace(marker,'\n'+HELPER+marker,1)
 marker='else {for(int oi=0;oi<q.no;++oi)';assert s.count(marker)==1;s=s.replace(marker,'else if(q.op==Resize&&q.no==1&&resize_mapped_eligible(xt,o)){if(!resize_mapped(m,unsigned(q.output[0]),s,x,ok))return false;}\n'+marker,1)
 out=HERE/'build/generated/rtdetr_graph.cpp';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s,encoding='utf-8');return out
if __name__=='__main__':print(prepare())
