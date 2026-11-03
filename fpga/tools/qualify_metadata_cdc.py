"""Narrow bundled-data CDC structural qualification; no timing exceptions written."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sdf',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 raw=ROOT/'link/rtl/link_reply_raw.v';core=ROOT/'link/rtl/link_bringup_filtered.v'
 r=re.sub(r'//[^\n]*','',raw.read_text());r=re.sub(r'\s+','',r)
 for exact in ['reg[49:0]metadata_meta,metadata_bus;','metadata_meta<=0;','metadata_meta<=metadata;','metadata_bus<=metadata_meta;']:
  assert r.count(exact)==1,exact
  r=r.replace(exact,'')
 assert not re.search(r'\bmetadata_meta\b',r),'stage0 has additional functional consumer'
 c=re.sub(r'\s+','',re.sub(r'//[^\n]*','',core.read_text()))
 assert c.count('fast_metadata<=')==2
 assert 'if(fast_prepare==2)beginfast_metadata<={tile_mode,bulk_mode,reply[5],reply[4],reply[3],reply[2],reply[1],reply[0]};fast_prepare<=1;' in c
 assert 'elseif(fast_prepare==1&&!raw_done_sync[1])beginfast_offer<=1;fast_prepare<=0;' in c
 text=a.sdf.read_text();norm=lambda x:x.replace('\\/','/').replace('\\.','.')
 instances={norm(x) for x in re.findall(r'\(INSTANCE\s+([^\s)]+metadata_meta_\d+_s0)\)',text)}
 assert instances
 edges=[(norm(x),norm(y),d) for x,y,d in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+\(([\d.:+-]+)\)',text)]
 rows=[]
 for inst in sorted(instances):
  bit=int(re.search(r'metadata_meta_(\d+)_s0',inst).group(1))
  incoming=[x for x in edges if x[1]==inst+'/D'];outgoing=[x for x in edges if x[0]==inst+'/Q']
  assert len(incoming)==len(outgoing)==1,(inst,incoming,outgoing)
  assert incoming[0][0]==f'core/fast_metadata_{bit}_s0/Q'
  assert outgoing[0][1]==f'core/fast_serializer.serializer/metadata_bus_{bit}_s0/D'
  rows.append(dict(bit=bit,first_stage_D=inst+'/D',source_Q=incoming[0][0],only_Q_consumer=outgoing[0][1],stage01_interconnect_ns=outgoing[0][2]))
 d=dict(hardware_access=False,scope='Source and actual mapped fanout qualification only; NOT metastability MTBF or physical timing proof',logical_stage_width=50,mapped_first_stage_count=len(rows),source_sha256={str(x.relative_to(ROOT)):sha(x) for x in [raw,core]},sdf_sha256=sha(a.sdf),first_stage_pins=rows,no_stage0_functional_fanout=True,exception_written=False)
 a.output.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mapped_first_stage_count':len(rows),'only_stage1_fanout':True,'output':str(a.output)}))
if __name__=='__main__':main()
