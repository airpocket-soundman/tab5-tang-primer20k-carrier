"""Generate exactly30 source-Q to async stage0-D exceptions; never stage1."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--proof',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
 proof=json.loads(a.proof.read_text());rows=proof['first_stage_pins']
 assert proof['no_stage0_functional_fanout'] and proof['logical_stage_width']==50 and proof['mapped_first_stage_count']==len(rows)==30
 assert len({r['bit']for r in rows})==30
 for source,digest in proof['source_sha256'].items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,'source drift:'+source
 lines=[(ROOT/'constraints/dock/triangle54filtered_official.sdc').read_text().rstrip(),'','# Qualified bundled-data CDC FIRST STAGE ONLY; see Metadata_CDC qualification.','# Source SHA256 '+json.dumps(proof['source_sha256'],sort_keys=True),'# EXACT_EXCEPTION_COUNT 30; do not wildcard or exempt metadata_bus.']
 stage0=[];stage1=[]
 for r in rows:
  bit=r['bit'];first=f'core/fast_serializer.serializer/metadata_meta_{bit}_s0/D';source=f'core/fast_metadata_{bit}_s0/Q';second=f'core/fast_serializer.serializer/metadata_bus_{bit}_s0/D'
  assert r['first_stage_D']==first and r['source_Q']==source and r['only_Q_consumer']==second
  lines.append(f'set_false_path -from [get_pins {{{source}}}] -to [get_pins {{{first}}}]')
  stage0.append(first[:-1]+'Q');stage1.append(second)
 for kind in ['setup','hold']:
  lines.append(f'report_timing -{kind} -from [get_pins {{{" ".join(stage0)}}}] -to [get_pins {{{" ".join(stage1)}}}] -max_paths 30 -max_common_paths 1')
 result='\n'.join(lines)+'\n'
 if a.verify:assert a.output.read_text()==result,'generated constraint drift'
 else:a.output.write_text(result)
 print(json.dumps(dict(exceptions=30,source_hashes_verified=True,stage01_paths_requested_per_analysis=30,constraint_sha256=hashlib.sha256(result.encode()).hexdigest())))
if __name__=='__main__':main()
