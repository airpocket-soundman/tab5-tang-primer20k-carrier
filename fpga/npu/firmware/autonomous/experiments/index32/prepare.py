"""Generate bounded32bit hot-loop indices; preserve Model.load and all floating code."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
FW=HERE.parents[1]
SOURCE=FW/'vendor/host/main/inference/rtdetr_graph.cpp'
def prepare():
 raw=SOURCE.read_bytes();expected=json.loads((FW/'vendor/host/PINNED_SOURCE.json').read_text())['files_sha256']['main/inference/rtdetr_graph.cpp'];assert hashlib.sha256(raw).hexdigest()==expected
 text=raw.decode('utf-8');a=text.index('bool Model::load(');b=text.index('bool run_graph(');before,loader,runner=text[:a],text[a:b],text[b:]
 def hot(s):return s.replace('std::uint64_t','std::uint32_t').replace('UINT64_MAX','UINT32_MAX')
 transformed=hot(before)+loader+hot(runner);old='GraphStats&stats){stats={};';assert transformed.count(old)==1;transformed=transformed.replace(old,old+'if(!index32::validate(m,stats.error))return false;',1)
 transformed=transformed.replace('#include "rtdetr_graph.hpp"','#include "rtdetr_graph.hpp"\n#include "index32_contract.hpp"',1)
 # The loader remains literally unmodified, including64bit range/overflow/binding checks.
 new_a=transformed.index('bool Model::load(');new_b=transformed.index('bool run_graph(');assert transformed[new_a:new_b].encode()==loader.encode()
 out=HERE/'generated';out.mkdir(exist_ok=True);(out/'rtdetr_graph.cpp').write_bytes(transformed.encode('utf-8'))
 proof={'source':str(SOURCE),'source_sha256':hashlib.sha256(raw).hexdigest(),'generated_sha256':hashlib.sha256(transformed.encode()).hexdigest(),'Model_load_sha256_UNCHANGED':hashlib.sha256(loader.encode()).hexdigest(),'hot_uint64_occurrences_replaced':before.count('std::uint64_t')+runner.count('std::uint64_t'),'changes':['Only unsigned64 hot index/address/coordinate types narrowed to unsigned32','UINT64_MAX private cache sentinel narrowed to UINT32_MAX','Preflight model-specific guard inserted before run','Tensor/Node ABI, signed INT64 data, all float/double expressions and Model.load remain unchanged'],'model':'RQG2 RT-DETRderived300 metadataCRC763848396','profile':'80MiB DDR graph, count<2^25, Resize cross-products and Slice endpoints checked; not arbitraryONNX support'}
 (out/'provenance.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');return out/'rtdetr_graph.cpp'
if __name__=='__main__':print(prepare())
